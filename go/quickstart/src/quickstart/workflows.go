// The digest workflow — fan out across the top Hacker News stories.
//
// Every agnt5.Step call is a durable checkpoint. If the worker crashes after
// some stories have been summarized, the runtime re-runs only the steps that
// hadn't completed — model calls included.
package quickstart

import (
	"context"
	"errors"
	"sync"

	"agnt5.dev/sdk-go/agnt5"
)

type DigestInput struct {
	Limit int `json:"limit"`
}

// digestWorkflow fetches the top `limit` HN stories, summarizes them in
// parallel, and assembles a single digest.
//
// Trace shape:
//
//	digest (workflow)
//	├─ fetch_top_ids
//	├─ fetch_stories     (parallel fan-out inside one Step)
//	├─ summarize_stories (parallel fan-out inside one Step)
//	└─ assemble_digest
func DigestWorkflow(ctx *agnt5.Context, in DigestInput) (DigestOutput, error) {
	limit := in.Limit
	if limit <= 0 {
		limit = 5
	}
	ctx.Logger().Info("Starting digest", "limit", limit)

	// 1. One checkpoint: pull the IDs.
	ids, err := agnt5.Step(ctx, "fetch_top_ids", func(c context.Context) ([]int, error) {
		return fetchTopIDs(c, limit)
	})
	if err != nil {
		return DigestOutput{}, err
	}

	// 2. Fan out: fetch every story concurrently, checkpointed as one Step.
	//    A worker restart re-runs this whole step, not just the missing
	//    stories — coarser-grained than Python/TypeScript's per-item
	//    checkpointing, since Go has no per-iteration fan-out primitive yet.
	stories, err := agnt5.Step(ctx, "fetch_stories", func(c context.Context) ([]Story, error) {
		return fetchAllStories(c, ids)
	})
	if err != nil {
		return DigestOutput{}, err
	}

	// 3. Fan out again on summarization, also checkpointed as one Step. Each
	//    goroutine's agent call goes through the same ctx, so the model
	//    calls are recorded as part of this step's result.
	summaries, err := agnt5.Step(ctx, "summarize_stories", func(context.Context) ([]SummarizedStory, error) {
		return summarizeAllStories(ctx, stories)
	})
	if err != nil {
		return DigestOutput{}, err
	}

	// 4. Combine. One last checkpoint, then return.
	return agnt5.Step(ctx, "assemble_digest", func(context.Context) (DigestOutput, error) {
		return assembleDigest(summaries), nil
	})
}

func fetchAllStories(ctx context.Context, ids []int) ([]Story, error) {
	stories := make([]Story, len(ids))
	errs := make([]error, len(ids))

	var wg sync.WaitGroup
	for i, id := range ids {
		wg.Add(1)
		go func(i, id int) {
			defer wg.Done()
			stories[i], errs[i] = fetchStory(ctx, id)
		}(i, id)
	}
	wg.Wait()

	if err := errors.Join(errs...); err != nil {
		return nil, err
	}
	return stories, nil
}

func summarizeAllStories(ctx *agnt5.Context, stories []Story) ([]SummarizedStory, error) {
	summaries := make([]SummarizedStory, len(stories))
	errs := make([]error, len(stories))

	var wg sync.WaitGroup
	for i, story := range stories {
		wg.Add(1)
		go func(i int, story Story) {
			defer wg.Done()
			summaries[i], errs[i] = summarize(ctx, story)
		}(i, story)
	}
	wg.Wait()

	if err := errors.Join(errs...); err != nil {
		return nil, err
	}
	return summaries, nil
}
