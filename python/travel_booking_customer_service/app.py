#!/usr/bin/env python3
"""Customer Service (Travel Booking) — AGNT5 Worker."""

import asyncio, logging, os, sys
from agnt5 import Worker
from customer_service.workflows import travel_booking_workflow
from customer_service.agents import travel_booking_agent
from customer_service.tools import search_flights, search_hotels, create_itinerary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "customer-service"


async def main() -> int:
    logger.info("Starting %s worker…", SERVICE_NAME)
    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            workflows=[travel_booking_workflow],
            agents=[travel_booking_agent],
            tools=[search_flights, search_hotels, create_itinerary],
        )
        await worker.run()
    except Exception as e:
        logger.error("Worker failed: %s", e, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
