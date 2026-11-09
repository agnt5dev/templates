/**
 * The `respond_to_incident` workflow: alert in, investigated and fixed incident out.
 *
 * The dangerous step is the rollback. It sits behind a human approval and
 * carries an idempotency key, so a crash or retry can never roll back twice.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { approved, crashPoint, step } from './demo.js';
import {
  analyze,
  applyRollback,
  buildReport,
  postPostmortem,
  proposeFix,
  verifyRecovery,
} from './functions.js';
import type { Alert, Finding, Fix, Health, Source } from './functions.js';

// Durable sleeps in this demo are measured in "minutes". Set to 60 for real
// time; the default turns the 10-minute settle time into 30 seconds.
const MS_PER_MINUTE = Number(process.env.INCIDENT_SECONDS_PER_MINUTE ?? 3) * 1000;

const DEFAULT_ALERT: Alert = {
  id: 'INC-4471',
  title: 'checkout-api error rate above 25% for 5 minutes',
  service: 'checkout-api',
};

export interface RespondToIncidentInput {
  alert?: Alert;
  settle_minutes?: number;
  /** Make the metrics backend fail this many times (retries absorb it). */
  flaky_failures?: number;
  /** Kill the worker once at "after_analysis", "after_rollback", or "during_rollback" (inside the step). */
  crash_at?: string;
}

export const respondToIncident = workflow(
  'respond_to_incident',
  async (ctx: Context, input: RespondToIncidentInput = {}) => {
    const alert = input.alert ?? DEFAULT_ALERT;
    const sources: Source[] = ['logs', 'metrics', 'deploys'];

    // 1. Three LLM investigations in parallel, each its own keyed checkpoint.
    const findings = await Promise.all(
      sources.map((source) =>
        step<Finding>(
          ctx, 'analyze', () => analyze(ctx, { source, alert, flakyFailures: input.flaky_failures ?? 0 }), source,
        ),
      ),
    );
    await crashPoint(ctx, input.crash_at, 'after_analysis');

    const fix = await step<Fix>(ctx, 'propose_fix', () => proposeFix(ctx, { alert, findings }));

    // 2. On call approves the rollback. The run is not in memory while it waits.
    const answer = await ctx.waitForUser(
      `${alert.id}: roll back ${fix.service} to ${fix.to_version}?\n\n${fix.rationale}`,
      {
        inputType: 'approval',
        options: [
          { id: 'approve', label: 'Roll back' },
          { id: 'reject', label: "Don't roll back" },
        ],
      },
    );
    if (!approved(answer)) {
      return { incident: alert.id, rollback: 'rejected by on call', findings };
    }

    // 3. The risky action, exactly once.
    const rollback = await step(ctx, 'apply_rollback', () => applyRollback(ctx, { fix, crashAt: input.crash_at }));
    await crashPoint(ctx, input.crash_at, 'after_rollback');

    // 4. Let the system settle. Durable: no worker is held while it waits.
    await ctx.sleep((input.settle_minutes ?? 10) * MS_PER_MINUTE, 'settle_after_rollback');

    const health = await step<Health>(ctx, 'verify_recovery', () => verifyRecovery(ctx, { service: fix.service }));
    const postmortem = await step(ctx, 'post_postmortem', () =>
      postPostmortem(ctx, { alert, findings, fix, health }),
    );

    const report = await step(ctx, 'build_report', () => buildReport(ctx, {}));
    return { incident: alert.id, fix, rollback, health, postmortem, execution_report: report };
  },
);
