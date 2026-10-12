/**
 * Workflows: multi-step work that survives crashes and restarts.
 *
 * Each `ctx.step(...)` checkpoints its result: if the worker restarts after
 * the order was looked up, the run resumes at the refund instead of starting
 * over. A step whose result was not checkpointed yet can still run again, so
 * the refund carries an idempotency key its provider dedupes on (see
 * issueRefund). Published on the MCP server, a call waits for the result up
 * to the server's call budget, then hands the client a run handle it can
 * follow with the built-in get_run tool.
 *
 * auditOrders is the long one: about 10 minutes of steps and durable sleeps,
 * reporting progress as it goes, to follow in the run card or with get_run.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { ORDER_IDS, auditOrder, issueRefund, lookupOrder } from './functions.js';
import type { AuditCheck, Order, Refund } from './functions.js';

export interface RefundResult {
  order: string;
  customer: string;
  refunded: number;
  refundId: string;
}

/**
 * Run `fn` as a checkpointed step. On replay the checkpoint can come back as
 * its JSON text rather than the value, so a string is decoded before use.
 */
async function step<T>(ctx: Context, name: string, fn: () => T | Promise<T>): Promise<T> {
  const result = await ctx.step<T | string>(name, fn);
  return typeof result === 'string' ? (JSON.parse(result) as T) : result;
}

/**
 * The key of an order's full refund: one per order, whichever run, retry or
 * repeated tool call asks for it.
 */
export function refundIdempotencyKey(orderId: string): string {
  return `refund-${orderId}`;
}

export const refundOrder = workflow(
  'refund_order',
  async (ctx: Context, input: { orderId: string; reason?: string }): Promise<RefundResult> => {
    const reason = input.reason ?? 'customer request';
    const order = await step<Order>(ctx, 'lookup_order', () => lookupOrder(ctx, { orderId: input.orderId }));
    const refund = await step<Refund>(ctx, 'issue_refund', () =>
      issueRefund(ctx, { orderId: order.id, amount: order.total, reason, idempotencyKey: refundIdempotencyKey(order.id) }),
    );
    return { order: order.id, customer: order.customer, refunded: refund.amount, refundId: refund.refundId };
  },
  {
    description: 'Refund an order in full: look it up, then issue the refund.',
    inputSchema: {
      type: 'object',
      properties: {
        orderId: { type: 'string', description: 'The order id, for example o-1002' },
        reason: { type: 'string', description: 'Why the order is refunded' },
      },
      required: ['orderId'],
    },
  },
);

// What an audit checks on each order: one step per order and check.
const AUDIT_CHECKS = ['payment', 'shipment', 'refunds'];

export interface AuditResult {
  orders: number;
  checks: number;
  flagged: string[];
  minutes: number;
}

/** How long an audit takes: the minutes asked for, held to 1 to 30. */
export function auditMinutes(minutes: number): number {
  return Math.min(Math.max(minutes, 1), 30);
}

export const auditOrders = workflow(
  'audit_orders',
  async (ctx: Context, input: { minutes?: number }): Promise<AuditResult> => {
    const minutes = auditMinutes(input.minutes ?? 10);
    const checks = ORDER_IDS.flatMap((orderId) => AUDIT_CHECKS.map((check) => ({ orderId, check })));
    const pauseMs = Math.round((minutes * 60_000) / checks.length);
    const flagged: string[] = [];
    for (const [done, { orderId, check }] of checks.entries()) {
      ctx.progress(done, { total: checks.length, message: `Checking ${check} on ${orderId}` });
      const result = await step<AuditCheck>(ctx, `audit_${orderId}_${check}`, () => auditOrder(ctx, { orderId, check }));
      if (!result.ok) {
        flagged.push(`${orderId} ${check}`);
      }
      // A durable timer, unlike setTimeout: after a restart the run waits
      // out what is left of it instead of starting over.
      await ctx.sleep(pauseMs, `pause-${orderId}-${check}`);
    }
    ctx.progress(checks.length, { total: checks.length, message: `Audited ${ORDER_IDS.length} orders` });
    return { orders: ORDER_IDS.length, checks: checks.length, flagged, minutes };
  },
  {
    description: "Audit every order's payment, shipment and refunds over about `minutes` (1 to 30).",
    inputSchema: {
      type: 'object',
      properties: {
        minutes: {
          type: 'integer',
          default: 10,
          description: 'About how long the audit runs, in minutes (held to 1 to 30)',
        },
      },
    },
  },
);
