"""Steps for the support triage workflow.

Each `@function` is a durable step. Called via `ctx.step(...)` inside a
workflow, its result is checkpointed, so a worker restart skips the steps that
already completed — the agent's model calls included.
"""
from __future__ import annotations

from agnt5 import FunctionContext, function

from .agent import build_support_agent
from .data import BUG_WORDS, ORDERS, REFUND_WORDS, URGENT_WORDS


@function
async def classify_ticket(ctx: FunctionContext, message: str) -> dict:
    """Sort a ticket into refund, bug or question, and flag urgent ones."""
    text = message.lower()
    if any(word in text for word in REFUND_WORDS):
        category = "refund"
    elif any(word in text for word in BUG_WORDS):
        category = "bug"
    else:
        category = "question"
    urgency = "high" if any(word in text for word in URGENT_WORDS) else "normal"
    return {"category": category, "urgency": urgency}


@function(retries=3, backoff="exponential")
async def lookup_order(ctx: FunctionContext, order_id: str) -> dict:
    """Fetch the order a ticket refers to. Retried, since order systems flake."""
    order = ORDERS.get(order_id)
    if order is None:
        return {"order_id": order_id, "found": False}
    return {**order, "found": True}


@function
async def draft_reply(ctx: FunctionContext, customer: str, category: str, message: str) -> dict:
    """Have the support agent draft a reply. `context=ctx` makes its model calls durable."""
    prompt = f"Customer: {customer}\nCategory: {category}\nMessage: {message}"
    result = await build_support_agent().run(user_message=prompt, context=ctx)
    return {
        "reply": result.output.strip(),
        "tools_used": [call["name"] for call in result.tool_calls],
    }
