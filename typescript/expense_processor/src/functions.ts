/**
 * Steps for the expense workflow.
 *
 * Each `fn(...)` is a function the workflow runs inside `ctx.step(...)`: its
 * result is checkpointed, and a replay returns the checkpoint instead of
 * running the code again (see workflows.ts).
 */

import { readFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { Agent, LM, fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { postLedgerEntry, sendEmail } from './accounting.js';
import { idempotencyKey, logExecution, mockMode, readExecutionLog } from './demo.js';

const MODEL = process.env.EXPENSES_MODEL || 'openai/gpt-6-luna';
const RECEIPTS_FILE = new URL('./receipts.json', import.meta.url);

// Fixed rates so the demo is reproducible; a real workflow would call an FX API.
const USD_PER_UNIT: Record<string, number> = { USD: 1.0, EUR: 1.08, GBP: 1.27 };

const EXTRACTION_PROMPT = `You read expense receipts. Extract the vendor name, the
final amount actually paid (after tax and tip), its ISO 4217 currency code, a
category (meals, travel, lodging, equipment, conference, books, other), and the
date in YYYY-MM-DD. Receipts may use European number formats (96,50 means
96.50) and DD/MM/YYYY dates. Reply with only a JSON object with the keys
vendor, amount, currency, category, date.`;

export interface Receipt {
  id: string;
  employee: string;
  text: string;
  mock_extraction: ReceiptFields;
}

export interface ReceiptFields {
  vendor: string;
  amount: number;
  currency: string;
  category: string;
  date: string;
}

export interface Expense extends ReceiptFields {
  receipt_id: string;
  employee: string;
  amount_usd?: number;
}

export interface PostResult {
  posted: string[];
  duplicates_skipped: string[];
}

export const loadReceipts = fn('load_receipts').run(
  async (ctx: Context, input: { batchId: string }): Promise<Receipt[]> => {
    logExecution(ctx.runId, 'load_receipts', input.batchId);
    const receipts = JSON.parse(readFileSync(RECEIPTS_FILE, 'utf8')) as Receipt[];
    ctx.logger.info(`Loaded ${receipts.length} receipts for ${input.batchId}`);
    return receipts;
  },
);

// Read one receipt with an LLM. This is the expensive part of the workflow.
// Each receipt is its own step, so after a crash only the receipts that had
// not finished are re-read.
export const extractReceipt = fn('extract_receipt').run(
  async (ctx: Context, input: { receipt: Receipt }): Promise<Expense> => {
    const { receipt } = input;
    logExecution(ctx.runId, 'extract_receipt', receipt.id);

    let fields: ReceiptFields;
    if (mockMode()) {
      await sleep(Number(process.env.EXPENSES_MOCK_LATENCY_MS ?? 1500));
      fields = receipt.mock_extraction;
    } else {
      const agent = new Agent({
        name: 'receipt_reader',
        model: LM.openai(),
        modelName: MODEL,
        temperature: 1, // gpt-6 accepts only its default temperature
        instructions: EXTRACTION_PROMPT,
      });
      const result = await agent.run(receipt.text, ctx);
      fields = JSON.parse(result.output.trim().replace(/^```(json)?|```$/g, '')) as ReceiptFields;
    }

    ctx.logger.info(`Extracted ${receipt.id}: ${fields.vendor} ${fields.amount.toFixed(2)} ${fields.currency}`);
    return { receipt_id: receipt.id, employee: receipt.employee, ...fields };
  },
);

// Convert every expense to USD. Set `flakyFailures` to make the exchange-rate
// service fail that many times first. The retry policy retries the function
// with exponential backoff; the workflow never sees the failures.
export const convertToUsd = fn('convert_to_usd')
  .retry({ maxAttempts: 4, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential' })
  .run(async (ctx: Context, input: { expenses: Expense[]; flakyFailures: number }): Promise<Expense[]> => {
    logExecution(ctx.runId, 'convert_to_usd', '', ctx.attempt);
    if (ctx.attempt < input.flakyFailures) {
      ctx.logger.warn(`FX service unavailable (attempt ${ctx.attempt + 1}) - will retry`);
      throw new Error(`FX service returned 503 on attempt ${ctx.attempt + 1}`);
    }
    return input.expenses.map((e) => ({
      ...e,
      amount_usd: Math.round(e.amount * (USD_PER_UNIT[e.currency] ?? 1) * 100) / 100,
    }));
  });

// Post expenses to the ledger, each exactly once. If this step runs again (a
// retry, or a worker that died before the result was saved), entries already
// written are refused as duplicates by their idempotency key.
export const postToLedger = fn('post_to_ledger').run(
  async (ctx: Context, input: { batchId: string; expenses: Expense[] }): Promise<PostResult> => {
    logExecution(ctx.runId, 'post_to_ledger', input.batchId);
    const posted: string[] = [];
    const duplicates: string[] = [];
    for (const expense of input.expenses) {
      const entry = { batch_id: input.batchId, ...expense };
      if (postLedgerEntry(idempotencyKey(ctx, expense.receipt_id), entry)) posted.push(expense.receipt_id);
      else duplicates.push(expense.receipt_id);
    }
    if (duplicates.length) ctx.logger.warn(`Skipped ${duplicates.length} already-posted entries: ${duplicates}`);
    return { posted, duplicates_skipped: duplicates };
  },
);

// Email each employee their reimbursement total, once.
export const notifyReimbursements = fn('notify_reimbursements').run(
  async (ctx: Context, input: { batchId: string; expenses: Expense[] }): Promise<{ emails_sent: string[] }> => {
    logExecution(ctx.runId, 'notify_reimbursements', input.batchId);
    const totals = new Map<string, number>();
    for (const e of input.expenses) totals.set(e.employee, (totals.get(e.employee) ?? 0) + (e.amount_usd ?? 0));

    const sent: string[] = [];
    for (const [employee, total] of [...totals].sort()) {
      const email = {
        to: employee,
        subject: `Your expenses for ${input.batchId} have been reimbursed`,
        body: `$${total.toFixed(2)} is on its way to your account.`,
      };
      if (sendEmail(idempotencyKey(ctx, employee), email)) sent.push(employee);
    }
    return { emails_sent: sent };
  },
);

// Summarize how many times each step's code actually ran in this run.
export const buildReport = fn('build_report').run(
  async (ctx: Context, input: { receiptCount: number }) => {
    const executions: Record<string, number> = {};
    for (const e of readExecutionLog(ctx.runId)) executions[e.step] = (executions[e.step] ?? 0) + 1;
    return {
      receipts: input.receiptCount,
      llm_extractions_run: executions.extract_receipt ?? 0,
      step_executions: executions,
    };
  },
);
