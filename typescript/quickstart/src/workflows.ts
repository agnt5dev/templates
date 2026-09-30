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

/**
 * Run `fn` as a checkpointed step and return its result. On replay the
 * checkpoint can come back as its JSON text rather than the value, so a string
 * is decoded before use. Every step here returns an object or an array, never
 * a string, so the decode can't misread a real result.
 */
async function step<T>(ctx: Context, name: string, fn: () => T | Promise<T>, key?: string): Promise<T> {
  const result = await ctx.step<T | string>(name, fn, key === undefined ? undefined : { key });
  return typeof result === 'string' ? (JSON.parse(result) as T) : result;
}

export const digest = workflow(
  'digest',
  async (ctx: Context, input: { limit?: number } = {}): Promise<Digest> => {
    const limit = input.limit ?? 5;
    ctx.logger.info(`Starting digest for top ${limit} stories`);

    // 1. Pull the IDs — one checkpoint.
    const ids = await step<number[]>(ctx, 'fetch_top_ids', () => fetchTopIds(ctx, { limit }));

    // 2. Fan out: one checkpoint per story. Promise.all runs them concurrently,
    //    so each step is keyed by its story ID to match it to its checkpoint on
    //    replay whatever order they finish in.
    const stories = await Promise.all(
      ids.map((storyId) =>
        step<Story>(ctx, 'fetch_story', () => fetchStory(ctx, { storyId }), String(storyId)),
      ),
    );

    // 3. Fan out again on summarization, one keyed checkpoint per story.
    const summaries = await Promise.all(
      stories.map((story) =>
        step<SummarizedStory>(ctx, 'summarize', () => summarize(ctx, { story }), String(story.id)),
      ),
    );

    // 4. Combine. One last checkpoint, then return.
    return step<Digest>(ctx, 'assemble_digest', () => assembleDigest(ctx, { summaries }));
  },
);
