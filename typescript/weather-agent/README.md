# Weather Agent (TypeScript)

An intelligent weather assistant that answers natural language queries using real-time data from the free Open-Meteo API.

## What it does

- **Answer natural language queries** — "What's the weather like in Tokyo?" gets a conversational, formatted response.
- **Return structured data** — A separate workflow returns typed weather data for programmatic use (dashboards, pipelines, etc.).
- **Geocode any location** — Accepts city names, coordinates, or postal codes; no API key required.

## Key concepts

- **Agent + tool + function layering** — the weather agent (chat) calls `getWeatherDataTool`, which delegates to the `getWeatherData` function for the actual geocode-and-fetch logic.
- **Two workflows, one function** — `getWeather` returns a structured `WeatherData` object directly; `getWeatherInteractive` routes the same request through the agent for a natural-language reply.

## Setup

1. Install Node.js 22+:
   ```bash
   node --version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template typescript/weather-agent my-weather-agent
   cd my-weather-agent
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Start the AGNT5 dev server (no API keys required):
   ```bash
   agnt5 dev up
   ```
