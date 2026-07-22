# Weather Agent (Go)

An intelligent weather assistant that answers natural language queries using real-time data from the free Open-Meteo API.

## What it does

- **Answer natural language queries** — "What's the weather like in Tokyo?" gets a conversational, formatted response.
- **Return structured data** — A separate workflow returns typed `WeatherData` for programmatic use (dashboards, pipelines, etc.).
- **Geocode any location** — Accepts city names; no API key required for the weather data itself.

## Key concepts

- **Agent + tool + function layering** — `weatherAgent` calls a `get_weather_data_tool`, which delegates to the same `fetchWeatherData` helper used by the plain `get_weather_data` function.
- **Two workflows, one helper** — `get_weather` returns structured `WeatherData` directly; `get_weather_interactive` routes the same request through the agent for a natural-language reply, keeping conversation history in session-scoped memory (`ctx.Memory().Conversation()`).
- **Explicit registration** — Go has no auto-discovery: every function, agent, and workflow is registered explicitly in `main()`.

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/weather-agent my-weather-agent
   cd my-weather-agent
   ```

3. Download dependencies:
   ```bash
   go mod download
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```
