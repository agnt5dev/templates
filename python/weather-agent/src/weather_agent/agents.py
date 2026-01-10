"""Weather agent definition."""

from agnt5 import Agent

from weather_agent.tools import get_weather_data_tool


weather_agent = Agent(
    name="weather-agent",
    model="openai/gpt-4o-mini",
    instructions="Get weather data for a location, if a generic question is posed, just answer the question with your knowledge",
    tools=[get_weather_data_tool],
    temperature=0.1,
)
