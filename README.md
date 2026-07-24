# AGNT5 Starter Templates

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Starter templates for building durable AI workflows on AGNT5 in Python and TypeScript. Clone, configure, deploy.

This repo contains starter templates for **Python** and **TypeScript**. See the [**Python**](python/) and [**TypeScript**](typescript/) subfolders for language-specific setup and per-template walkthroughs.

> [!IMPORTANT]
> Templates run on the **AGNT5 CLI**. Install it before running any sample:
> ```bash
> # curl
> curl -LsSf https://agnt5.com/cli.sh | bash
>
> # or Homebrew
> brew install agnt5/tap/agnt5
> ```

## Getting Started

**Prerequisites:**
- Python 3.12+ (for Python templates), Node.js 22+ (for TypeScript templates), and/or Go 1.23+ (for Go templates)
- [Docker](https://docs.docker.com/get-started/get-docker/)
- AGNT5 CLI (see callout above)

### Create from a template

```bash
agnt5 create --template <template-name> my-project
cd my-project
```

### Run locally

```bash
agnt5 dev up
```

Open the Dev Dashboard at `http://localhost:34180` to see logs and traces.

### Execute a workflow

```bash
agnt5 run <workflow-name> --input '{"key": "value"}'
```

## Templates

| Template | Languages | Description |
|----------|-----------|-------------|
| `quickstart` | Python, TypeScript, Go | Fan-out workflow that summarizes the top Hacker News stories |
| `weather-agent` | Python, TypeScript, Go | Weather agent with Open-Meteo integration |
| `code_reviewer` | Python, TypeScript, Go | AI-powered code review with GitHub and Jira/Linear integration |
| `coding_agent` | Python, TypeScript, Go | Autonomous TDD agent running in an E2B sandbox |
| `travel_booking_customer_service` | Python, TypeScript, Go | Multi-agent travel booking assistant |
| `tutor_agent` | Python, TypeScript, Go | Multi-subject tutor with specialized handoffs |
| `hitl_deep_research` | Python, TypeScript, Go | Research pipeline with a human-in-the-loop approval gate |

See [`templates.json`](templates.json) for the authoritative manifest.

## Repository Structure

```
├── python/         # Python templates (uv + pyproject.toml)
├── typescript/     # TypeScript templates (pnpm + tsx)
├── templates.json  # Manifest used by the CLI and release pipeline
└── README.md
```

Each template includes:
- Working code you can run locally
- `agnt5.yaml` deployment manifest
- README with setup and customization notes

## SDKs and Documentation

- [AGNT5 Documentation](https://www.agnt5.com/docs)
- [AGNT5 Python SDK](https://github.com/agnt5/agnt5)
- [AGNT5 TypeScript SDK](https://www.npmjs.com/package/@agnt5/sdk)

## Contributing

Found a bug? Want to add a template? [Open an issue](https://github.com/agnt5dev/templates/issues) or submit a PR.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

These templates are alpha-grade and intended for demonstration and as starting points for your own projects. They are not production-ready as shipped — review and harden before deploying to production workloads.
