/**
 * The `digest` workflow — fan out across the top Hacker News stories.
 *
 * Every step call is a durable checkpoint. If the worker crashes after some
 * stories have been summarized, the runtime re-runs only the missing ones —
 * model calls included.
 *
 *     digest (workflow)
 *     ├─ fetch_top_ids
 *     ├─ fetch_story  (×N parallel)
 *     ├─ summarize    (×N parallel)
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

export const digest = workflow(
  'digest',
  async (ctx: Context, input: { limit?: number } = {}) => {
    const limit = input.limit ?? 5;
    ctx.logger.info(`Starting digest for top ${limit} stories`);

    // 1. Pull the IDs — one checkpoint.
    const ids = await fetchTopIds(ctx, { limit });

    // 2. Fan out: each fetchStory is its own checkpoint. Promise.all runs them
    //    concurrently. A worker restart resumes from whichever had completed.
    const stories = await Promise.all(
      ids.map((storyId) => fetchStory(ctx, { storyId })),
    );

    // 3. Fan out again on summarization. The Agent inside each summarize call
    //    threads `ctx`, so model calls also checkpoint.
    const summaries = await Promise.all(
      stories.map((story) => summarize(ctx, { story })),
    );

    // 4. Combine. One last checkpoint, then return.
    return assembleDigest(ctx, { summaries });
  },
);
