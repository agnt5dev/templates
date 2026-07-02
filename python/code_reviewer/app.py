import asyncio

from agnt5 import Worker
from agnt5._telemetry import setup_module_logger

from code_reviewer.config import config

logger = setup_module_logger(__name__)


async def main():
    logger.info("🚀 CODE REVIEWER - Production Worker")

    try:
        config.validate()
        logger.info("✅ Configuration validated")
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return

    worker = Worker(
        service_name="code-reviewer",
        service_version="2.0.0",
        auto_register=True,
        metadata={
            "description": (
                "AI-powered code reviewer that analyzes pull requests "
                "with per-file parallel reviews and dedicated security analysis."
            ),
            "capabilities": "pr-review,security-review,ticket-alignment,tech-stack-detection",
            "language": "python",
        },
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
