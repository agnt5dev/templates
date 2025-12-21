# Weather Agent - Simple AGNT5 Template

A minimal weather agent built with AGNT5 that demonstrates core concepts: one function to fetch weather data and one workflow to orchestrate it.

## 🌟 What You'll Learn

This template showcases:

- **Functions** – Reusable operations with automatic retry logic
- **Workflows** – Simple orchestration to call functions
- **Models** – Type-safe data structures with Pydantic
- **Worker** – How to register and run an AGNT5 worker

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- AGNT5 Platform installed (`curl -LsSf https://agnt5.com/cli.sh | bash`)

### Installation

```bash
# 1. Navigate to the weather-agent directory
cd blueprints/weather-agent

# 2. Install dependencies
uv sync  # or: pip install -e .
```

### Running the Agent

```bash
agnt5 dev up
```

This will start the AGNT5 platform and the weather agent automatically.

## 🧪 Testing Workflows

To test the workflow, run:

```bash
python -m test
```

This will execute the workflow tests directly.
## 🧪 Running Tests


To run tests, make sure you are in the `weather-agent` directory and that dependencies are installed:

```bash
uv sync  # or pip install -e .
python -m test
```
```

## 📁 Project Structure

```
weather-agent/
├── src/
│   └── weather_agent/
│       ├── __init__.py           # Package exports
│       ├── models.py             # WeatherData model
│       ├── functions.py          # get_weather_data function
│       ├── workflows.py          # get_weather workflow
│       └── config.py             # Configuration
├── app.py                        # Worker entry point
├── pyproject.toml                # Python dependencies
└── README.md                     # This file
```

## 🔧 Core Components

### 1. Model (`models.py`)

Type-safe data structure:

```python
class WeatherData(BaseModel):
    location: str
    latitude: float
    longitude: float
    temperature_c: float
    temperature_f: float
    humidity: int
    wind_kph: float
    country: Optional[str] = None
    region: Optional[str] = None
```

### 2. Function (`functions.py`)

Fetches weather data from the Open-Meteo API:

```python
@function(
    name="get_weather_data",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def get_weather_data(ctx: FunctionContext, location: str) -> WeatherData:
    """Fetch weather data for a location."""
    # 1. Geocodes location to get coordinates
    # 2. Fetches weather using coordinates
    # Returns WeatherData model
```

### 3. Workflow (`workflows.py`)

Orchestrates the function call:

```python
@workflow(name="get_weather")
async def get_weather(ctx: WorkflowContext, location: str) -> WeatherData:
    """Fetch weather data for a location."""
    weather = await ctx.task(get_weather_data, location)
    return weather
```

### 4. Worker (`app.py`)

Registers components with AGNT5:

```python
worker = Worker(
    service_name="weather-agent",
    service_version="1.0.0",
    functions=[get_weather_data],
    workflows=[get_weather],
)
await worker.run()
```

## 💡 How It Works

1. **User provides location** → Workflow receives city name
2. **Workflow calls function** → `ctx.task(get_weather_data, location)`
3. **Function geocodes location** → Converts city name to coordinates via Open-Meteo
4. **Function fetches weather** → Gets current weather for coordinates
5. **Returns weather data** → Type-safe `WeatherData` model

## 🔑 Key AGNT5 Concepts

### Functions

Functions are reusable operations with built-in retry logic:

```python
@function(
    name="my_function",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def my_function(ctx: FunctionContext, arg: str) -> dict:
    ctx.logger.info(f"Processing: {arg}")
    return {"result": "success"}
```

### Workflows

Workflows orchestrate functions:

```python
@workflow(name="my_workflow")
async def my_workflow(ctx: WorkflowContext, input: str) -> dict:
    result = await ctx.task(my_function, input)
    return result
```

### Worker

Workers register and run your components:

```python
worker = Worker(
    service_name="my-service",
    functions=[my_function],
    workflows=[my_workflow],
)
await worker.run()
```

## 🎯 Extending This Template

You can extend this by:

1. **Adding more functions** – Create functions for data transformation, formatting, etc.
2. **Adding more workflows** – Compose multiple functions into complex workflows
3. **Adding state management** – Use `ctx.state.set()` and `ctx.state.get()` in workflows
4. **Adding error handling** – Wrap function calls in try/except blocks

## 🛠️ Development

### Adding New Features

1. Define data models in `models.py`
2. Implement functions in `functions.py`
3. Compose workflows in `workflows.py`
4. Register with worker in `app.py`

## 📚 Learn More

- **AGNT5 Documentation**: [https://agnt5.com/docs](https://agnt5.com/docs)
- **Open-Meteo API Docs**: [open-meteo.com](https://open-meteo.com/)

## 🆘 Troubleshooting

### "Location not found"

The geocoding API couldn't find the city. Try:
- Using a more common spelling
- Adding the country (e.g., "Paris, France")

### Import errors

Install dependencies:
```bash
uv sync  # or pip install -e .
```

### Platform connection issues

Make sure AGNT5 platform is running:
```bash
agnt5 dev up
```

---

**Built with ❤️ using AGNT5** | **Simple template to get started!**
