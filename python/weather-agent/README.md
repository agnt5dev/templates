# Weather Agent

> Build intelligent weather assistants that answer natural language queries using real-time data.

## Quick Start

```bash
agnt5 create --template python/weather-agent
cd weather-agent
agnt5 dev up
```

## What You Can Build

- **Conversational Weather Bots**: Chat-based agents that understand "What's the weather like in Tokyo?" and respond naturally
- **Weather Data Pipelines**: Automated workflows that fetch, process, and route weather information across systems
- **Location-Aware Apps**: Services that provide weather context for travel planning, event scheduling, or logistics

## Installation

### Prerequisites

- Python 3.12+
- AGNT5 SDK
- No API keys required (uses free Open-Meteo API)

### Setup

```bash
# Clone or create from template
agnt5 create --template python/weather-agent
cd weather-agent

# Install dependencies
uv sync

# Start the platform and worker
agnt5 dev up
```

The worker auto-starts with the platform. Check startup logs for the assigned port.

## Usage

### Via Workflow Client

Call the workflow programmatically:

```python
import asyncio
from weather_agent.workflows import get_weather
from agnt5 import with_entity_context

@with_entity_context
async def main():
    result = await get_weather(location="London")

    print(f"Location: {result.location}")
    print(f"Temperature: {result.temperature_c}°C ({result.temperature_f}°F)")
    print(f"Humidity: {result.humidity}%")
    print(f"Wind Speed: {result.wind_kph} km/h")
    print(f"Conditions: {result.condition}")

asyncio.run(main())
```

### Example Output

The `get_weather` workflow returns structured data:

```python
WeatherData(
    location="London, United Kingdom",
    temperature_c=15.2,
    temperature_f=59.4,
    humidity=65,
    wind_kph=12.5,
    wind_mph=7.8,
    condition="Partly cloudy",
    feels_like_c=14.1,
    feels_like_f=57.4,
    uv_index=3,
    visibility_km=10.0
)
```

The `get_weather_interactive` workflow returns natural language:
```
"The weather in London is currently 15°C (59°F) with partly cloudy skies.
Humidity is at 65% with light winds at 12 km/h. It feels like 14°C."
```

## Configuration

### Environment Variables

