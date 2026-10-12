/**
 * Functions: durable steps, and tools an MCP client can call directly.
 *
 * Replace the in-memory ORDERS with your own data source. Every `fn(...)` is
 * an AGNT5 component: run it with `agnt5 run`, call it from a workflow
 * through `ctx.step(...)`, or publish it on the MCP server (see server.ts).
 * The input schema is what MCP clients see as the tool's arguments.
 */

import { fn } from '@agnt5/sdk';
import type { Context, JSONSchema } from '@agnt5/sdk';

export interface Order {
  id: string;
  customer: string;
  item: string;
  total: number;
  status: string;
}

export interface Refund {
  refundId: string;
  orderId: string;
  amount: number;
  reason: string;
}

// Sample data so the template runs without any setup.
const ORDERS: Record<string, Order> = {
  'o-1001': { id: 'o-1001', customer: 'Ada', item: 'Mechanical keyboard', total: 129, status: 'delivered' },
  'o-1002': { id: 'o-1002', customer: 'Grace', item: 'USB-C dock', total: 89.5, status: 'shipped' },
  'o-1003': { id: 'o-1003', customer: 'Linus', item: '27-inch monitor', total: 349, status: 'processing' },
};

export const ORDER_IDS = Object.keys(ORDERS);

/** One order, or an error naming the sample ids. */
export function findOrder(orderId: string): Order {
  const order = ORDERS[orderId.trim().toLowerCase()];
  if (!order) {
    throw new Error(`No order "${orderId}". Try o-1001, o-1002 or o-1003.`);
  }
  return order;
}

const orderIdSchema: JSONSchema = {
  type: 'object',
  properties: {
    orderId: { type: 'string', description: 'The order id, for example o-1001' },
  },
  required: ['orderId'],
};

export const lookupOrder = fn<{ orderId: string }, Order>('lookup_order')
  .description('Look up an order by its id (for example o-1001).')
  .inputSchema(orderIdSchema)
  .run(async (ctx: Context, input: { orderId: string }): Promise<Order> => {
    ctx.logger.info(`Looking up order ${input.orderId}`);
    return findOrder(input.orderId);
  });

export interface RefundInput {
  orderId: string;
  amount: number;
  reason: string;
  idempotencyKey: string;
}

/**
 * Issue a refund. A stand-in for your payment provider's API.
 *
 * Send idempotencyKey with the provider call (Stripe's Idempotency-Key
 * header, for example). A step runs at least once: if the worker dies after
 * the provider refunded but before the result was checkpointed, the step runs
 * again, and the key is what makes the provider answer the retry with the
 * first refund instead of issuing a second one.
 */
export const issueRefund = fn<RefundInput, Refund>('issue_refund')
  .description("Issue a refund. A stand-in for your payment provider's API.")
  .run(async (ctx: Context, input: RefundInput): Promise<Refund> => {
    ctx.logger.info(`Refunding ${input.amount} on ${input.orderId}: ${input.reason} (key ${input.idempotencyKey})`);
    return { refundId: `rf_${input.idempotencyKey}`, orderId: input.orderId, amount: input.amount, reason: input.reason };
  });

export interface AuditCheck {
  orderId: string;
  check: string;
  ok: boolean;
}

/**
 * Check an order's payment, shipment or refunds, one at a time.
 *
 * A stand-in for the systems an audit reads: here only an order still
 * processing fails its shipment check.
 */
export const auditOrder = fn<{ orderId: string; check: string }, AuditCheck>('audit_order')
  .description("Check an order's payment, shipment or refunds, one at a time.")
  .run(async (ctx: Context, input: { orderId: string; check: string }): Promise<AuditCheck> => {
    ctx.logger.info(`Checking ${input.check} on ${input.orderId}`);
    const order = findOrder(input.orderId);
    const ok = !(input.check === 'shipment' && order.status === 'processing');
    return { orderId: order.id, check: input.check, ok };
  });
