/**
 * Steps for the release announcement workflow.
 *
 * Each `fn(...)` is a function the workflow runs inside `ctx.step(...)`: its
 * result is checkpointed, and a replay returns the checkpoint instead of
 * running the code again (see workflows.ts).
 */

import { readFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { Agent, LM, fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { idempotencyKey, logExecution, mockMode, readExecutionLog } from './demo.js';
import { sendOnce } from './outbox.js';

const MODEL = process.env.RELEASE_MODEL || 'openai/gpt-6-luna';
const PRS_FILE = new URL('./prs.json', import.meta.url);

export interface PullRequest {
  number: number;
  title: string;
  author: string;
  body: string;
  mock_summary: string;
}

export interface PrSummary {
  number: number;
  title: string;
  summary: string;
}

export interface Published {
  channel: string;
  published: boolean;
  duplicate_skipped: boolean;
}

async function generate(ctx: Context, instructions: string, prompt: string, mock: string): Promise<string> {
  if (mockMode()) {
    await sleep(Number(process.env.RELEASE_MOCK_LATENCY_MS ?? 1500));
    return mock;
  }
  const agent = new Agent({
    name: 'release_writer',
    model: LM.openai(),
    modelName: MODEL,
    temperature: 1, // gpt-6 accepts only its default temperature
    instructions,
  });
  return (await agent.run(prompt, ctx)).output.trim();
}

// Load the pull requests merged for this release (a bundled sample).
export const loadPrs = fn('load_prs').run(
  async (ctx: Context, input: { release: string }): Promise<PullRequest[]> => {
    logExecution(ctx.runId, 'load_prs', input.release);
    return JSON.parse(readFileSync(PRS_FILE, 'utf8')) as PullRequest[];
  },
);

// Summarize one PR for users. One LLM call, one checkpoint.
export const summarizePr = fn('summarize_pr').run(
  async (ctx: Context, input: { pr: PullRequest }): Promise<PrSummary> => {
    const { pr } = input;
    logExecution(ctx.runId, 'summarize_pr', `#${pr.number}`);
    const summary = await generate(
      ctx,
      'Summarize this pull request in one sentence for end users. No jargon.',
      `${pr.title}\n\n${pr.body}`,
      pr.mock_summary,
    );
    return { number: pr.number, title: pr.title, summary };
  },
);

// Turn the PR summaries into one announcement.
export const draftAnnouncement = fn('draft_announcement').run(
  async (ctx: Context, input: { release: string; summaries: PrSummary[] }): Promise<{ text: string }> => {
    logExecution(ctx.runId, 'draft_announcement', input.release);
    const bullets = input.summaries.map((s) => `- ${s.summary} (#${s.number})`).join('\n');
    const text = await generate(
      ctx,
      'Write a short, friendly release announcement from these changes. Keep the bullet list.',
      `Release ${input.release}\n${bullets}`,
      `${input.release} is out! Here's what changed:\n${bullets}`,
    );
    return { text };
  },
);

// Check the PR links in the draft. Fails `flakyFailures` times first; the
// retry policy absorbs the failures.
export const checkLinks = fn('check_links')
  .retry({ maxAttempts: 4, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential' })
  .run(async (ctx: Context, input: { draft: string; flakyFailures: number }) => {
    logExecution(ctx.runId, 'check_links', '', ctx.attempt);
    if (ctx.attempt < input.flakyFailures) {
      ctx.logger.warn(`Link checker timed out (attempt ${ctx.attempt + 1}) - will retry`);
      throw new Error(`link checker timed out on attempt ${ctx.attempt + 1}`);
    }
    return { links_checked: input.draft.split('#').length - 1, broken: 0 };
  });

// Post `text` to `channel`, once. A re-run of this step is refused as a duplicate.
export const publish = fn('publish').run(
  async (ctx: Context, input: { channel: string; release: string; text: string }): Promise<Published> => {
    logExecution(ctx.runId, 'publish', input.channel);
    const sent = sendOnce(idempotencyKey(ctx, input.channel), input);
    return { channel: input.channel, published: sent, duplicate_skipped: !sent };
  },
);

// A day later: draft a "what people are saying" follow-up.
export const draftFollowup = fn('draft_followup').run(
  async (ctx: Context, input: { release: string }): Promise<{ text: string }> => {
    logExecution(ctx.runId, 'draft_followup', input.release);
    const text = await generate(
      ctx,
      'Write a two-sentence follow-up post thanking users for feedback on the release.',
      `Release ${input.release} shipped yesterday.`,
      `Thanks for all the feedback on ${input.release}! Dark mode and the faster cold starts are the clear favourites so far.`,
    );
    return { text };
  },
);

// Summarize how many times each step's code actually ran in this run.
export const buildReport = fn('build_report').run(async (ctx: Context, input: { prCount: number }) => {
  const executions: Record<string, number> = {};
  for (const e of readExecutionLog(ctx.runId)) executions[e.step] = (executions[e.step] ?? 0) + 1;
  return { prs: input.prCount, llm_summaries_run: executions.summarize_pr ?? 0, step_executions: executions };
});
