"""Weather Agent - Simple AGNT5 Template.

A minimal weather agent demonstrating AGNT5 core concepts:
- Functions for reusable operations
- Workflows for orchestration
- Models for type-safe data structures

Example usage:

    from weather_agent import get_weather

    result = await get_weather(location="London")
    print(f"{result.location}: {result.temperature_c}°C")
"""

from weather_agent.workflows import get_weather
from weather_agent.functions import get_weather_data
from weather_agent.models import WeatherData
from weather_agent.config import config

__version__ = "1.0.0"

__all__ = [
    # Workflow
    "get_weather",
    # Function
    "get_weather_data",
    # Model
    "WeatherData",
    # Config
    "config",
]
