# Weather Agent

An intelligent weather assistant that answers natural language queries using real-time data from the free Open-Meteo API.

## What it does

- **Answer natural language queries** — "What's the weather like in Tokyo?" gets a conversational, formatted response.
- **Return structured data** — A separate workflow returns typed weather data for programmatic use (dashboards, pipelines, etc.).
- **Geocode any location** — Accepts city names, coordinates, or postal codes; no API key required.

## Key concepts

- **Agent + tool + function layering** — `weather_agent` (chat) calls `get_weather_data_tool`, which delegates to the `get_weather_data` function for the actual geocode-and-fetch logic.
- **Two workflows, one function** — `get_weather` returns structured `WeatherData` directly; `get_weather_interactive` (`chat=True`) routes the same request through the agent for a natural-language reply.

## Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template python/weather-agent my-weather-agent
   cd my-weather-agent
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```
