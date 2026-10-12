/**
 * Agents: an LLM with tools. Published on the MCP server, an agent becomes a
 * tool that takes a message (and optionally a session to continue).
 *
 * The agent needs OPENAI_API_KEY: in .env for a local worker, and as a project
 * secret for a deployment (agnt5 secrets set --name OPENAI_API_KEY --type api_key).
 * The function and the workflow need nothing.
 */

import { Agent, LM, tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { findOrder } from './functions.js';
import type { Order } from './functions.js';

export const getOrder = tool(
  'get_order',
  {
    description: 'Look up an order by its id (for example o-1001).',
    inputSchema: {
      type: 'object',
      properties: { orderId: { type: 'string', description: 'The order id' } },
      required: ['orderId'],
    },
  },
  async (_ctx: Context, args: { orderId: string }): Promise<Order> => findOrder(args.orderId),
);

export const supportAgent = new Agent({
  name: 'support_agent',
  model: LM.openai(),
  modelName: 'openai/gpt-6-luna',
  temperature: 1, // gpt-6 accepts only its default temperature; the SDK would send 0.7
  instructions:
    'You answer questions about customer orders. Look orders up with get_order before ' +
    'answering, and say plainly when an order does not exist. You cannot issue refunds: ' +
    'point the user to the refund_order tool.',
  tools: [getOrder],
});
