/**
 * The `digest` workflow — fan out across the top Hacker News stories.
 *
 * Each step runs through `ctx.step`, which checkpoints its result. If the
 * worker crashes after some stories have been summarized, the runtime replays
 * the finished steps from their checkpoints and runs only the missing ones —
 * model calls included. A function called directly, without `ctx.step`, would
 * run again on every replay.
 *
 *     digest (workflow)
 *     ├─ fetch_top_ids
 *     ├─ fetch_story  (×N parallel, keyed by story ID)
 *     ├─ summarize    (×N parallel, keyed by story ID)
 *     └─ assemble_digest
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import {
  assembleDigest,
  fetchStory,
  fetchTopIds,
  summarize,
} from './functions.js';
import type { Digest, Story, SummarizedStory } from './functions.js';

export const digest = workflow(
  'digest',
  async (ctx: Context, input: { limit?: number } = {}): Promise<Digest> => {
    const limit = input.limit ?? 5;
    ctx.logger.info(`Starting digest for top ${limit} stories`);

    // 1. Pull the IDs — one checkpoint.
    const ids = await ctx.step<number[]>('fetch_top_ids', () => fetchTopIds(ctx, { limit }));

    // 2. Fan out: one checkpoint per story. Promise.all runs them concurrently,
    //    so each step is keyed by its story ID to match it to its checkpoint on
    //    replay whatever order they finish in.
    const stories = await Promise.all(
      ids.map((storyId) =>
        ctx.step<Story>('fetch_story', () => fetchStory(ctx, { storyId }), {
          key: String(storyId),
        }),
      ),
    );

    // 3. Fan out again on summarization, one keyed checkpoint per story.
    const summaries = await Promise.all(
      stories.map((story) =>
        ctx.step<SummarizedStory>('summarize', () => summarize(ctx, { story }), {
          key: String(story.id),
        }),
      ),
    );

    // 4. Combine. One last checkpoint, then return.
    return ctx.step<Digest>('assemble_digest', () => assembleDigest(ctx, { summaries }));
  },
);
