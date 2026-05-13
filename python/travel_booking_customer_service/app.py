#!/usr/bin/env python3
"""Travel Booking Service - AGNT5 Worker."""

import asyncio
import os
import sys
import logging
from agnt5 import Worker


# Import travel booking components
from travel_booking import (
    # Workflows
    travel_booking_workflow,
    # Agents
    travel_booking_agent,
    # Entities
    TravelBookingSession,
)

# Configure logging (this will also control Rust log levels via PyO3-log)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "travel-booking-service"

async def main():
    """Main entry point for the worker."""
    logger.info("Starting %s worker...", SERVICE_NAME)

    # Configuration from environment
    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")
    project_id = os.getenv("AGNT5_PROJECT_ID")
    deployment_id = os.getenv("AGNT5_DEPLOYMENT_ID")

    # Log the IDs we're seeing
    logger.info(f"Environment variables - PROJECT_ID: {project_id}, DEPLOYMENT_ID: {deployment_id}")

    # The SDK reads these from the environment automatically.

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            # Register travel booking components
            workflows=[
                travel_booking_workflow,
            ],
            entities=[
                TravelBookingSession,
            ],
            agents=[travel_booking_agent],
        )

        # Components are explicitly registered, tools are auto-included from agents
        logger.info("Travel booking worker created successfully with unified entity")

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
