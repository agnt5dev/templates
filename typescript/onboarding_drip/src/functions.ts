/**
 * Steps for the onboarding workflow.
 *
 * Each `fn(...)` is a function the workflow runs inside `ctx.step(...)`: its
 * result is checkpointed, and a replay returns the checkpoint instead of
 * running the code again (see workflows.ts).
 */

import { setTimeout as sleep } from 'node:timers/promises';
import { Agent, LM, fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { idempotencyKey, logExecution, mockMode, readExecutionLog } from './demo.js';
import { sendOnce } from './outbox.js';

const MODEL = process.env.ONBOARDING_MODEL || 'openai/gpt-6-luna';

export interface User {
  name: string;
  email: string;
  company: string;
  role: string;
}

export interface Email {
  kind: string;
  subject: string;
  body: string;
}

export interface SendResult {
  kind: string;
  sent: boolean;
  duplicate_skipped?: boolean;
  reason?: string;
}

export interface Activity {
  logins: number;
  features_used: string[];
  teammates_invited: number;
}

// Simulated product analytics, keyed by email.
const ACTIVITY: Record<string, Activity> = {
  'dana@northwind.io': { logins: 2, features_used: ['dashboards'], teammates_invited: 0 },
};

async function generate(ctx: Context, instructions: string, prompt: string, mock: string): Promise<string> {
  if (mockMode()) {
    await sleep(Number(process.env.ONBOARDING_MOCK_LATENCY_MS ?? 1500));
    return mock;
  }
  const agent = new Agent({
    name: 'onboarding_writer',
    model: LM.openai(),
    modelName: MODEL,
    temperature: 1, // gpt-6 accepts only its default temperature
    instructions,
  });
  return (await agent.run(prompt, ctx)).output.trim();
}

// Write a short brief on the new user's company. One LLM call.
export const researchCompany = fn('research_company').run(
  async (ctx: Context, input: { user: User }): Promise<{ brief: string }> => {
    const { user } = input;
    logExecution(ctx.runId, 'research_company', user.company);
    const brief = await generate(
      ctx,
      'In two sentences, describe what this company likely does and why it might use an analytics product.',
      `Company: ${user.company}\nSignup role: ${user.role}`,
      `${user.company} is a mid-sized logistics company. As ${user.role}, ${user.name} likely wants ` +
        'shipment dashboards their ops team can share.',
    );
    return { brief };
  },
);

// Write one personalised email (welcome, follow-up, or offer). One LLM call.
export const writeEmail = fn('write_email').run(
  async (ctx: Context, input: { user: User; kind: string; context: string }): Promise<Email> => {
    const { user, kind } = input;
    logExecution(ctx.runId, 'write_email', kind);
    const mocks: Record<string, string> = {
      welcome: `Hi ${user.name}, welcome aboard! Teams like yours at ${user.company} usually start ` +
        "with a shared shipments dashboard - here's a 3-minute guide.",
      followup: `Hi ${user.name}, you've built your first dashboard. Invite your ops team so they ` +
        'see the same numbers you do.',
      offer: `Hi ${user.name}, your trial ends soon. Upgrade this week and get 20% off the Team plan.`,
    };
    const body = await generate(
      ctx,
      `Write a short, warm ${kind} email for a new user of an analytics product. Under 60 words.`,
      `User: ${user.name}, ${user.role} at ${user.company}\nContext: ${input.context}`,
      mocks[kind],
    );
    return { kind, subject: `[${kind}] ${user.company} x Acme Analytics`, body };
  },
);

// Send one email through a flaky provider, exactly once. The provider fails
// `flakyFailures` times first; the retry policy absorbs it. The idempotency
// key stays the same on every retry, so a send that reached the provider
// before a failure is never sent again.
export const sendEmail = fn('send_email')
  .retry({ maxAttempts: 4, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential' })
  .run(async (ctx: Context, input: { to: string; email: Email; flakyFailures?: number }): Promise<SendResult> => {
    const { email } = input;
    logExecution(ctx.runId, 'send_email', email.kind, ctx.attempt);
    if (ctx.attempt < (input.flakyFailures ?? 0)) {
      ctx.logger.warn(`Email provider returned 503 (attempt ${ctx.attempt + 1}) - will retry`);
      throw new Error(`email provider returned 503 on attempt ${ctx.attempt + 1}`);
    }
    const sent = sendOnce(idempotencyKey(ctx, email.kind), { to: input.to, ...email });
    return { kind: email.kind, sent, duplicate_skipped: !sent };
  });

// Read the user's product activity since signup (simulated analytics API).
export const checkActivity = fn('check_activity').run(
  async (ctx: Context, input: { email: string }): Promise<Activity> => {
    logExecution(ctx.runId, 'check_activity', input.email);
    return ACTIVITY[input.email] ?? { logins: 0, features_used: [], teammates_invited: 0 };
  },
);

// Summarize how many times each step's code actually ran in this run.
export const buildReport = fn('build_report').run(async (ctx: Context) => {
  const executions: Record<string, number> = {};
  for (const e of readExecutionLog(ctx.runId)) executions[e.step] = (executions[e.step] ?? 0) + 1;
  return {
    llm_calls_run: (executions.research_company ?? 0) + (executions.write_email ?? 0),
    step_executions: executions,
  };
});
