#!/usr/bin/env python3
"""AGNT5 Tutor Agent Worker - Demonstrates agent handoffs."""

import asyncio
import os
import sys
import logging
from agnt5 import Worker
from agents import tutor_agent, history_tutor_agent, math_tutor_agent
from entities import TutorConversation
from workflows import tutor_chat_workflow

# Configure logging (this will also control Rust log levels via PyO3-log)
logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG to see all Rust logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "agnt5-tutor-agent"

async def main():
    """Main entry point for the worker."""
    logger.info("Starting %s worker...", SERVICE_NAME)

    # Configuration from environment
    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")
    tenant_id = os.getenv("AGNT5_TENANT_ID")
    deployment_id = os.getenv("AGNT5_DEPLOYMENT_ID")

    # Log the IDs we're seeing
    logger.info(f"Environment variables - TENANT_ID: {tenant_id}, DEPLOYMENT_ID: {deployment_id}")

    # Note: The SDK should read these from environment variables automatically
    # AGNT5_TENANT_ID and AGNT5_DEPLOYMENT_ID must be set in the environment

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            agents=[tutor_agent, history_tutor_agent, math_tutor_agent],  # Triage agent + specialist agents
            entities=[TutorConversation],  # Register entities for state management
            workflows=[tutor_chat_workflow],  # Register workflows
        )

        # Using agent handoffs: triage_agent delegates to history_tutor and math_tutor
        logger.info("Worker created with agent handoffs architecture")

        # Start the worker (this is async and will block until shutdown)
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
