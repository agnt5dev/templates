"""The `process_expenses` workflow: receipts in, ledger entries and emails out.

Kill the worker at any point and restart it: the run picks up where it left
off. Finished steps (LLM extractions included) return their checkpoints,
the human approval and the payout wait survive the restart, and nothing is
posted or emailed twice.
"""
from __future__ import annotations

import os

from agnt5 import WorkflowContext, workflow

from expense_processor.demo import crash_point
from expense_processor.functions import (
    build_report,
    convert_to_usd,
    extract_receipt,
    load_receipts,
    notify_reimbursements,
    post_to_ledger,
)

# Durable sleeps in this demo are measured in "hours". Set to 3600 for real time;
# the default turns a 48-hour payout window into 48 seconds.
SECONDS_PER_HOUR = float(os.getenv("EXPENSES_SECONDS_PER_HOUR", "1"))


@workflow
async def process_expenses(
    ctx: WorkflowContext,
    batch_id: str = "2026-10-team-travel",
    approval_limit_usd: float = 500.0,
    payout_delay_hours: float = 48.0,
    flaky_failures: int = 0,
    crash_at: str | None = None,
) -> dict:
    """Extract, convert, approve, post, wait for payout, notify.

    Demo inputs:
        flaky_failures: make the FX service fail this many times (retries absorb it).
        crash_at: kill the worker once at "receipt_<n>", right after the nth
            receipt is extracted.
    """
    receipts = await ctx.step(load_receipts, batch_id)

    # 1. One LLM call per receipt, each its own checkpoint. The key ties the
    #    checkpoint to the receipt, not to its position in the loop.
    expenses = []
    for n, receipt in enumerate(receipts, start=1):
        expenses.append(await ctx.step(extract_receipt, receipt, key=receipt["id"]))
        await crash_point(ctx, crash_at, f"receipt_{n}")

    # 2. A flaky dependency. The step's retry policy absorbs the failures.
    expenses = await ctx.step(convert_to_usd, expenses, flaky_failures)

    small = [e for e in expenses if e["amount_usd"] <= approval_limit_usd]
    large = [e for e in expenses if e["amount_usd"] > approval_limit_usd]

    # 3. Post everything under the limit right away, exactly once.
    auto_posted = await ctx.step(post_to_ledger, batch_id, small, key="auto-approved")

    # 4. A manager signs off on the rest. The run is not in memory while it
    #    waits; restart the worker as often as you like before answering.
    decision, approved_posted = "not_needed", {"posted": [], "duplicates_skipped": []}
    if large:
        lines = "\n".join(
            f"- {e['employee']}: {e['vendor']} ${e['amount_usd']:,.2f} ({e['category']})" for e in large
        )
        answer = await ctx.wait_for_user(
            f"{len(large)} expenses are over ${approval_limit_usd:,.0f}:\n{lines}\n\nApprove them?",
            input_type="approval",
            options=[{"id": "approve", "label": "Approve"}, {"id": "reject", "label": "Reject"}],
        )
        decision = "approve" if (answer or "").strip().lower() in ("approve", "approved") else "reject"
        if decision == "approve":
            approved_posted = await ctx.step(post_to_ledger, batch_id, large, key="manager-approved")

    reimbursed = small + (large if decision == "approve" else [])

    # 5. Wait out the payout window. Durable: no worker is held while it sleeps.
    await ctx.sleep(payout_delay_hours * SECONDS_PER_HOUR, name="payout_window")

    # 6. Tell each employee, once.
    notified = await ctx.step(notify_reimbursements, batch_id, reimbursed)

    report = await ctx.step(build_report, len(receipts))
    return {
        "batch_id": batch_id,
        "total_usd": round(sum(e["amount_usd"] for e in expenses), 2),
        "auto_approved": auto_posted,
        "manager_decision": decision,
        "manager_approved": approved_posted,
        "notified": notified,
        "execution_report": report,
    }