No API keys required! This template uses the free [Open-Meteo API](https://open-meteo.com).

### Workflow Parameters

```python
# Simple workflow - returns structured data
get_weather(
    location: str  # City name, coordinates, or postal code
) -> WeatherData

# Interactive workflow - returns natural language
get_weather_interactive(
    message: str  # Natural language query
) -> str
```

### Customization

Edit `src/weather_agent/config.py`:

```python
SERVICE_NAME = "weather-agent"
SERVICE_VERSION = "1.0.0"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
```

Edit `src/weather_agent/agents.py`:

```python
weather_agent = Agent(
    name="weather-agent",
    model="openai/gpt-4o-mini",       # Change to any supported model
    instructions="...",                # Customize agent behavior
    temperature=0.1,                   # Adjust creativity (0.0-1.0)
    tools=[get_weather_data_tool],
)
```

<details>
<summary>Architecture</summary>

### Component Overview

The weather agent demonstrates a clean separation between agent-based chat and function-based workflows.

#### 1. Agent (`agents.py`)

Conversational AI that handles natural language:

```python
weather_agent = Agent(
    name="weather-agent",
    model="openai/gpt-4o-mini",
    instructions="Get weather data for a location...",
    tools=[get_weather_data_tool],
    temperature=0.1,
)
```

**Capabilities:**
- Understands location queries in natural language
- Maintains conversation context across messages
- Returns formatted, human-readable responses
- Automatically calls tools when needed

#### 2. Tools (`tools.py`)

Bridge between the agent and weather data:

```python
@tool(auto_schema=True)
async def get_weather_data_tool(ctx: Context, location: str) -> WeatherData:
    """Fetch weather data for a location."""
    fun_ctx = FunctionContext(run_id=ctx.run_id)
    return await get_weather_data(fun_ctx, location)
```

**Purpose:**
- Provides agent-callable interface to functions
- Handles context translation between agents and functions
- Returns structured data for agent interpretation

#### 3. Functions (`functions.py`)

Core weather fetching logic:

```python
@function(name="get_weather_data")
async def get_weather_data(ctx: FunctionContext, location: str) -> WeatherData:
    """Fetch weather data with built-in retry logic.

    Steps:
    1. Geocode location → coordinates
    2. Fetch weather data for coordinates
    3. Parse and structure response
    """
```

**Features:**
- Built-in retry mechanism via AGNT5
- Geocoding with Open-Meteo API
- Real-time weather data fetching
- Structured output via Pydantic models

#### 4. Workflows (`workflows.py`)

Two workflows for different use cases:

**Simple Workflow** - Direct function call:
```python
@workflow(name="get_weather")
async def get_weather(ctx: WorkflowContext, location: str) -> WeatherData:
    """Returns structured weather data."""
    weather = await ctx.task(get_weather_data, location)
    return weather
```

**Interactive Workflow** - Chat-enabled:
```python
@workflow(name="get_weather_interactive", chat=True)
async def get_weather_interactive(ctx: WorkflowContext, message: str) -> str:
    """Returns natural language response with conversation history."""
    result = await weather_agent.run(message, context=ctx)
    return result.output
```

The `chat=True` parameter:
- Exposes workflow as a chat endpoint
- Maintains conversation history in workflow entity
- Enables multi-turn conversations

#### 5. Models (`models.py`)

Type-safe data structures:

```python
class WeatherData(BaseModel):
    location: str
    temperature_c: float
    temperature_f: float
    humidity: int
    wind_kph: float
    wind_mph: float
    condition: str
    feels_like_c: float
    feels_like_f: float
    uv_index: int
    visibility_km: float
```

**Benefits:**
- Runtime validation
- Type hints for IDEs
- Automatic JSON serialization
- Clear data contracts

#### 6. Worker (`app.py`)

Registers all components with AGNT5:

```python
worker = Worker(
    service_name="weather-agent",
    auto_register=True,  # Discovers all @function, @workflow, @tool, Agent
    metadata={"description": "Simple weather agent..."},
)
await worker.run()
```

**Auto-discovery:**
- Scans source paths in `pyproject.toml`
- Registers all decorated components
- No manual registration needed

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                           │
└─────────────────────────────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
        ┌───────▼─────────┐      ┌───────▼─────────┐
        │  Simple Workflow │      │ Chat Workflow   │
        │   (get_weather)  │      │  (interactive)  │
        └───────┬──────────┘      └────────┬────────┘
                │                          │
                │                    ┌─────▼─────┐
                │                    │   Agent   │
                │                    │ (interprets│
                │                    │  + calls   │
                │                    │   tool)    │
                │                    └─────┬─────┘
                │                          │
                │                    ┌─────▼─────┐
                │                    │   Tool    │
                │                    └─────┬─────┘
                │                          │
                └──────────┬───────────────┘
                           │
                    ┌──────▼──────┐
                    │  Function   │
                    │ (geocode +  │
                    │  fetch API) │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Open-Meteo  │
                    │     API     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ WeatherData │
                    │   Model     │
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                │                     │
        ┌───────▼─────────┐   ┌──────▼──────┐
        │ Structured Data │   │  Natural    │
        │  (JSON/Pydantic)│   │  Language   │
        └─────────────────┘   └─────────────┘
```

### Workflow Comparison

| Feature | `get_weather` | `get_weather_interactive` |
|---------|---------------|---------------------------|
| Input | Location string | Natural language message |
| Output | WeatherData model | Human-readable string |
| Use Case | Programmatic API calls | Chat interfaces |
| Context | Stateless | Conversation history |
| Endpoint | Standard workflow | Chat endpoint (`/api/chat/weather-agent`) |

</details>

## Troubleshooting

### "Location not found" error
```
ValueError: Could not find location: XYZ
```
**Solution**: The geocoding API couldn't find the location. Try:
- Use more specific names: "Paris, France" instead of "Paris"
- Check spelling: "New York" not "Newyork"
- Use major cities or well-known locations

### Import errors
```
ModuleNotFoundError: No module named 'weather_agent'
```
**Solution**: Ensure dependencies are installed:
```bash
uv sync  # or: pip install -e .
```

### Platform connection issues
```
ConnectionError: Could not connect to AGNT5 Coordinator
```
**Solution**: Verify AGNT5 platform is running:
```bash
agnt5 dev status  # Check status
agnt5 dev up      # Start platform
```

### API rate limiting
Open-Meteo is free and has generous rate limits. If you hit limits:
- Wait a few seconds before retrying
- Consider caching results for repeated locations
- For production, review [Open-Meteo's terms](https://open-meteo.com/en/terms)

## Customization

### Add Forecast Data

Modify `functions.py` to fetch 7-day forecasts:

```python
@function(name="get_weather_forecast")
async def get_weather_forecast(ctx: FunctionContext, location: str, days: int = 7):
    # Fetch coordinates
    coords = await _geocode_location(location)

    # Add forecast parameter to API call
    params = {
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": days,
    }
    # ... implementation
```

### Add Weather Alerts

Create a new tool for severe weather warnings:

```python
@tool(auto_schema=True)
async def get_weather_alerts(ctx: Context, location: str) -> list:
    """Fetch active weather alerts for a location."""
    # Implementation using weather alerts API
    pass
```

Update `agents.py`:
```python
weather_agent = Agent(
    name="weather-agent",
    tools=[get_weather_data_tool, get_weather_alerts],  # Add new tool
)
```

### Support Multiple Locations

Extend the workflow to handle batch queries:

```python
@workflow(name="get_weather_batch")
async def get_weather_batch(ctx: WorkflowContext, locations: list[str]):
    """Fetch weather for multiple locations in parallel."""
    tasks = [ctx.task(get_weather_data, loc) for loc in locations]
    results = await ctx.parallel(*tasks)
    return results
```

### Switch Weather Provider

Replace Open-Meteo with another API in `functions.py`:

```python
# Update API endpoint
WEATHER_API_URL = "https://api.weatherapi.com/v1/current.json"

# Add API key if required
api_key = os.getenv("WEATHER_API_KEY")

# Modify request and response parsing
```

### Related Templates

- **code_reviewer**: AI-powered code review with security and quality analysis
- **coding_agent_agnt5**: Autonomous TDD agent that writes and tests code
- **text-to-sql**: Multi-step reasoning workflows with validation

### Integration Ideas

- **Slack/Discord Bot**: Connect `get_weather_interactive` to messaging platforms
- **Voice Assistant**: Integrate with speech-to-text for voice queries
- **Mobile App**: Use the REST API from iOS/Android apps
- **IoT Devices**: Trigger workflows from smart home systems

## License

MIT License - see [LICENSE](LICENSE) for details
