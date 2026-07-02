#!/usr/bin/env python3
"""AGNT5 Tutor Agent Worker - Demonstrates agent handoffs."""

import asyncio
import os
import sys
import logging
from agnt5 import Worker
from tutor_agent.agents import tutor_agent, history_tutor_agent, math_tutor_agent
from tutor_agent.workflows import tutor_chat_workflow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "agnt5-tutor-agent"


async def main():
    """Main entry point for the worker."""
    logger.info("Starting %s worker...", SERVICE_NAME)

    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            agents=[tutor_agent, history_tutor_agent, math_tutor_agent],
            workflows=[tutor_chat_workflow],
        )

        logger.info("Worker created with agent handoffs architecture")
        logger.info("Starting worker and registering with coordinator...")
        await worker.run()

    except ImportError as e:
        logger.error("Make sure to install agnt5: pip install agnt5")
        logger.error(f"Import error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
