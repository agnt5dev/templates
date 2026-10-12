"""The MCP server: which components MCP clients (Claude, ChatGPT, Cursor, ...)
see as tools.

A deploy serves it at https://api.agnt5.com/mcp/{project}/{env}/support, and
`agnt5 dev` at a dev URL only you can sign in to. Clients sign in with AGNT5;
every tool call runs as a durable AGNT5 run you can open in Studio.

The worker publishes a server only when its module is imported, so app.py
imports this one. The server's name is part of its URL (lowercase letters,
digits, '-' and '_') and matches mcp.servers in agnt5.yaml.
"""
from __future__ import annotations

from pathlib import Path

from agnt5 import MCPServer

from agnt5_mcp_server.agents import support_agent
from agnt5_mcp_server.functions import lookup_order
from agnt5_mcp_server.workflows import audit_orders, refund_order

support = MCPServer(
    "support",
    title="Order support",
    instructions=(
        "Tools for customer orders. Use lookup_order to read an order, "
        "refund_order to refund one in full, ask_support for questions "
        "that need judgement, and audit_orders to audit every order. "
        "audit_orders takes about 10 minutes and hands back a run at once: "
        "follow it with get_run."
    ),
)

# A view: your own MCP App UI, one self-contained HTML file built from ui/
# (cd ui && npm install && npm run build). Clients that render MCP Apps show
# it for lookup_order's results; the rest read the result as text.
order_view = support.add_view("order", path=Path(__file__).parent / "views" / "order.html")

# A function answers synchronously, here shown in the order view.
support.add_function("lookup_order", lookup_order, annotations={"readOnlyHint": True}, view=order_view)

# A workflow waits up to the call budget, then hands back a run handle.
support.add_workflow(
    "refund_order",
    refund_order,
    annotations={"destructiveHint": True, "idempotentHint": False},
)

# A long workflow hands back a run handle at once (mode="background"); the
# client follows its steps and progress while it runs.
support.add_workflow("audit_orders", audit_orders, mode="background", annotations={"readOnlyHint": True})

# An agent is a tool that takes a message.
support.add_agent("ask_support", support_agent, title="Ask the support agent")

# In clients that render MCP Apps (ChatGPT, Claude, Cursor, VS Code), calls to
# auto and background tools without a view of their own, like refund_order,
# audit_orders and ask_support here, show the built-in AGNT5 run card: live
# status, steps, progress, output and Cancel run. Pass view=None to
# add_function / add_workflow / add_agent to turn it off for a tool.
