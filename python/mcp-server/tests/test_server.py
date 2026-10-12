"""The server publishes one tool per component, each naming its component.

Run with: uv run --with pytest pytest
"""
import asyncio
import hashlib
import re
from pathlib import Path

import pytest

from agnt5_mcp_server.functions import find_order
from agnt5_mcp_server.server import order_view, support


def test_server_publishes_function_workflow_and_agent():
    definition = support.definition()
    assert definition["name"] == "support"
    tools = {tool["name"]: tool["component"] for tool in definition["tools"]}
    assert tools == {
        "lookup_order": {"type": "function", "name": "lookup_order"},
        "refund_order": {"type": "workflow", "name": "refund_order"},
        "audit_orders": {"type": "workflow", "name": "audit_orders"},
        "ask_support": {"type": "agent", "name": "support_agent"},
    }


def test_lookup_order_shows_the_order_view_built_as_one_file():
    """The view is built from ui/ and committed; a deploy sends it as is."""
    definition = support.definition()
    lookup = next(tool for tool in definition["tools"] if tool["name"] == "lookup_order")
    assert lookup["view"] == "order"

    built = Path(__file__).parents[1] / "src" / "agnt5_mcp_server" / "views" / "order.html"
    html = built.read_text(encoding="utf-8")
    assert html.lower().startswith("<!doctype html>"), "run `npm run build` in ui/"
    assert len(html.encode()) <= 2 * 1024 * 1024, "views are up to 2 MB"
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=", html, re.I), "everything is inlined"
    assert order_view.sha256 == hashlib.sha256(html.encode()).hexdigest()
    assert definition["views"][0]["name"] == "order"


def test_audit_orders_runs_in_the_background_with_the_run_card():
    """A call hands back a run at once; with no view of its own, MCP Apps
    clients show the built-in run card."""
    audit = next(tool for tool in support.definition()["tools"] if tool["name"] == "audit_orders")
    assert audit["mode"] == "background"
    assert audit["annotations"]["readOnlyHint"] is True
    assert "view" not in audit
    assert audit["input_schema"]["properties"]["minutes"]["default"] == 10


def test_audit_takes_1_to_30_minutes():
    from agnt5_mcp_server.workflows import audit_minutes

    assert audit_minutes(10) == 10
    assert audit_minutes(0) == 1
    assert audit_minutes(90) == 30


def test_audit_orders_checks_every_order_over_10_minutes(monkeypatch):
    """The whole audit, run in-process, its durable sleeps recorded instead of waited out."""
    from agnt5 import WorkflowContext

    from agnt5_mcp_server.workflows import audit_orders

    pauses = []

    async def sleep(ctx, seconds, name=None):
        pauses.append(seconds)

    monkeypatch.setattr(WorkflowContext, "sleep", sleep)
    result = asyncio.run(audit_orders())
    assert result == {"orders": 3, "checks": 9, "flagged": ["o-1003 shipment"], "minutes": 10}
    assert round(sum(pauses)) == 10 * 60


def test_refund_key_is_stable_per_order():
    from agnt5_mcp_server.workflows import refund_idempotency_key

    assert refund_idempotency_key("o-1002") == refund_idempotency_key("o-1002")
    assert refund_idempotency_key("o-1002") != refund_idempotency_key("o-1003")


def test_find_order():
    assert find_order("O-1001")["customer"] == "Ada"
    with pytest.raises(ValueError, match="o-1001"):
        find_order("o-9")
