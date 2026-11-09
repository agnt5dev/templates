"""Steps for the expense workflow.

Each `@function` becomes a durable step when the workflow calls it through
`ctx.step(...)`: its result is checkpointed, and a replay returns the
checkpoint instead of running the code again.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agnt5 import FunctionContext, function, lm

from expense_processor.accounting import post_ledger_entry, send_email
from expense_processor.demo import log_execution, mock_mode, read_execution_log

MODEL = os.getenv("EXPENSES_MODEL", "openai/gpt-6-luna")
RECEIPTS_FILE = Path(__file__).parent / "receipts.json"

# Fixed rates so the demo is reproducible; a real workflow would call an FX API.
USD_PER_UNIT = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}

EXTRACTION_PROMPT = """You read expense receipts. Extract the vendor name, the
final amount actually paid (after tax and tip), its ISO 4217 currency code, a
category, and the date in YYYY-MM-DD. Receipts may use European number formats
(96,50 means 96.50) and DD/MM/YYYY dates."""


class ReceiptFields(BaseModel):
    vendor: str
    amount: float
    currency: str
    category: Literal["meals", "travel", "lodging", "equipment", "conference", "books", "other"]
    date: str


class FxServiceUnavailable(Exception):
    """The (simulated) exchange-rate service is down. Retryable."""


def _idempotency_key(ctx: FunctionContext, item: str) -> str:
    # The platform gives every step a key that stays the same across retries
    # and crash replays of that step. Suffix it per item written.
    activation = ctx.activation
    base = activation.idempotency_key if activation else f"{ctx.run_id}:local"
    return f"{base}:{item}"


@function
async def load_receipts(ctx: FunctionContext, batch_id: str) -> list[dict]:
    """Load the batch of receipts to process (a bundled sample batch)."""
    log_execution(ctx.run_id, "load_receipts", batch_id)
    receipts = json.loads(RECEIPTS_FILE.read_text())
    ctx.logger.info("Loaded %d receipts for %s", len(receipts), batch_id)
    return receipts


@function
async def extract_receipt(ctx: FunctionContext, receipt: dict) -> dict:
    """Read one receipt with an LLM and return structured expense fields.

    This is the expensive part of the workflow. Each receipt is its own step,
    so after a crash only the receipts that had not finished are re-read.
    """
    log_execution(ctx.run_id, "extract_receipt", receipt["id"])

    if mock_mode():
        await asyncio.sleep(float(os.getenv("EXPENSES_MOCK_LATENCY_S", "1.5")))
        fields = ReceiptFields(**receipt["mock_extraction"])
    else:
        response = await lm.generate(
            model=MODEL,
            system_prompt=EXTRACTION_PROMPT,
            prompt=receipt["text"],
            response_format=ReceiptFields,
        )
        fields = response.structured_output
        if fields is None:
            raise ValueError(f"Could not extract fields from {receipt['id']}: {response.text!r}")

    ctx.logger.info("Extracted %s: %s %.2f %s", receipt["id"], fields.vendor, fields.amount, fields.currency)
    return {"receipt_id": receipt["id"], "employee": receipt["employee"], **fields.model_dump()}


@function(retries=4, backoff="exponential")
async def convert_to_usd(ctx: FunctionContext, expenses: list[dict], flaky_failures: int = 0) -> list[dict]:
    """Convert every expense to USD.

    Set `flaky_failures` to make the exchange-rate service fail that many
    times first. The retry policy on the decorator retries the step with
    exponential backoff; the workflow never sees the failures.
    """
    log_execution(ctx.run_id, "convert_to_usd", attempt=ctx.attempt)
    if ctx.attempt < flaky_failures:
        ctx.logger.warning("FX service unavailable (attempt %d) - will retry", ctx.attempt + 1)
        raise FxServiceUnavailable(f"FX service returned 503 on attempt {ctx.attempt + 1}")

    return [
        {**e, "amount_usd": round(e["amount"] * USD_PER_UNIT.get(e["currency"], 1.0), 2)}
        for e in expenses
    ]


@function
async def post_to_ledger(ctx: FunctionContext, batch_id: str, expenses: list[dict]) -> dict:
    """Post expenses to the accounting ledger, each exactly once.

    If this step runs again (a retry, or a worker that died before the result
    was saved), entries that were already written are refused as duplicates by
    their idempotency key, so nothing is double-posted.
    """
    log_execution(ctx.run_id, "post_to_ledger", batch_id)
    posted, duplicates = [], []
    for expense in expenses:
        entry = {"batch_id": batch_id, **expense}
        if post_ledger_entry(_idempotency_key(ctx, expense["receipt_id"]), entry):
            posted.append(expense["receipt_id"])
        else:
            duplicates.append(expense["receipt_id"])

    if duplicates:
        ctx.logger.warning("Skipped %d already-posted entries: %s", len(duplicates), duplicates)
    return {"posted": posted, "duplicates_skipped": duplicates}


@function
async def notify_reimbursements(ctx: FunctionContext, batch_id: str, expenses: list[dict]) -> dict:
    """Email each employee their reimbursement total, once."""
    log_execution(ctx.run_id, "notify_reimbursements", batch_id)
    totals: Counter[str] = Counter()
    for e in expenses:
        totals[e["employee"]] += e["amount_usd"]

    sent = []
    for employee, total in sorted(totals.items()):
        email = {
            "to": employee,
            "subject": f"Your expenses for {batch_id} have been reimbursed",
            "body": f"${total:,.2f} is on its way to your account.",
        }
        if send_email(_idempotency_key(ctx, employee), email):
            sent.append(employee)
    return {"emails_sent": sent}


@function
async def build_report(ctx: FunctionContext, receipt_count: int) -> dict:
    """Summarize how many times each step's code actually ran in this run."""
    executions = Counter(e["step"] for e in read_execution_log(ctx.run_id))
    return {
        "receipts": receipt_count,
        "llm_extractions_run": executions["extract_receipt"],
        "step_executions": dict(executions),
    }
