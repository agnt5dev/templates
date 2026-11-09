/**
 * The `process_expenses` workflow: receipts in, ledger entries and emails out.
 *
 * Kill the worker at any point and restart it: the run picks up where it left
 * off. Finished steps (LLM extractions included) return their checkpoints, the
 * human approval and the payout wait survive the restart, and nothing is
 * posted or emailed twice.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { approved, crashPoint, step } from './demo.js';
import {
  buildReport,
  convertToUsd,
  extractReceipt,
  loadReceipts,
  notifyReimbursements,
  postToLedger,
} from './functions.js';
import type { Expense, PostResult, Receipt } from './functions.js';

// Durable sleeps in this demo are measured in "hours". Set to 3600 for real
// time; the default turns a 48-hour payout window into 48 seconds.
const MS_PER_HOUR = Number(process.env.EXPENSES_SECONDS_PER_HOUR ?? 1) * 1000;

export interface ProcessExpensesInput {
  batch_id?: string;
  approval_limit_usd?: number;
  payout_delay_hours?: number;
  /** Make the FX service fail this many times (retries absorb it). */
  flaky_failures?: number;
  /** Kill the worker once at "receipt_<n>", right after the nth receipt is extracted. */
  crash_at?: string;
}

export const processExpenses = workflow(
  'process_expenses',
  async (ctx: Context, input: ProcessExpensesInput = {}) => {
    const batchId = input.batch_id ?? '2026-10-team-travel';
    const limit = input.approval_limit_usd ?? 500;

    const receipts = await step<Receipt[]>(ctx, 'load_receipts', () => loadReceipts(ctx, { batchId }));

    // 1. One LLM call per receipt, each its own checkpoint. The key ties the
    //    checkpoint to the receipt, not to its position in the loop.
    let expenses: Expense[] = [];
    for (const [i, receipt] of receipts.entries()) {
      expenses.push(
        await step<Expense>(ctx, 'extract_receipt', () => extractReceipt(ctx, { receipt }), receipt.id),
      );
      await crashPoint(ctx, input.crash_at, `receipt_${i + 1}`);
    }

    // 2. A flaky dependency. The function's retry policy absorbs the failures.
    expenses = await step<Expense[]>(ctx, 'convert_to_usd', () =>
      convertToUsd(ctx, { expenses, flakyFailures: input.flaky_failures ?? 0 }),
    );

    const small = expenses.filter((e) => (e.amount_usd ?? 0) <= limit);
    const large = expenses.filter((e) => (e.amount_usd ?? 0) > limit);

    // 3. Post everything under the limit right away, exactly once.
    const autoPosted = await step<PostResult>(
      ctx, 'post_to_ledger', () => postToLedger(ctx, { batchId, expenses: small }), 'auto-approved',
    );

    // 4. A manager signs off on the rest. The run is not in memory while it waits.
    let decision = 'not_needed';
    let approvedPosted: PostResult = { posted: [], duplicates_skipped: [] };
    if (large.length) {
      const lines = large
        .map((e) => `- ${e.employee}: ${e.vendor} $${e.amount_usd?.toFixed(2)} (${e.category})`)
        .join('\n');
      const answer = await ctx.waitForUser(
        `${large.length} expenses are over $${limit}:\n${lines}\n\nApprove them?`,
        {
          inputType: 'approval',
          options: [
            { id: 'approve', label: 'Approve' },
            { id: 'reject', label: 'Reject' },
          ],
        },
      );
      decision = approved(answer) ? 'approve' : 'reject';
      if (decision === 'approve') {
        approvedPosted = await step<PostResult>(
          ctx, 'post_to_ledger', () => postToLedger(ctx, { batchId, expenses: large }), 'manager-approved',
        );
      }
    }
    const reimbursed = decision === 'approve' ? [...small, ...large] : small;

    // 5. Wait out the payout window. Durable: no worker is held while it sleeps.
    await ctx.sleep((input.payout_delay_hours ?? 48) * MS_PER_HOUR, 'payout_window');

    // 6. Tell each employee, once.
    const notified = await step<{ emails_sent: string[] }>(ctx, 'notify_reimbursements', () =>
      notifyReimbursements(ctx, { batchId, expenses: reimbursed }),
    );

    const report = await step(ctx, 'build_report', () => buildReport(ctx, { receiptCount: receipts.length }));
    return {
      batch_id: batchId,
      total_usd: Math.round(expenses.reduce((sum, e) => sum + (e.amount_usd ?? 0), 0) * 100) / 100,
      auto_approved: autoPosted,
      manager_decision: decision,
      manager_approved: approvedPosted,
      notified,
      execution_report: report,
    };
  },
);
