/**
 * Demo-only helpers: the crash switch and the execution log.
 *
 * None of this is needed in a real workflow. It exists so you can break the
 * worker on purpose and then *see* what replay skipped. Everything is written
 * under `.data/` in the project directory (override with RELEASE_DATA_DIR).
 */

import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Context } from '@agnt5/sdk';

export function dataDir(): string {
  const dir = process.env.RELEASE_DATA_DIR || join(process.cwd(), '.data');
  mkdirSync(dir, { recursive: true });
  return dir;
}

export function mockMode(): boolean {
  const flags = [process.env.RELEASE_MOCK_MODE ?? '', process.env.AGNT5_MOCK_MODE ?? ''];
  return flags.some((flag) => ['1', 'true', 'yes'].includes(flag.toLowerCase()));
}

export interface ExecutionEntry {
  runId: string;
  step: string;
  item: string;
  attempt: number;
  ts: number;
}

/**
 * Append one line each time a step's code *actually runs*.
 *
 * A replayed step returns its checkpointed result without running its code,
 * so it never reaches this call. After a crash, the log shows which work was
 * redone and which was not.
 */
export function logExecution(runId: string, step: string, item = '', attempt = 0): void {
  const entry: ExecutionEntry = { runId, step, item, attempt, ts: Date.now() / 1000 };
  appendFileSync(join(dataDir(), 'execution_log.jsonl'), JSON.stringify(entry) + '\n');
}

export function readExecutionLog(runId: string): ExecutionEntry[] {
  const path = join(dataDir(), 'execution_log.jsonl');
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as ExecutionEntry)
    .filter((e) => e.runId === runId);
}

/**
 * Run `fn` as a checkpointed step and return its result. On replay the
 * checkpoint can come back as its JSON text rather than the value, so a string
 * is decoded before use. Every step here returns an object or an array, never
 * a string, so the decode can't misread a real result.
 */
export async function step<T>(
  ctx: Context,
  name: string,
  fn: () => T | Promise<T>,
  key?: string,
): Promise<T> {
  const result = await ctx.step<T | string>(name, fn, key === undefined ? undefined : { key });
  return typeof result === 'string' ? (JSON.parse(result) as T) : result;
}

/**
 * Kill the worker process once, at `point`.
 *
 * The crash point is itself a checkpointed step. Its code runs the first time
 * the workflow reaches it, and that is the only time the worker is killed. On
 * replay the step returns from its checkpoint without running, so the run
 * continues even on a new container. `process.exit` skips all cleanup, like a
 * power cut or an OOM kill.
 */
export async function crashPoint(ctx: Context, crashAt: string | undefined, point: string): Promise<void> {
  if (crashAt !== point) return;
  let firstPass = false;
  await step(ctx, `crash_point_${point}`, () => {
    firstPass = true;
    return { point };
  });
  if (firstPass) {
    console.log(`💥 Simulated crash at '${point}' (run ${ctx.runId}). Restart the worker to resume.`);
    process.exit(1);
  }
}

/** Studio answers an approval with "approved"; the API takes the option id "approve". */
export function approved(answer: string | null | undefined): boolean {
  return ['approve', 'approved'].includes((answer ?? '').trim().toLowerCase());
}

/** The platform gives every step a key that stays the same across retries and replays of that step. */
export function idempotencyKey(ctx: Context, item = ''): string {
  const base = ctx.activation?.idempotencyKey ?? `${ctx.runId}:local`;
  return item ? `${base}:${item}` : base;
}
