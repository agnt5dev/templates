/**
 * The server publishes one tool per component, each naming its component.
 *
 * Run with: npm test
 */

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { Agent, ContextImpl } from '@agnt5/sdk';

import { supportAgent } from '../src/agents.js';
import { findOrder } from '../src/functions.js';
import { orderView, support } from '../src/server.js';
import { auditMinutes, auditOrders, refundIdempotencyKey } from '../src/workflows.js';

test('the server publishes a function, a workflow and an agent', () => {
  const definition = support.definition();
  assert.equal(definition.name, 'support');
  const tools = Object.fromEntries(definition.tools.map((tool) => [tool.name, tool.component]));
  assert.deepEqual(tools, {
    lookup_order: { type: 'function', name: 'lookup_order' },
    refund_order: { type: 'workflow', name: 'refund_order' },
    audit_orders: { type: 'workflow', name: 'audit_orders' },
    ask_support: { type: 'agent', name: 'support_agent' },
  });
});

// The worker serves an agent published on a server without a registerAgents
// call, for a tool whose target is an Agent (@agnt5/sdk >= 0.10.9).
test('ask_support publishes the agent itself, so the worker serves it', () => {
  const tool = support.publishedToolList().find((t) => t.name === 'ask_support');
  assert.ok(tool, 'ask_support is published');
  assert.equal(tool.componentType, 'agent');
  assert.ok(tool.target instanceof Agent);
  assert.equal(tool.target, supportAgent);
});

// The view is built from ui/ and committed; a deploy sends it as is.
test('lookup_order shows the order view, built as one self-contained file', () => {
  const definition = support.definition();
  const lookup = definition.tools.find((t) => t.name === 'lookup_order');
  assert.equal(lookup?.view, 'order');

  const html = readFileSync(new URL('../views/order.html', import.meta.url), 'utf8');
  assert.match(html, /^<!doctype html>/i, 'run `npm run build` in ui/');
  assert.ok(Buffer.byteLength(html) <= 2 * 1024 * 1024, 'views are up to 2 MB');
  assert.doesNotMatch(html, /<script[^>]+src=|<link[^>]+href=/i, 'everything is inlined');
  assert.equal(orderView.sha256, createHash('sha256').update(html).digest('hex'));
  assert.equal(definition.views?.[0]?.name, 'order');
});

// A call hands back a run at once; with no view of its own, MCP Apps clients
// show the built-in run card.
test('audit_orders runs in the background with the run card', () => {
  const audit = support.definition().tools.find((t) => t.name === 'audit_orders');
  assert.equal(audit?.mode, 'background');
  assert.equal(audit?.annotations.readOnlyHint, true);
  assert.equal(audit?.view, undefined);
  assert.equal(audit?.input_schema.properties?.minutes?.default, 10);
  // No schema bounds: out-of-range minutes reach auditMinutes and are held
  // to 1 to 30, as in the Python template, instead of failing validation.
  assert.equal(audit?.input_schema.properties?.minutes?.minimum, undefined);
  assert.equal(audit?.input_schema.properties?.minutes?.maximum, undefined);
});

test('an audit takes 1 to 30 minutes', () => {
  assert.equal(auditMinutes(10), 10);
  assert.equal(auditMinutes(0), 1);
  assert.equal(auditMinutes(90), 30);
});

// The whole audit, run in-process, its durable sleeps recorded instead of
// waited out.
test('auditOrders checks every order over 10 minutes', async () => {
  const ctx = new ContextImpl('audit-test', 'audit-test', 0, 'mcp-server');
  const pauses: number[] = [];
  ctx.sleep = async (durationMs: number) => {
    pauses.push(durationMs);
  };
  const result = await auditOrders(ctx, {});
  assert.deepEqual(result, { orders: 3, checks: 9, flagged: ['o-1003 shipment'], minutes: 10 });
  assert.equal(Math.round(pauses.reduce((a, b) => a + b) / 60_000), 10);
});

test('one refund key per order', () => {
  assert.equal(refundIdempotencyKey('o-1002'), refundIdempotencyKey('o-1002'));
  assert.notEqual(refundIdempotencyKey('o-1002'), refundIdempotencyKey('o-1003'));
});

test('findOrder', () => {
  assert.equal(findOrder('O-1001').customer, 'Ada');
  assert.throws(() => findOrder('o-9'), /o-1001/);
});
