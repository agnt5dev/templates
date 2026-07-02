#!/usr/bin/env python3
"""Deep Research Agent - AGNT5 Worker."""

import asyncio
import os
import sys
import logging
from agnt5 import Worker
from deep_research.workflows import deep_research_workflow
from deep_research.agents import scoping_agent, research_agent, writing_agent
from deep_research.tools import fetch_webpage_tool, wikipedia_search_tool
from deep_research.functions import _plan_research, _conduct_research, _write_report


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "deep-research"


async def main():
    """Main entry point for the worker."""
    logger.info("Starting %s worker...", SERVICE_NAME)

    # Configuration from environment
    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")
    tenant_id = os.getenv("AGNT5_TENANT_ID")
    deployment_id = os.getenv("AGNT5_DEPLOYMENT_ID")

    logger.info(f"Environment - TENANT_ID: {tenant_id}, DEPLOYMENT_ID: {deployment_id}")

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="2.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            workflows=[deep_research_workflow],
            functions=[_plan_research, _conduct_research, _write_report],
            agents=[scoping_agent, research_agent, writing_agent],
            tools=[fetch_webpage_tool, wikipedia_search_tool],
        )

        logger.info("Worker created successfully with parallel research system:")
        logger.info("  - 3 specialized agents: Scoping, Research, Writing")
        logger.info("  - 1 main workflow: deep_research_workflow")

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
