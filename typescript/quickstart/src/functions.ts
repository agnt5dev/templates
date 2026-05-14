/**
 * Steps for the Hacker News digest workflow.
 *
 * Each `fn(...)` is a durable step. When called inside a workflow, the runtime
 * checkpoints the result — a worker restart skips steps that already completed.
 */

import { fn, Agent, LM } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

const HN_TOP = 'https://hacker-news.firebaseio.com/v0/topstories.json';
const HN_ITEM = (id: number) =>
  `https://hacker-news.firebaseio.com/v0/item/${id}.json`;

const SUMMARIZER_PROMPT = `You are summarizing a Hacker News story for a busy
engineer. Given a title and (if available) a URL, write 1-2 plain sentences
covering what the story is and why it might matter. No marketing language.`;

interface Story {
  id: number;
  title: string;
  url?: string;
  score: number;
  by?: string;
}

interface SummarizedStory {
  id: number;
  title: string;
  url?: string;
  summary: string;
}

// 1. Fetch the current top story IDs from HN.
export const fetchTopIds = fn('fetch_top_ids').run(
  async (ctx: Context, input: { limit: number }): Promise<number[]> => {
    const resp = await fetch(HN_TOP);
    if (!resp.ok) throw new Error(`HN topstories HTTP ${resp.status}`);
    const ids = (await resp.json()) as number[];
    ctx.logger.info(`Fetched ${ids.length} top IDs, taking first ${input.limit}`);
    return ids.slice(0, input.limit);
  },
);

// 2. Fetch one HN story by ID.
export const fetchStory = fn('fetch_story').run(
  async (_ctx: Context, input: { storyId: number }): Promise<Story> => {
    const resp = await fetch(HN_ITEM(input.storyId));
    if (!resp.ok) throw new Error(`HN item HTTP ${resp.status}`);
    const story = ((await resp.json()) ?? {}) as Partial<Story>;
    return {
      id: input.storyId,
      title: story.title ?? '(no title)',
      url: story.url,
      score: story.score ?? 0,
      by: story.by,
    };
  },
);

// 3. Summarize one story with a small model call. The Agent.run(..., ctx) call
//    threads the workflow context, so the model call is also checkpointed.
export const summarize = fn('summarize').run(
  async (ctx: Context, input: { story: Story }): Promise<SummarizedStory> => {
    const { story } = input;
    const prompt = `Title: ${story.title}\nURL: ${story.url ?? '(no link)'}`;

    const agent = new Agent({
      name: 'hn_summarizer',
      model: LM.openai(),
      modelName: 'openai/gpt-5-mini',
      instructions: SUMMARIZER_PROMPT,
    });
    const result = await agent.run(prompt, ctx);

    return {
      id: story.id,
      title: story.title,
      url: story.url,
      summary: result.output.trim(),
    };
  },
);

// 4. Combine the per-story summaries into a single readable digest.
export const assembleDigest = fn('assemble_digest').run(
  async (
    _ctx: Context,
    input: { summaries: SummarizedStory[] },
  ): Promise<{ count: number; digest: string }> => {
    const lines: string[] = ['# Hacker News digest\n'];
    input.summaries.forEach((s, i) => {
      const link = s.url ? ` — ${s.url}` : '';
      lines.push(`${i + 1}. **${s.title}**${link}\n   ${s.summary}\n`);
    });
    return {
      count: input.summaries.length,
      digest: lines.join('\n'),
    };
  },
);
