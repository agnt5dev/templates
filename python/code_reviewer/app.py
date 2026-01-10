import asyncio

from agnt5 import Worker
from agnt5._telemetry import setup_module_logger
from code_reviewer.config import config

from code_reviewer import (
    code_reviewer_workflow,
    CodeReviewSession,
    context_builder_agent,
    reviewer_agent,
    synthesize_review_report,
)


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
        service_name="code_reviewer_agent",
        service_version="1.0.0",
        metadata={
            "description": (
                "AI-powered code reviewer agent that analyzes pull "
                "requests and associated tickets to provide "
                "comprehensive code reviews."
            ),
            "language": "python",
        },
        functions=[synthesize_review_report],
        workflows=[code_reviewer_workflow],
        agents=[context_builder_agent, reviewer_agent],
        entities=[CodeReviewSession],
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