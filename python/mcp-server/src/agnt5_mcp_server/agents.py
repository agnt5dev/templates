"""Agents: an LLM with tools. Published on the MCP server, an agent becomes a
tool that takes a message (and optionally a session to continue).

The agent needs OPENAI_API_KEY: in .env for a local worker, and as a project
secret for a deployment (agnt5 secrets set --name OPENAI_API_KEY --type api_key).
The function and the workflow need nothing.
"""

from agnt5 import Agent, Context, tool

from agnt5_mcp_server.functions import find_order


@tool
async def get_order(ctx: Context, order_id: str) -> dict:
    """Look up an order by its id (for example o-1001)."""
    return find_order(order_id)


support_agent = Agent(
    name="support_agent",
    model="openai/gpt-6-luna",
    temperature=None,  # gpt-6 rejects any temperature; None stops the SDK sending its 0.7 default
    instructions=(
        "You answer questions about customer orders. Look orders up with get_order "
        "before answering, and say plainly when an order does not exist. You cannot "
        "issue refunds: point the user to the refund_order tool."
    ),
    tools=[get_order],
)
