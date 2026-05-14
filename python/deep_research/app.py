#!/usr/bin/env python3
"""Deep Research Agent - AGNT5 Worker."""

import asyncio
import os
import sys
import logging
from agnt5 import Worker
from deep_research.workflows import deep_research_workflow
from deep_research.functions import (clarify_and_plan, conduct_research, write_report)
from deep_research.agents import scoping_agent, research_agent, writing_agent


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "agnt5-deep-research"


async def main():
    """Main entry point for the worker."""
    logger.info("Starting %s worker...", SERVICE_NAME)

    # Configuration from environment
    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")
    project_id = os.getenv("AGNT5_PROJECT_ID")
    deployment_id = os.getenv("AGNT5_DEPLOYMENT_ID")

    logger.info(f"Environment - PROJECT_ID: {project_id}, DEPLOYMENT_ID: {deployment_id}")

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="2.1.0",  # Bumped version for state API migration
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            workflows=[deep_research_workflow],
            functions=[clarify_and_plan, conduct_research, write_report],
            agents=[scoping_agent, research_agent, writing_agent],
        )

        logger.info("Worker created successfully with simplified 3-agent research system:")
        logger.info("  - 3 specialized agents: Scoping, Research, Writing")
        logger.info("  - 1 main workflow: deep_research_workflow")
        logger.info("  - 3 stage functions: clarify_and_plan, conduct_research, write_report")

        # Start the worker
        logger.info("Starting worker and registering with coordinator...")
        await worker.run()

    except ImportError as e:
        logger.error("Make sure to install agnt5: pip install agnt5")
        logger.error(f"Import error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
