#!/usr/bin/env python3
"""
Support Triage Worker - AGNT5 Quickstart

Two workflows demonstrating different patterns:

1. support_triage (chat=False) - Structured Pipeline
   - Checkpointing: Steps are memoized; completed steps skip on restart
   - Human-in-the-Loop: Durable pauses for approval that survive restarts
   - Exactly-Once: No duplicate side effects after recovery

2. support_chat (chat=True) - Interactive Chat
   - Multi-turn conversation with the support agent
   - Agent uses tools to search KB and fetch customer info

Usage:
    python app.py

Or with the AGNT5 CLI:
    agnt5 dev up
"""

import asyncio
import logging
import os
import sys

import agnt5
from agnt5 import Worker, get_logger
from support_triage import support_triage, support_agent, my_scheduled_workflow
from support_triage.functions import (
    analyze_ticket,
    fetch_customer_info,
    hello_world,
    post_reply,
)
from support_triage.tools import (
    categorize_ticket_tool,
    fetch_customer_info_tool,
    search_kb_tool,
)

SERVICE_NAME = "support-triage"
logger = get_logger(__name__)
# agnt5.set_log_level(logging.DEBUG)


async def main():
    """Main entry point for the support triage worker."""
    # Configuration from environment
    coordinator_endpoint = os.getenv(
        "AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186"
    )

    # Check if mock mode is enabled
    mock_mode = os.getenv("AGNT5_MOCK_MODE", "").lower() in ("1", "true", "yes")

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            workflows=[support_triage, my_scheduled_workflow],
            functions=[fetch_customer_info, analyze_ticket, post_reply, hello_world],
            agents=[support_agent],
            tools=[search_kb_tool, fetch_customer_info_tool, categorize_ticket_tool],
        )

        if not mock_mode:
            logger.info("Set AGNT5_MOCK_MODE=1 to run without an API key")

        # Start the worker
        await worker.run()

    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure to install dependencies: pip install -e .")
        return 1
    except asyncio.CancelledError:
        # Clean exit on cancellation (e.g., Ctrl+C)
        return 0
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        sys.exit(0)
