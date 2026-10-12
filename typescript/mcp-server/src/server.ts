/**
 * The MCP server: which components MCP clients (Claude, ChatGPT, Cursor, ...)
 * see as tools.
 *
 * A deploy serves it at https://api.agnt5.com/mcp/{project}/{env}/support, and
 * `agnt5 dev` at a dev URL only you can sign in to. Clients sign in with
 * AGNT5; every tool call runs as a durable AGNT5 run you can open in Studio.
 *
 * The worker publishes a server only when its module is imported, so app.ts
 * imports this one. The server's name is part of its URL (lowercase letters,
 * digits, '-' and '_') and matches mcp.servers in agnt5.yaml.
 */

import { MCPServer } from '@agnt5/sdk';

import { supportAgent } from './agents.js';
import { lookupOrder } from './functions.js';
import { auditOrders, refundOrder } from './workflows.js';

export const support = new MCPServer('support', {
  title: 'Order support',
  instructions:
    'Tools for customer orders. Use lookup_order to read an order, refund_order to ' +
    'refund one in full, ask_support for questions that need judgement, and ' +
    'audit_orders to audit every order. audit_orders takes about 10 minutes and ' +
    'hands back a run at once: follow it with get_run.',
});

// A view: your own MCP App UI, one self-contained HTML file built from ui/
// (cd ui && npm install && npm run build). Clients that render MCP Apps show
// it for lookup_order's results; the rest read the result as text.
export const orderView = support.addView('order', {
  path: new URL('../views/order.html', import.meta.url),
});

// A function answers synchronously, here shown in the order view.
support.addFunction('lookup_order', lookupOrder, {
  annotations: { readOnlyHint: true },
  view: orderView,
});

// A workflow waits up to the call budget, then hands back a run handle.
support.addWorkflow('refund_order', refundOrder, {
  annotations: { destructiveHint: true, idempotentHint: false },
});

// A long workflow hands back a run handle at once (mode: 'background'); the
// client follows its steps and progress while it runs.
support.addWorkflow('audit_orders', auditOrders, {
  mode: 'background',
  annotations: { readOnlyHint: true },
});

// An agent is a tool that takes a message. The worker serves it; no
// registerAgents call is needed.
support.addAgent('ask_support', supportAgent, { title: 'Ask the support agent' });

// In clients that render MCP Apps (ChatGPT, Claude, Cursor, VS Code), calls to
// auto and background tools without a view of their own, like refund_order,
// audit_orders and ask_support here, show the built-in AGNT5 run card: live
// status, steps, progress, output and Cancel run. Pass { view: null } to
// addFunction / addWorkflow / addAgent to turn it off for a tool.
