#!/usr/bin/env python3
"""AGNT5 Quickstart Python."""

import asyncio
import os
import sys
import logging
from agnt5 import Worker


# Import components for explicit registration (hybrid approach)
from agnt5_quickstart import research


# Configure logging (this will also control Rust log levels via PyO3-log)
logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG to see all Rust logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "sdk-python-benchmark"


async def main():
    """Main entry point for the worker."""
    logger.info("Starting %s worker...", SERVICE_NAME)

    # Configuration from environment
    coordinator_endpoint = os.getenv(
        "AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186"
    )

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            # Hybrid registration: workflows/entities/agents explicit, tools auto-included
            workflows=[
                research,
            ],
        )

        # Components are explicitly registered, tools are auto-included from agents
        logger.info("Worker created successfully with explicit component registration")

        # Start the worker (this is async and will block until shutdown)
        logger.info("Starting worker and registering with coordinator...")
        await worker.run()

    except ImportError as e:
        logger.error("Make sure to install agnt5: pip install agnt5")
        return 1
    except Exception as e:
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
