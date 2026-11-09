/**
 * Runs `triage_ticket` in-process, in mock mode, against the shared cases.
 *
 * `tests/cases.json` is the same file the Python template tests against, so
 * both languages are held to identical inputs and outputs.
 */

import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.MOCK_MODE = '1';

const { WaitingForUserInputError } = await import('@agnt5/sdk');
const { triageTicket: registered } = await import('../src/workflows.js');
type Ticket = import('../src/workflows.js').Ticket;

// Called without a context, a workflow builds a local one and runs in-process.
// Its type only declares the (ctx, input) form, so name the input-only form here.
const triageTicket = registered as unknown as (input: Ticket) => Promise<unknown>;

interface Case {
  name: string;
  input: any;
  expected?: unknown;
  expected_pause?: string;
}

const cases: Case[] = JSON.parse(readFileSync(new URL('./cases.json', import.meta.url), 'utf8'));

for (const c of cases) {
  test(c.name, async () => {
    if (c.expected_pause !== undefined) {
      await assert.rejects(triageTicket(c.input), (error: unknown) => {
        assert.ok(error instanceof WaitingForUserInputError);
        assert.equal(error.question, c.expected_pause);
        return true;
      });
      return;
    }
    assert.deepEqual(await triageTicket(c.input), c.expected);
  });
}
