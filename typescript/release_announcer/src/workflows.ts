/**
 * The `announce_release` workflow: merged PRs in, an announcement and a follow-up out.
 *
 * Kill the worker at any point and restart it: finished steps (the PR
 * summaries included) return their checkpoints, the approval and the one-day
 * wait survive the restart, and nothing is posted twice.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { approved, crashPoint, step } from './demo.js';
import {
  buildReport,
  checkLinks,
  draftAnnouncement,
  draftFollowup,
  loadPrs,
  publish,
  summarizePr,
} from './functions.js';
import type { PrSummary, Published, PullRequest } from './functions.js';

// Durable sleeps in this demo are measured in "hours". Set to 3600 for real
// time; the default turns the 24-hour follow-up delay into 24 seconds.
const MS_PER_HOUR = Number(process.env.RELEASE_SECONDS_PER_HOUR ?? 1) * 1000;

export interface AnnounceReleaseInput {
  release?: string;
  followup_after_hours?: number;
  /** Make the link checker fail this many times (retries absorb it). */
  flaky_failures?: number;
  /** Kill the worker once at "after_summaries" or "after_draft". */
  crash_at?: string;
}

export const announceRelease = workflow(
  'announce_release',
  async (ctx: Context, input: AnnounceReleaseInput = {}) => {
    const release = input.release ?? 'v1.4.0';
    const prs = await step<PullRequest[]>(ctx, 'load_prs', () => loadPrs(ctx, { release }));

    // 1. One LLM call per PR, all in parallel. Each is its own checkpoint, keyed
    //    by PR number so a replay matches results to PRs, not to their order.
    const summaries = await Promise.all(
      prs.map((pr) => step<PrSummary>(ctx, 'summarize_pr', () => summarizePr(ctx, { pr }), `pr-${pr.number}`)),
    );
    await crashPoint(ctx, input.crash_at, 'after_summaries');

    const draft = (await step<{ text: string }>(ctx, 'draft_announcement', () =>
      draftAnnouncement(ctx, { release, summaries }),
    )).text;
    await crashPoint(ctx, input.crash_at, 'after_draft');

    // 2. A flaky dependency. The function's retry policy absorbs the failures.
    const links = await step(ctx, 'check_links', () =>
      checkLinks(ctx, { draft, flakyFailures: input.flaky_failures ?? 0 }),
    );

    // 3. A maintainer signs off. The run is not in memory while it waits.
    const answer = await ctx.waitForUser(`Publish the ${release} announcement?\n\n${draft}`, {
      inputType: 'approval',
      options: [
        { id: 'approve', label: 'Publish' },
        { id: 'reject', label: 'Reject' },
      ],
    });
    if (!approved(answer)) {
      return { release, published: false, reason: 'rejected by maintainer' };
    }

    // 4. Post it, exactly once.
    const announcement = await step<Published>(
      ctx, 'publish', () => publish(ctx, { channel: 'changelog', release, text: draft }), 'changelog',
    );

    // 5. Wait a day. Durable: no worker is held while it sleeps.
    await ctx.sleep((input.followup_after_hours ?? 24) * MS_PER_HOUR, 'followup_delay');

    const followupText = (await step<{ text: string }>(ctx, 'draft_followup', () =>
      draftFollowup(ctx, { release }),
    )).text;
    const followup = await step<Published>(
      ctx, 'publish', () => publish(ctx, { channel: 'community', release, text: followupText }), 'followup',
    );

    const report = await step(ctx, 'build_report', () => buildReport(ctx, { prCount: prs.length }));
    return { release, links, announcement, followup, execution_report: report };
  },
);
