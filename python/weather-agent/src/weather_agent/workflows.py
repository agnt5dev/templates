"""Weather agent workflow."""

from agnt5 import workflow, WorkflowContext

from weather_agent.agents import weather_agent
from weather_agent.functions import get_weather_data
from weather_agent.models import WeatherData


@workflow(name="get_weather")
async def get_weather(ctx: WorkflowContext, location: str) -> WeatherData:
    """Fetch weather data for a location.

    Args:
        ctx: Workflow context (injected by AGNT5)
        location: City name, coordinates, or postal code

    Returns:
        WeatherData: Weather information
    """
    weather = await ctx.task(get_weather_data, location)

    ctx.logger.info(
        f"Weather retrieved: {weather.location} - {weather.temperature_c}°C"
    )

    return weather


@workflow(name="get_weather_interactive", chat=True)
async def get_weather_interactive(ctx: WorkflowContext, message: str, **kwargs) -> str:
    """Interactive chat workflow for weather queries.

    The agent's conversation history is stored in the workflow entity,
    enabling multi-turn conversations with context persistence.

    Args:
        ctx: Workflow context (injected by AGNT5)
        message: User message for the chat
        **kwargs: Additional parameters (session_id, etc.) passed by chat endpoint

    Returns:
        str: Agent response
    """
    result = await weather_agent.run_sync(message, context=ctx)

    ctx.logger.info(f"Weather agent response: {result.output[:100]}...")

    return result.output
