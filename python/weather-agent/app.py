"""Weather Agent Worker.

This file registers the weather agent with the AGNT5 platform.

Usage:
    # Start the AGNT5 platform (if not already running)
    agnt5 dev up

    # Start this worker
    python app.py
"""

import asyncio
from agnt5 import Worker
from agnt5._telemetry import setup_module_logger

from weather_agent.config import config

logger = setup_module_logger(__name__)


async def main():
    """Start the AGNT5 Worker for the Weather Agent."""
    logger.info("=" * 60)
    logger.info("🌤️  WEATHER AGENT - Worker")
    logger.info("=" * 60)

    # Create and configure worker
    # auto_register=True discovers all @function, @workflow, @tool, @entity, and Agent
    # components from the source paths defined in pyproject.toml
    worker = Worker(
        service_name=config.SERVICE_NAME,
        service_version=config.SERVICE_VERSION,
        auto_register=True,
        metadata={
            "description": "Simple weather agent for fetching weather data",
        },
    )

    logger.info("✅ Components auto-discovered from weather_agent package")
    logger.info("")
    logger.info("🔗 Connecting to AGNT5 Coordinator...")
    logger.info("")

    # Start the worker
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n👋 Worker shutting down gracefully...")
    except Exception as e:
        logger.exception("❌ Worker error: %s", e)
        raise
