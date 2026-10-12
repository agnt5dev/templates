"""Functions: durable steps, and tools an MCP client can call directly.

Replace the in-memory ORDERS with your own data source. Every `@function` is
an AGNT5 component: run it with `agnt5 run`, call it from a workflow with
`ctx.step(...)`, or publish it on the MCP server (see server.py).
"""
from __future__ import annotations

from agnt5 import FunctionContext, function

# Sample data so the template runs without any setup.
ORDERS: dict[str, dict] = {
    "o-1001": {"id": "o-1001", "customer": "Ada", "item": "Mechanical keyboard", "total": 129.0, "status": "delivered"},
    "o-1002": {"id": "o-1002", "customer": "Grace", "item": "USB-C dock", "total": 89.5, "status": "shipped"},
    "o-1003": {"id": "o-1003", "customer": "Linus", "item": "27-inch monitor", "total": 349.0, "status": "processing"},
}


def find_order(order_id: str) -> dict:
    """Return one order, or raise when there is none."""
    order = ORDERS.get(order_id.strip().lower())
    if order is None:
        raise ValueError(f"No order {order_id!r}. Try o-1001, o-1002 or o-1003.")
    return order


@function
async def lookup_order(ctx: FunctionContext, order_id: str) -> dict:
    """Look up an order by its id (for example o-1001)."""
    ctx.logger.info("Looking up order %s", order_id)
    return find_order(order_id)


@function
async def issue_refund(ctx: FunctionContext, order_id: str, amount: float, reason: str, idempotency_key: str) -> dict:
    """Issue a refund. A stand-in for your payment provider's API.

    Send idempotency_key with the provider call (Stripe's Idempotency-Key
    header, for example). A step runs at least once: if the worker dies after
    the provider refunded but before the result was checkpointed, the step
    runs again, and the key is what makes the provider answer the retry with
    the first refund instead of issuing a second one.
    """
    ctx.logger.info("Refunding %.2f on %s: %s (key %s)", amount, order_id, reason, idempotency_key)
    return {"refund_id": f"rf_{idempotency_key}", "order_id": order_id, "amount": amount, "reason": reason}


@function
async def audit_order(ctx: FunctionContext, order_id: str, check: str) -> dict:
    """Check an order's payment, shipment or refunds, one at a time.

    A stand-in for the systems an audit reads: here only an order still
    processing fails its shipment check.
    """
    ctx.logger.info("Checking %s on %s", check, order_id)
    order = find_order(order_id)
    ok = not (check == "shipment" and order["status"] == "processing")
    return {"order_id": order["id"], "check": check, "ok": ok}
