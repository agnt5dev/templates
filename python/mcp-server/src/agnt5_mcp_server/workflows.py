"""Workflows: multi-step work that survives crashes and restarts.

Each `ctx.step(...)` is a durable checkpoint: if the worker restarts after the
order was looked up, the run resumes at the refund instead of starting over.
A step whose result was not checkpointed yet can still run again, so the
refund carries an idempotency key its provider dedupes on (see issue_refund).
Published on the MCP server, a call waits for the result up to the server's
call budget, then hands the client a run handle it can follow with the
built-in get_run tool.

audit_orders is the long one: about 10 minutes of steps and durable sleeps,
reporting progress as it goes, to follow in the run card or with get_run.
"""
from __future__ import annotations

from agnt5 import WorkflowContext, workflow

from agnt5_mcp_server.functions import ORDERS, audit_order, issue_refund, lookup_order


def refund_idempotency_key(order_id: str) -> str:
    """The key of an order's full refund: one per order, whichever run, retry
    or repeated tool call asks for it."""
    return f"refund-{order_id}"


@workflow
async def refund_order(ctx: WorkflowContext, order_id: str, reason: str = "customer request") -> dict:
    """Refund an order in full: look it up, then issue the refund."""
    order = await ctx.step(lookup_order, order_id=order_id)
    refund = await ctx.step(
        issue_refund,
        order_id=order["id"],
        amount=order["total"],
        reason=reason,
        idempotency_key=refund_idempotency_key(order["id"]),
    )
    return {"order": order["id"], "customer": order["customer"], "refunded": refund["amount"], "refund_id": refund["refund_id"]}


# What an audit checks on each order: one step per order and check.
AUDIT_CHECKS = ("payment", "shipment", "refunds")


def audit_minutes(minutes: int) -> int:
    """How long an audit takes: the minutes asked for, held to 1 to 30."""
    return min(max(minutes, 1), 30)


@workflow
async def audit_orders(ctx: WorkflowContext, minutes: int = 10) -> dict:
    """Audit every order's payment, shipment and refunds over about `minutes` (1 to 30).

    A long run on purpose, 10 minutes by default: one step per order and
    check, a durable sleep after each, and a progress report before each."""
    minutes = audit_minutes(minutes)
    checks = [(order_id, check) for order_id in ORDERS for check in AUDIT_CHECKS]
    pause = minutes * 60 / len(checks)
    flagged = []
    for done, (order_id, check) in enumerate(checks):
        ctx.progress(done, total=len(checks), message=f"Checking {check} on {order_id}")
        result = await ctx.step(audit_order, order_id=order_id, check=check)
        if not result["ok"]:
            flagged.append(f"{order_id} {check}")
        # A durable timer, unlike asyncio.sleep: after a restart the run
        # waits out what is left of it instead of starting over.
        await ctx.sleep(pause, name=f"pause-{order_id}-{check}")
    ctx.progress(len(checks), total=len(checks), message=f"Audited {len(ORDERS)} orders")
    return {"orders": len(ORDERS), "checks": len(checks), "flagged": flagged, "minutes": minutes}
