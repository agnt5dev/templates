import asyncio
from agnt5 import get_logger, with_entity_context
from weather_agent.workflows import get_weather

logger = get_logger(__name__)


@with_entity_context
async def test_workflow():
    location = input("Enter location for weather data (e.g., London): ")
    result = await get_weather(location=location)
    logger.info("✅ Weather Result: %s", result)
    return result


if __name__ == "__main__":
    asyncio.run(test_workflow())
