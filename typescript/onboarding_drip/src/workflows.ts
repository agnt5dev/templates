/**
 * The `onboard_customer` workflow: a multi-day email sequence for one new signup.
 *
 * The run lives for days (seconds, in the demo) and spends almost all of that
 * time asleep. A durable sleep doesn't hold a worker, so deploys and crashes
 * in between don't matter: the run wakes on schedule and nothing is sent twice.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { approved, crashPoint, step } from './demo.js';
import { buildReport, checkActivity, researchCompany, sendEmail, writeEmail } from './functions.js';
import type { Activity, Email, SendResult, User } from './functions.js';

// Durable sleeps in this demo are measured in "hours". Set to 3600 for real
// time; the default turns the 3-day wait into 72 seconds.
const MS_PER_HOUR = Number(process.env.ONBOARDING_SECONDS_PER_HOUR ?? 1) * 1000;

const DEFAULT_USER: User = {
  name: 'Dana',
  email: 'dana@northwind.io',
  company: 'Northwind Logistics',
  role: 'Head of Ops',
};

export interface OnboardCustomerInput {
  user?: User;
  wait_days?: number;
  /** Make the email provider fail this many times on the welcome email. */
  flaky_failures?: number;
  /** Kill the worker once at "after_research", "after_welcome", or "after_wait". */
  crash_at?: string;
}

export const onboardCustomer = workflow(
  'onboard_customer',
  async (ctx: Context, input: OnboardCustomerInput = {}) => {
    const user = input.user ?? DEFAULT_USER;

    const { brief } = await step<{ brief: string }>(ctx, 'research_company', () => researchCompany(ctx, { user }));
    await crashPoint(ctx, input.crash_at, 'after_research');

    const welcome = await step<Email>(
      ctx, 'write_email', () => writeEmail(ctx, { user, kind: 'welcome', context: brief }), 'welcome',
    );
    const welcomeSent = await step<SendResult>(
      ctx, 'send_email',
      () => sendEmail(ctx, { to: user.email, email: welcome, flakyFailures: input.flaky_failures ?? 0 }),
      'welcome',
    );
    await crashPoint(ctx, input.crash_at, 'after_welcome');

    // Wait three days. Durable: the platform holds the timer, not a worker.
    await ctx.sleep((input.wait_days ?? 3) * 24 * MS_PER_HOUR, 'wait_after_welcome');
    await crashPoint(ctx, input.crash_at, 'after_wait');

    const activity = await step<Activity>(ctx, 'check_activity', () => checkActivity(ctx, { email: user.email }));
    const context = JSON.stringify(activity);
    const followup = await step<Email>(
      ctx, 'write_email', () => writeEmail(ctx, { user, kind: 'followup', context }), 'followup',
    );
    const followupSent = await step<SendResult>(
      ctx, 'send_email', () => sendEmail(ctx, { to: user.email, email: followup }), 'followup',
    );

    // A sales rep signs off before a discount goes out.
    const offer = await step<Email>(
      ctx, 'write_email', () => writeEmail(ctx, { user, kind: 'offer', context }), 'offer',
    );
    const answer = await ctx.waitForUser(`Send this upgrade offer to ${user.email}?\n\n${offer.body}`, {
      inputType: 'approval',
      options: [
        { id: 'approve', label: 'Send offer' },
        { id: 'reject', label: "Don't send" },
      ],
    });
    let offerSent: SendResult = { kind: 'offer', sent: false, reason: 'rejected by sales' };
    if (approved(answer)) {
      offerSent = await step<SendResult>(
        ctx, 'send_email', () => sendEmail(ctx, { to: user.email, email: offer }), 'offer',
      );
    }

    const report = await step(ctx, 'build_report', () => buildReport(ctx, {}));
    return { user: user.email, activity, emails: [welcomeSent, followupSent, offerSent], execution_report: report };
  },
);
