// Steps for the Hacker News digest workflow.
//
// Each plain function here is wrapped in an agnt5.Step inside the digest
// workflow (see workflows.go), which checkpoints its result. It's also
// registered standalone via RegisterFunction so it can be run and inspected
// on its own with `agnt5 run <name>`.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

const (
	hnTopStoriesURL = "https://hacker-news.firebaseio.com/v0/topstories.json"
	hnItemURLFormat = "https://hacker-news.firebaseio.com/v0/item/%d.json"

	summarizerPrompt = `You are summarizing a Hacker News story for a busy
engineer. Given a title and (if available) a URL, write 1-2 plain sentences
covering what the story is and why it might matter. No marketing language.`
)

var httpClient = &http.Client{Timeout: 10 * time.Second}

// summarizer is the agent used by summarize. Assigned once in main() before
// the worker starts registering components.
var summarizer *agnt5.Agent

// Story is one Hacker News story.
type Story struct {
	ID    int    `json:"id"`
	Title string `json:"title"`
	URL   string `json:"url,omitempty"`
	Score int    `json:"score"`
	By    string `json:"by,omitempty"`
}

// SummarizedStory is a Story plus its generated summary.
type SummarizedStory struct {
	ID      int    `json:"id"`
	Title   string `json:"title"`
	URL     string `json:"url,omitempty"`
	Summary string `json:"summary"`
}

type FetchTopIDsInput struct {
	Limit int `json:"limit"`
}

type FetchStoryInput struct {
	StoryID int `json:"story_id"`
}

type SummarizeInput struct {
	Story Story `json:"story"`
}

type AssembleDigestInput struct {
	Summaries []SummarizedStory `json:"summaries"`
}

type DigestOutput struct {
	Count  int    `json:"count"`
	Digest string `json:"digest"`
}

// fetchTopIDs returns the first `limit` IDs from the HN top-stories feed.
func fetchTopIDs(ctx context.Context, limit int) ([]int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, hnTopStoriesURL, nil)
	if err != nil {
		return nil, err
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HN topstories HTTP %d", resp.StatusCode)
	}

	var ids []int
	if err := json.NewDecoder(resp.Body).Decode(&ids); err != nil {
		return nil, err
	}
	if limit < len(ids) {
		ids = ids[:limit]
	}
	return ids, nil
}

func fetchTopIDsFunction(ctx *agnt5.Context, in FetchTopIDsInput) ([]int, error) {
	ids, err := fetchTopIDs(ctx, in.Limit)
	if err != nil {
		return nil, err
	}
	ctx.Logger().Info("Fetched top IDs", "count", len(ids), "limit", in.Limit)
	return ids, nil
}

// fetchStory fetches one HN story by ID.
func fetchStory(ctx context.Context, storyID int) (Story, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, fmt.Sprintf(hnItemURLFormat, storyID), nil)
	if err != nil {
		return Story{}, err
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return Story{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return Story{}, fmt.Errorf("HN item HTTP %d", resp.StatusCode)
	}

	var raw struct {
		Title string `json:"title"`
		URL   string `json:"url"`
		Score int    `json:"score"`
		By    string `json:"by"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return Story{}, err
	}

	title := raw.Title
	if title == "" {
		title = "(no title)"
	}
	return Story{ID: storyID, Title: title, URL: raw.URL, Score: raw.Score, By: raw.By}, nil
}

func fetchStoryFunction(ctx *agnt5.Context, in FetchStoryInput) (Story, error) {
	return fetchStory(ctx, in.StoryID)
}

// summarize summarizes one story with a small model call. The agent runs
// through the invocation's *agnt5.Context, so the model call is checkpointed
// as part of whichever Step wraps this call.
func summarize(ctx *agnt5.Context, story Story) (SummarizedStory, error) {
	link := story.URL
	if link == "" {
		link = "(no link)"
	}
	prompt := fmt.Sprintf("Title: %s\nURL: %s", story.Title, link)

	result, err := summarizer.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		return SummarizedStory{}, err
	}
	return SummarizedStory{
		ID:      story.ID,
		Title:   story.Title,
		URL:     story.URL,
		Summary: strings.TrimSpace(result.Response),
	}, nil
}

func summarizeFunction(ctx *agnt5.Context, in SummarizeInput) (SummarizedStory, error) {
	return summarize(ctx, in.Story)
}

// assembleDigest combines the per-story summaries into one readable digest.
func assembleDigest(summaries []SummarizedStory) DigestOutput {
	var b strings.Builder
	b.WriteString("# Hacker News digest\n\n")
	for i, s := range summaries {
		link := ""
		if s.URL != "" {
			link = " — " + s.URL
		}
		fmt.Fprintf(&b, "%d. **%s**%s\n   %s\n\n", i+1, s.Title, link, s.Summary)
	}
	return DigestOutput{Count: len(summaries), Digest: b.String()}
}

func assembleDigestFunction(ctx *agnt5.Context, in AssembleDigestInput) (DigestOutput, error) {
	return assembleDigest(in.Summaries), nil
}
