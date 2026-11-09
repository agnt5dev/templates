"""Offline checks: no worker, model, or platform needed."""
import json

import pytest

from expense_processor import accounting, demo
from expense_processor.functions import RECEIPTS_FILE, USD_PER_UNIT, ReceiptFields


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPENSES_DATA_DIR", str(tmp_path))


def test_ledger_refuses_a_reused_idempotency_key():
    assert accounting.post_ledger_entry("key-1", {"amount": 10}) is True
    assert accounting.post_ledger_entry("key-1", {"amount": 10}) is False
    assert accounting.post_ledger_entry("key-2", {"amount": 10}) is True
    ledger = json.loads((demo.data_dir() / "ledger.json").read_text())
    assert list(ledger) == ["key-1", "key-2"]


def test_execution_log_is_filtered_by_run():
    demo.log_execution("run-a", "extract_receipt", "rcpt-01")
    demo.log_execution("run-b", "extract_receipt", "rcpt-01")
    assert [e["run_id"] for e in demo.read_execution_log("run-a")] == ["run-a"]


def test_crash_only_fires_at_its_point_and_only_once(monkeypatch):
    exits = []
    monkeypatch.setattr(demo.os, "_exit", exits.append)
    demo.maybe_crash("run-1", "receipt_7", "receipt_6")
    demo.maybe_crash("run-1", None, "receipt_7")
    assert exits == []
    demo.maybe_crash("run-1", "receipt_7", "receipt_7")
    demo.maybe_crash("run-1", "receipt_7", "receipt_7")  # the replay passes through
    assert exits == [1]


def test_sample_receipts_are_valid_and_need_approval():
    receipts = json.loads(RECEIPTS_FILE.read_text())
    assert len({r["id"] for r in receipts}) == len(receipts) == 12
    fields = [ReceiptFields(**r["mock_extraction"]) for r in receipts]
    assert {f.currency for f in fields} <= set(USD_PER_UNIT)
    over_limit = [f for f in fields if f.amount * USD_PER_UNIT[f.currency] > 500]
    assert len(over_limit) == 4  # flight, two hotels, and the conference pass go to the manager
