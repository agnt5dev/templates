# TypeScript Templates for AGNT5

Starter templates for building durable AI agents with the [AGNT5 TypeScript SDK](https://www.npmjs.com/package/@agnt5/sdk).

> [!IMPORTANT]
> All templates assume the [AGNT5 CLI](https://www.agnt5.com/docs) is installed. See the [repo root README](../README.md) for install instructions.

## Prerequisites

- Node.js **22+**
- `npm` or `pnpm`
- [Docker](https://docs.docker.com/get-started/get-docker/) — required by `agnt5 dev`

## Available templates

| Template | Description |
|----------|-------------|
| [`quickstart`](quickstart/) | Fan-out workflow that summarizes the top Hacker News stories |
| [`weather-agent`](weather-agent/) | Weather agent with Open-Meteo integration |
| [`code_reviewer`](code_reviewer/) | AI-powered code review with GitHub and Jira/Linear integration |
| [`coding_agent`](coding_agent/) | Autonomous TDD agent running in an E2B sandbox |
| [`travel_booking_customer_service`](travel_booking_customer_service/) | Multi-agent travel booking assistant |
| [`tutor_agent`](tutor_agent/) | Multi-subject tutor with specialized handoffs |
| [`hitl_deep_research`](hitl_deep_research/) | Research pipeline with a human-in-the-loop approval gate |

Not published — internal samples that the sync skips:

| Template | Description |
|----------|-------------|
| [`llm-playground`](llm-playground/) | Model and provider checks |

## Running a template

```bash
cd <template-name>
npm install                          # or: pnpm install
cp .env.example .env                 # if present — fill in API keys
agnt5 dev                            # start the local AGNT5 platform
```

The terminal prints a Studio URL. Open it in your browser, pick a workflow, set its input, and click **Run**.

## Resources

- [AGNT5 Documentation](https://www.agnt5.com/docs)
- [TypeScript SDK on npm](https://www.npmjs.com/package/@agnt5/sdk)
