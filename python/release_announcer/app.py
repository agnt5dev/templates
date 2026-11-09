"""AGNT5 release-announcer — worker entry point."""
import asyncio
import logging
import sys

from agnt5 import Worker

from release_announcer import announce_release  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    worker = Worker(
        service_name="release-announcer",
        service_version="0.1.0",
        auto_register=True,
    )
    logger.info("Worker created. Connecting to AGNT5 runtime...")
    await worker.run()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
