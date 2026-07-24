# Code Reviewer Agent (Go)

An AI-powered code review agent that analyzes GitHub pull requests and linked tickets to deliver comprehensive, context-aware reviews.

## What it does

- **Review pull requests** — Fetches PR diffs from GitHub and reviews every changed file for correctness, quality, and security issues.
- **Align with tickets** — Cross-references the PR against a linked Jira or Linear ticket to flag missing requirements.
- **Produce a merge recommendation** — Synthesizes all findings into a Markdown report with an APPROVE / REQUEST CHANGES / BLOCK verdict.

## Key concepts

- **Context builder + reviewer agents** — One agent gathers PR/ticket context using tools (`pr_fetcher`, `jira_ticket_fetcher`, `linear_ticket_fetcher`); a second agent synthesizes the final report.
- **Parallel per-file review** — Each changed file is reviewed independently, all in parallel, alongside a cross-file security review, wrapped in a single `agnt5.Step` (the Go SDK has no per-item fan-out helper yet).
- **Structured output without `response_format`** — The Go SDK's `GenerateRequest` has no schema field, so `GenerateStructured` (see `utils.go`) prompts the model for raw JSON matching a documented shape, unmarshals it, and retries once with an error-correction follow-up on a parse failure.
- **Manual retry/backoff** — External API calls (GitHub, Jira, Linear) use a small exponential-backoff helper (`retryWithBackoff`) rather than the SDK's component-level `WithRetry`, since these are plain Go function calls from inside a tool handler, not separately registered components.

## Project structure

```
main.go                  # entry point: loads config, builds the model/agents, registers components, runs the worker
src/code_reviewer/         # implementation package (mirrors Python's src/<package>/, TypeScript's src/)
  models.go                 # Finding, FileReview, SecurityReview, TechStack, PRData, TicketData
  config.go                 # environment-variable configuration and validation
  utils.go                  # ADF parsing, retryWithBackoff, GenerateStructured
  tools.go                  # pr_fetcher, jira_ticket_fetcher, linear_ticket_fetcher, detect_ticket_source
  agents.go                 # the context-builder and reviewer agents
  functions.go               # PR fetch, tech-stack detection, per-file review, security review
  workflow.go                # the code review orchestration workflow
```

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/code_reviewer my-code-reviewer
   cd my-code-reviewer
   ```

3. Download dependencies:
   ```bash
   go mod download
   ```

4. Set up environment variables (`GITHUB_TOKEN` and `OPENAI_API_KEY` are required; at least one of Jira or Linear credentials is required):
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```
