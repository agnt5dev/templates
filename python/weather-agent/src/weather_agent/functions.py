"""Functions and tools for the weather agent."""

import httpx
from agnt5 import function, tool, FunctionContext, Context

from weather_agent.models import WeatherData
from weather_agent.config import config


async def _fetch_weather_data(location: str) -> WeatherData:
    """Fetch weather data for a location.

    Args:
        location: City name

    Returns:
        WeatherData: Weather information
    """
    async with httpx.AsyncClient() as client:
        # Geocode the location to get coordinates
        geo_response = await client.get(
            config.GEOCODING_API_URL,
            params={"name": location, "count": 1},
            timeout=10.0,
        )
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if not geo_data.get("results"):
            raise ValueError(f"Location not found: {location}")

        place = geo_data["results"][0]
        latitude = place["latitude"]
        longitude = place["longitude"]

        # Fetch weather using coordinates
        weather_response = await client.get(
            config.WEATHER_API_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            },
            timeout=10.0,
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()

    current = weather_data["current"]
    temp_c = current["temperature_2m"]

    return WeatherData(
        location=place["name"],
        latitude=latitude,
        longitude=longitude,
        temperature_c=temp_c,
        temperature_f=temp_c * 9 / 5 + 32,
        humidity=current["relative_humidity_2m"],
        wind_kph=current["wind_speed_10m"],
        country=place.get("country"),
        region=place.get("admin1"),
    )


@function(name="get_weather_data")
async def get_weather_data(ctx: FunctionContext, location: str) -> WeatherData:
    """Fetch weather data for a location.

    Args:
        ctx: Function context
        location: City name

    Returns:
        WeatherData: Weather information
    """
    return await _fetch_weather_data(location)



