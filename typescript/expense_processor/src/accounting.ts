/**
 * A stand-in for the external systems: the accounting ledger and the email outbox.
 *
 * Both are JSON files under `.data/`. Like most real payment, ledger, and email
 * APIs, they accept an idempotency key and refuse to apply the same key twice.
 * That refusal is what keeps a retried or replayed step from double-posting.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { dataDir } from './demo.js';

/** Store `record` under `idempotencyKey`. Returns false if the key was already used. */
function writeOnce(filename: string, idempotencyKey: string, record: object): boolean {
  const path = join(dataDir(), filename);
  const records: Record<string, object> = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : {};
  if (idempotencyKey in records) return false;
  records[idempotencyKey] = record;
  writeFileSync(path, JSON.stringify(records, null, 2));
  return true;
}

export function postLedgerEntry(idempotencyKey: string, entry: object): boolean {
  return writeOnce('ledger.json', idempotencyKey, entry);
}

export function sendEmail(idempotencyKey: string, email: object): boolean {
  return writeOnce('outbox.json', idempotencyKey, email);
}
