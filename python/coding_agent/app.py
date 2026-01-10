"""Production worker entry point for the Coding Agent.

This file starts the AGNT5 Worker for production deployment.
For local development and testing, use main.py instead.
"""

import asyncio

from agnt5 import Worker
from agnt5._telemetry import setup_module_logger

from coding_agent_agnt5.workflows import coding_agent_workflow
from coding_agent_agnt5.functions import (
    planner_node,
    code_generator_node,
    test_generator_node,
    code_sync_node,
    code_executor_node,
    final_response_node,
    error_analyzer_node
)
from coding_agent_agnt5.tools import E2BSandboxTools
from coding_agent_agnt5.config import config

logger = setup_module_logger(__name__)


async def main():
    """Start the AGNT5 Worker for the Coding Agent."""
    logger.info("🚀 CODING AGENT - Production Worker")

    try:
        config.validate()
        logger.info("✅ Configuration validated")
    except ValueError as e:
        logger.error("Configuration error while validating config: %s", e)
        return

    worker = Worker(
        service_name="coding-agent",
        service_version="1.0.0",
        auto_register=True,
        metadata={
            "description": "AI-powered coding agent with test-driven development",
            "capabilities": "planning,coding,testing,documentation",
            "language": "python",
        },
        tools=[
            E2BSandboxTools.create_sandbox,
            E2BSandboxTools.write_file,
            E2BSandboxTools.run_command,
            E2BSandboxTools.read_file,
        ],
        functions=[
            planner_node,
            code_generator_node,
            test_generator_node,
            code_sync_node,
            code_executor_node,
            final_response_node,
            error_analyzer_node
        ],
        workflows=[coding_agent_workflow],
    )

    logger.info("✅ Registered components successfully")
    logger.info("🔗 Connecting to AGNT5 Coordinator...")

    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n👋 Worker shutting down gracefully...")
    except Exception as e:
        logger.exception("Worker error: %s", e)
        raise