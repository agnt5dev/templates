"""A stand-in for the outside world: everything the workflow sends or changes.

Records go to `.data/outbox.json`. Like most real email, chat, and deploy APIs,
it accepts an idempotency key and refuses to apply the same key twice. That
refusal is what keeps a retried or replayed step from sending twice.
"""
from __future__ import annotations

import json

from onboarding_drip.demo import data_dir


def send_once(idempotency_key: str, record: dict) -> bool:
    """Store `record` under `idempotency_key`. Returns False if the key was already used."""
    path = data_dir() / "outbox.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    if idempotency_key in records:
        return False
    records[idempotency_key] = record
    path.write_text(json.dumps(records, indent=2))
    return True


def idempotency_key(ctx, item: str = "") -> str:
    # The platform gives every step a key that stays the same across retries
    # and crash replays of that step.
    activation = ctx.activation
    base = activation.idempotency_key if activation else f"{ctx.run_id}:local"
    return f"{base}:{item}" if item else base
