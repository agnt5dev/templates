# Go Templates for AGNT5

Starter templates for building durable AGNT5 workers in Go.

## Templates

| Template | Description |
|----------|-------------|
| `quickstart` | Fan-out workflow that summarizes the top Hacker News stories |
| `weather-agent` | Weather agent with Open-Meteo integration |
| `code_reviewer` | AI-powered code review with GitHub and Jira/Linear integration |
| `coding_agent` | Autonomous TDD agent running in an E2B sandbox |
| `travel_booking_customer_service` | Multi-agent travel booking assistant |
| `tutor_agent` | Multi-subject tutor with specialized handoffs |
| `hitl_deep_research` | Research pipeline with a human-in-the-loop approval gate |

## Prerequisites

- Go 1.26+
- AGNT5 CLI

## Run

```bash
cd quickstart
cp .env.example .env  # add your LLM API key
go mod tidy
agnt5 dev up
```
