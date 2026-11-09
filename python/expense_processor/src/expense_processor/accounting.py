"""A stand-in for the external systems: the accounting ledger and the email outbox.

Both are JSON files under `.data/`. Like most real payment, ledger, and email
APIs, they accept an idempotency key and refuse to apply the same key twice.
That refusal is what keeps a retried or replayed step from double-posting.
"""
from __future__ import annotations

import json
from pathlib import Path

from expense_processor.demo import data_dir


def _load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _save(path: Path, records: dict) -> None:
    path.write_text(json.dumps(records, indent=2))


def _write_once(filename: str, idempotency_key: str, record: dict) -> bool:
    """Store `record` under `idempotency_key`. Returns False if the key was already used."""
    path = data_dir() / filename
    records = _load(path)
    if idempotency_key in records:
        return False
    records[idempotency_key] = record
    _save(path, records)
    return True


def post_ledger_entry(idempotency_key: str, entry: dict) -> bool:
    return _write_once("ledger.json", idempotency_key, entry)


def send_email(idempotency_key: str, email: dict) -> bool:
    return _write_once("outbox.json", idempotency_key, email)
