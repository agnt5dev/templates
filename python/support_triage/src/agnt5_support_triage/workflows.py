"""The `triage_ticket` workflow.

    triage_ticket (workflow)
    ├─ classify_ticket
    ├─ lookup_order          (only when the ticket names an order)
    ├─ wait_for_user         (only for refunds above APPROVAL_THRESHOLD_USD)
    └─ draft_reply           (support agent → get_policy tool)

Every `ctx.step(...)` is a checkpoint. While the workflow waits for approval it
is not in process memory; it resumes from the checkpoints, possibly on another
host, when the reviewer answers.
"""
from __future__ import annotations

from typing import Optional

from agnt5 import WorkflowContext, workflow

from .data import APPROVAL_THRESHOLD_USD
from .functions import classify_ticket, draft_reply, lookup_order


@workflow
async def triage_ticket(
    ctx: WorkflowContext,
    ticket_id: str,
    customer: str,
    message: str,
    order_id: Optional[str] = None,
) -> dict:
    """Classify a ticket, check its order, get approval for large refunds, draft a reply."""
    ctx.state.set("status", "classifying")
    triage = await ctx.step(classify_ticket, message=message)

    order = None
    if order_id:
        order = await ctx.step(lookup_order, order_id=order_id)

    decision = "not_needed"
    if (
        triage["category"] == "refund"
        and order
        and order["found"]
        and order["amount_usd"] > APPROVAL_THRESHOLD_USD
    ):
        ctx.state.set("status", "awaiting_approval")
        answer = await ctx.wait_for_user(
            f"Approve a ${order['amount_usd']} refund for {order['order_id']} ({customer})?",
            input_type="approval",
            options=[
                {"id": "approve", "label": "Approve"},
                {"id": "reject", "label": "Reject"},
            ],
        )
        decision = "approved" if answer == "approve" else "rejected"

    ctx.state.set("status", "drafting")
    draft = await ctx.step(
        draft_reply, customer=customer, category=triage["category"], message=message
    )

    ctx.state.set("status", "done")
    return {
        "ticket_id": ticket_id,
        "category": triage["category"],
        "urgency": triage["urgency"],
        "order": order,
        "refund_decision": decision,
        "reply": draft["reply"],
        "tools_used": draft["tools_used"],
    }
