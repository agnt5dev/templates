import asyncio
from agnt5 import with_entity_context
from agnt5._telemetry import setup_module_logger
from weather_agent.workflows import get_weather

logger = setup_module_logger(__name__)


@with_entity_context
async def test_workflow():
    location = input("Enter location for weather data (e.g., London): ")
    result = await get_weather(location=location)
    logger.info("✅ Weather Result: %s", result)
    return result


if __name__ == "__main__":
    asyncio.run(test_workflow())
