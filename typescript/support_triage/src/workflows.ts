/**
 * The `triage_ticket` workflow.
 *
 *     triage_ticket (workflow)
 *     ├─ classify_ticket
 *     ├─ lookup_order          (only when the ticket names an order)
 *     ├─ waitForUser           (only for refunds above APPROVAL_THRESHOLD_USD)
 *     └─ draft_reply           (support agent → get_policy tool)
 *
 * Every `ctx.step(...)` is a checkpoint. While the workflow waits for approval
 * it is not in process memory; it resumes from the checkpoints, possibly on
 * another host, when the reviewer answers.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { APPROVAL_THRESHOLD_USD } from './data.js';
import { classifyTicket, draftReply, lookupOrder } from './functions.js';
import type { Draft, OrderLookup, Triage } from './functions.js';

export interface Ticket {
  ticket_id: string;
  customer: string;
  message: string;
  order_id?: string | null;
}

/**
 * Run `fn` as a checkpointed step and return its result. On replay the
 * checkpoint can come back as its JSON text rather than the value, so a string
 * is decoded before use. Every step here returns an object, never a string, so
 * the decode can't misread a real result.
 */
async function step<T>(ctx: Context, name: string, fn: () => T | Promise<T>): Promise<T> {
  const result = await ctx.step<T | string>(name, fn);
  return typeof result === 'string' ? (JSON.parse(result) as T) : result;
}

export const triageTicket = workflow(
  'triage_ticket',
  async (ctx: Context, input: Ticket) => {
    const { ticket_id, customer, message } = input;
    await ctx.set('status', 'classifying');
    const triage = await step<Triage>(ctx, 'classify_ticket', () => classifyTicket(ctx, { message }));

    let order: OrderLookup | null = null;
    if (input.order_id) {
      const order_id = input.order_id;
      order = await step<OrderLookup>(ctx, 'lookup_order', () => lookupOrder(ctx, { order_id }));
    }

    let decision = 'not_needed';
    if (triage.category === 'refund' && order?.found && order.amount_usd > APPROVAL_THRESHOLD_USD) {
      await ctx.set('status', 'awaiting_approval');
      const answer = await ctx.waitForUser(
        `Approve a $${order.amount_usd} refund for ${order.order_id} (${customer})?`,
        {
          inputType: 'approval',
          options: [
            { id: 'approve', label: 'Approve' },
            { id: 'reject', label: 'Reject' },
          ],
        },
      );
      decision = answer === 'approve' ? 'approved' : 'rejected';
    }

    await ctx.set('status', 'drafting');
    const draft = await step<Draft>(ctx, 'draft_reply', () =>
      draftReply(ctx, { customer, category: triage.category, message }),
    );

    await ctx.set('status', 'done');
    return {
      ticket_id,
      category: triage.category,
      urgency: triage.urgency,
      order,
      refund_decision: decision,
      reply: draft.reply,
      tools_used: draft.tools_used,
    };
  },
  {
    description: 'Classify a ticket, check its order, get approval for large refunds, draft a reply.',
    // TypeScript types are erased at runtime, so Studio's input form needs a schema.
    inputSchema: {
      type: 'object',
      properties: {
        ticket_id: { type: 'string' },
        customer: { type: 'string' },
        message: { type: 'string' },
        order_id: { type: 'string' },
      },
      required: ['ticket_id', 'customer', 'message'],
    },
  },
);
