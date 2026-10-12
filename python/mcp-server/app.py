"""AGNT5 MCP server starter: worker entry point.

Importing agnt5_mcp_server.server is what publishes the MCP server: a worker
publishes only the servers defined in modules it imports.
"""
import asyncio
import logging
import sys

from agnt5 import Worker

from agnt5_mcp_server.agents import support_agent
from agnt5_mcp_server.functions import audit_order, issue_refund, lookup_order
from agnt5_mcp_server.server import support  # noqa: F401  (publishes the "support" MCP server)
from agnt5_mcp_server.workflows import audit_orders, refund_order

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    worker = Worker(
        service_name="mcp-server",
        service_version="0.1.0",
        functions=[lookup_order, issue_refund, audit_order],
        workflows=[refund_order, audit_orders],
        agents=[support_agent],
    )
    logger.info("Worker created. Connecting to AGNT5 runtime...")
    await worker.run()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
