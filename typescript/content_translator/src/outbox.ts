/**
 * A stand-in for the outside world: everything the workflow sends or changes.
 *
 * Records go to `.data/outbox.json`. Like most real email, chat, and deploy
 * APIs, it accepts an idempotency key and refuses to apply the same key twice.
 * That refusal is what keeps a retried or replayed step from sending twice.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { dataDir } from './demo.js';

/** Store `record` under `idempotencyKey`. Returns false if the key was already used. */
export function sendOnce(idempotencyKey: string, record: object): boolean {
  const path = join(dataDir(), 'outbox.json');
  const records: Record<string, object> = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : {};
  if (idempotencyKey in records) return false;
  records[idempotencyKey] = record;
  writeFileSync(path, JSON.stringify(records, null, 2));
  return true;
}
