/**
 * Steps for the support triage workflow.
 *
 * Each `fn(...)` is a function the workflow runs as a step. Called through
 * `ctx.step(...)`, its result is checkpointed, so a worker restart skips the
 * steps that already completed — the agent's model calls included.
 */

import { fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { buildSupportAgent } from './agent.js';
import { BUG_WORDS, ORDERS, REFUND_WORDS, URGENT_WORDS } from './data.js';
import type { Order } from './data.js';

export interface Triage {
  category: 'refund' | 'bug' | 'question';
  urgency: 'high' | 'normal';
}

export type OrderLookup = (Order & { found: true }) | { order_id: string; found: false };

export interface Draft {
  reply: string;
  tools_used: string[];
}

// Sort a ticket into refund, bug or question, and flag urgent ones.
export const classifyTicket = fn('classify_ticket').run(
  async (_ctx: Context, input: { message: string }): Promise<Triage> => {
    const text = input.message.toLowerCase();
    const has = (words: string[]) => words.some((word) => text.includes(word));
    const category = has(REFUND_WORDS) ? 'refund' : has(BUG_WORDS) ? 'bug' : 'question';
    return { category, urgency: has(URGENT_WORDS) ? 'high' : 'normal' };
  },
);

// Fetch the order a ticket refers to. Retried, since order systems flake.
export const lookupOrder = fn('lookup_order')
  .retry({ maxAttempts: 3 })
  .backoff({ type: 'exponential' })
  .run(async (_ctx: Context, input: { order_id: string }): Promise<OrderLookup> => {
    const order = ORDERS[input.order_id];
    if (!order) return { order_id: input.order_id, found: false };
    return { ...order, found: true };
  });

// Have the support agent draft a reply. Passing `ctx` makes its model calls durable.
export const draftReply = fn('draft_reply').run(
  async (
    ctx: Context,
    input: { customer: string; category: string; message: string },
  ): Promise<Draft> => {
    const prompt = `Customer: ${input.customer}\nCategory: ${input.category}\nMessage: ${input.message}`;
    const result = await buildSupportAgent().run(prompt, ctx);
    return {
      reply: result.output.trim(),
      tools_used: result.toolCalls.map((call) => call.name),
    };
  },
);
