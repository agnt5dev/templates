
from agnt5 import tool, Context

from weather_agent.models import WeatherData
from weather_agent.functions import _fetch_weather_data



@tool
async def get_weather_data_tool(ctx: Context, location: str) -> WeatherData:
    """Fetch weather data for a location.

    Args:
        ctx: Context for logging
        location: City name

    Returns:
        WeatherData: Weather information
    """
    ctx.logger.info(f"Fetching weather data for {location}")
    weather = await _fetch_weather_data(location)
    ctx.logger.info(f"Received temperature {weather.temperature_c}°C for {location}")
    return weather