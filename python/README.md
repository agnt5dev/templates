# Python Templates for AGNT5

Starter templates for building durable AI agents with the [AGNT5 Python SDK](https://github.com/agnt5/agnt5).

> [!IMPORTANT]
> All templates assume the [AGNT5 CLI](https://www.agnt5.com/docs) is installed. See the [repo root README](../README.md) for install instructions.

## Prerequisites

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- [Docker](https://docs.docker.com/get-started/get-docker/) — required by `agnt5 dev`

## Available templates

| Template | Description |
|----------|-------------|
| [`quickstart`](quickstart/) | Fan-out workflow that summarizes the top Hacker News stories |
| [`deep-wiki-agent`](deep-wiki-agent/) | Durable investigator agent with DeepWiki MCP, human review, and a checkpointed save step |
| [`weather-agent`](weather-agent/) | Weather agent with OpenWeatherMap integration |
| [`code_reviewer`](code_reviewer/) | AI-powered code review with GitHub and Jira integration |
| [`coding_agent`](coding_agent/) | Autonomous TDD agent running in an E2B sandbox |
| [`customer_service`](customer_service/) | Multi-agent travel booking assistant |
| [`deep_research`](deep_research/) | Autonomous research agent with Wikipedia sourcing |
| [`tutor_agent`](tutor_agent/) | Multi-subject tutor with specialized handoffs |

Each template directory has its own README with template-specific setup.

## Running a template

```bash
cd <template-name>
uv sync                             # install dependencies
cp .env.example .env                # if present — fill in API keys
agnt5 dev                           # start the local AGNT5 platform
agnt5 run <workflow-name> --input '{"key": "value"}'
```

The Dev Dashboard is at `http://localhost:34180`.

## Resources

- [AGNT5 Documentation](https://www.agnt5.com/docs)
- [Python SDK on GitHub](https://github.com/agnt5/agnt5)
