# AGNT5 Starter Templates

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Starter templates for building durable AI workflows on AGNT5. Clone, configure, deploy.

## Getting Started

**Prerequisites:**
- Python 3.10+
- [Docker](https://docs.docker.com/get-started/get-docker/)

### Install the CLI

```bash
# curl
curl -LsSf https://agnt5.com/cli.sh | bash

# or Homebrew
brew install agnt5/tap/agnt5
```

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

| Template | Description |
|----------|-------------|
| `quickstart` | Minimal workflow with checkpoints and logging |

*More templates coming soon*

## Repository Structure

```
├── python/
│   ├── quickstart/
│   │   ├── src/
│   │   │   └── main.py
│   │   └── README.md
│   └── README.md
└── README.md
```

Each template includes:
- Working code you can run locally
- Configuration for AGNT5 deployment
- README with setup and customization notes

## Contributing

Found a bug? Want to add a template? Open an issue or submit a PR.

## Help

- [AGNT5 Documentation](https://www.agnt5.com/docs)
- [GitHub Issues](https://github.com/agnt5dev/templates/issues)

## License

MIT - see [LICENSE](LICENSE)
