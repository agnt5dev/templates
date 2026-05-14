"""AGNT5 DeepWiki investigator worker."""
import asyncio
import logging
import sys

from agnt5 import Worker

from deep_wiki_agent import investigate_with_review, save_report  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    worker = Worker(
        service_name="deep-wiki-agent",
        service_version="0.1.0",
        auto_register=True,
    )
    logger.info("Worker created. Registering with coordinator...")
    await worker.run()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
