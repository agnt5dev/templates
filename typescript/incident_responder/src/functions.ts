/**
 * Steps for the incident response workflow.
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

const MODEL = process.env.INCIDENT_MODEL || 'openai/gpt-6-luna';

export type Source = 'logs' | 'metrics' | 'deploys';

export interface Alert {
  id: string;
  title: string;
  service: string;
}

export interface Finding {
  source: Source;
  finding: string;
}

export interface Fix {
  action: string;
  service: string;
  to_version: string;
  rationale: string;
}

export interface Health {
  service: string;
  p99_ms: number;
  error_rate: number;
  recovered: boolean;
}

// Simulated telemetry for the sample incident.
const EVIDENCE: Record<Source, string> = {
  logs: '14:02:11 checkout-api ERROR pool exhausted: 50/50 connections in use (x1,204)\n' +
    '14:02:13 checkout-api WARN request timeout after 30s (x388)',
  metrics: 'checkout-api p99 latency 180ms -> 30.4s at 14:01; error rate 0.2% -> 31%; db connections 50/50',
  deploys: '14:00:05 checkout-api v2.31.0 rolled out (changed: db pool size 200 -> 50, retry middleware)',
};
const MOCK_FINDINGS: Record<Source, string> = {
  logs: 'Connection pool exhausted on checkout-api since 14:02; requests time out waiting for a connection.',
  metrics: 'Latency and errors jumped at 14:01, right as DB connections hit the 50 cap.',
  deploys: 'v2.31.0 shipped at 14:00 and cut the DB pool from 200 to 50 connections.',
};

async function generate(ctx: Context, instructions: string, prompt: string, mock: string): Promise<string> {
  if (mockMode()) {
    await sleep(Number(process.env.INCIDENT_MOCK_LATENCY_MS ?? 1500));
    return mock;
  }
  const agent = new Agent({
    name: 'incident_analyst',
    model: LM.openai(),
    modelName: MODEL,
    temperature: 1, // gpt-6 accepts only its default temperature
    instructions,
  });
  return (await agent.run(prompt, ctx)).output.trim();
}

// Investigate one evidence source (logs, metrics, or deploys) with an LLM.
// The metrics backend fails `flakyFailures` times first; retries absorb it.
export const analyze = fn('analyze')
  .retry({ maxAttempts: 4, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential' })
  .run(async (ctx: Context, input: { source: Source; alert: Alert; flakyFailures: number }): Promise<Finding> => {
    const { source, alert } = input;
    logExecution(ctx.runId, 'analyze', source, ctx.attempt);
    if (source === 'metrics' && ctx.attempt < input.flakyFailures) {
      ctx.logger.warn(`Metrics backend timed out (attempt ${ctx.attempt + 1}) - will retry`);
      throw new Error(`metrics query timed out on attempt ${ctx.attempt + 1}`);
    }
    const finding = await generate(
      ctx,
      `You are on call. In one sentence, what do these ${source} say about the alert?`,
      `Alert: ${alert.title}\n\n${EVIDENCE[source]}`,
      MOCK_FINDINGS[source],
    );
    return { source, finding };
  });

// Name the likely cause and propose one remediation.
export const proposeFix = fn('propose_fix').run(
  async (ctx: Context, input: { alert: Alert; findings: Finding[] }): Promise<Fix> => {
    const { alert } = input;
    logExecution(ctx.runId, 'propose_fix', alert.id);
    const notes = input.findings.map((f) => `- ${f.source}: ${f.finding}`).join('\n');
    const rationale = await generate(
      ctx,
      'From these findings, state the likely root cause and the safest fix in two sentences.',
      `Alert: ${alert.title}\n${notes}`,
      'v2.31.0 cut the DB pool from 200 to 50, so checkout-api runs out of connections under load. ' +
        'Roll back checkout-api to v2.30.4.',
    );
    return { action: 'rollback', service: alert.service, to_version: 'v2.30.4', rationale };
  },
);

// Roll the service back. Must never run twice, so it carries an idempotency key.
export const applyRollback = fn('apply_rollback').run(async (ctx: Context, input: { fix: Fix; crashAt?: string }) => {
  logExecution(ctx.runId, 'apply_rollback', input.fix.service);
  const applied = sendOnce(idempotencyKey(ctx), { type: 'rollback', ...input.fix });
  // Demo: die after the rollback is applied, before the step completes.
  if (input.crashAt === 'during_rollback' && applied) {
    console.log(`💥 Simulated crash during the rollback (run ${ctx.runId}).`);
    process.exit(1);
  }
  return { rollback_applied: applied, duplicate_skipped: !applied };
});

// Check the service's health after the fix settles (simulated).
export const verifyRecovery = fn('verify_recovery').run(
  async (ctx: Context, input: { service: string }): Promise<Health> => {
    logExecution(ctx.runId, 'verify_recovery', input.service);
    return { service: input.service, p99_ms: 175, error_rate: 0.002, recovered: true };
  },
);

// Write the postmortem with an LLM and post it to the incident channel, once.
export const postPostmortem = fn('post_postmortem').run(
  async (ctx: Context, input: { alert: Alert; findings: Finding[]; fix: Fix; health: Health }) => {
    const { alert, fix } = input;
    logExecution(ctx.runId, 'post_postmortem', alert.id);
    const text = await generate(
      ctx,
      'Write a 4-line incident postmortem: impact, cause, fix, follow-up.',
      `Alert: ${alert.title}\nFindings: ${JSON.stringify(input.findings)}\nFix: ${JSON.stringify(fix)}\n` +
        `Health after fix: ${JSON.stringify(input.health)}`,
      `Impact: checkout errors up to 31% for ~20 min. Cause: ${fix.rationale} ` +
        `Fix: rolled back to ${fix.to_version}. Follow-up: load-test pool size changes before rollout.`,
    );
    const posted = sendOnce(idempotencyKey(ctx), { type: 'postmortem', incident: alert.id, text });
    return { postmortem_posted: posted, duplicate_skipped: !posted, text };
  },
);

// Summarize how many times each step's code actually ran in this run.
export const buildReport = fn('build_report').run(async (ctx: Context) => {
  const executions: Record<string, number> = {};
  for (const e of readExecutionLog(ctx.runId)) executions[e.step] = (executions[e.step] ?? 0) + 1;
  return { rollbacks_run: executions.apply_rollback ?? 0, step_executions: executions };
});
