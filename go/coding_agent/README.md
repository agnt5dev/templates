# Coding Agent (Go)

An autonomous test-driven development agent that writes, tests, and iteratively fixes Python code until all tests pass, using an E2B sandbox for execution.

## What it does

- **Plan then build** — Generates a synchronized dev plan and test plan from a task description before writing any code.
- **Test-driven iteration** — Writes tests first, then code; on failure, analyzes the pytest output and fixes the code, up to `max_retries` times (default 15).
- **Sandboxed execution** — Runs and tests all generated code inside an isolated E2B sandbox, never on the worker host.

## Key concepts

- **Multi-node workflow** — Planner → (test generator → code generator) or (error analyzer → code generator) → sync → install deps → executor → final response. Each node is wrapped in `agnt5.Step`, which derives its checkpoint key from the step name plus a call-count index — the same step name inside the retry loop gets a fresh checkpoint every iteration automatically.
- **Structured error feedback loop** — Each failed pytest run is parsed into a structured `ErrorAnalysis` that drives the next fix iteration, rather than regenerating code from scratch.
- **Structured output without `response_format`** — The Go SDK's `GenerateRequest` has no schema field, so `GenerateStructured` (see `utils.go`) prompts the model for raw JSON matching a documented shape, unmarshals it, and retries once with an error-correction follow-up on a parse failure.
- **Hand-written E2B client** — There's no E2B Go SDK and `agnt5.NewHTTPSandbox` speaks AGNT5's own protocol, not E2B's, so `e2b.go` implements a small client directly against E2B's public HTTP API: sandbox lifecycle via E2B's documented control-plane API, and command/file operations via the sandbox's envd HTTP surface. envd's real interface is richer than shown here (it supports streaming process output); this implements a simplified synchronous wrapper — verify against [E2B's docs](https://e2b.dev/docs) and adjust endpoints if needed before relying on this in production.

## Project structure

```
main.go               # entry point: loads config, builds the model/E2B client, registers the workflow, runs the worker
src/coding_agent/       # implementation package (mirrors Python's src/<package>/, TypeScript's src/)
  models.go              # Plan, GeneratedCode, ErrorAnalysis, ExecutionResult, WorkflowResult
  config.go              # environment-variable configuration and validation
  utils.go               # code cleanup, import scanning, GenerateStructured
  e2b.go                 # the hand-written E2B sandbox client
  functions.go            # planner, coder, tester, error analyzer, and doc-writer nodes
  workflow.go             # the plan -> generate -> sync -> test -> fix retry loop
```

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/coding_agent my-coding-agent
   cd my-coding-agent
   ```

3. Download dependencies:
   ```bash
   go mod download
   ```

4. Set up environment variables (`GROQ_API_KEY` and `E2B_API_KEY` are required):
   ```bash
   cp .env.example .env
   ```

   Get keys at: https://console.groq.com/keys and https://e2b.dev/dashboard

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```
