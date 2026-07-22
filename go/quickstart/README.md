# Hacker News digest — AGNT5 quickstart (Go)

A fan-out workflow that summarizes the top Hacker News stories, with every step visible live in Studio and durable across restarts.

## What it does

- **Fetch top stories** — Pulls the current top Hacker News story IDs, then fetches each story concurrently.
- **Summarize in parallel** — Each story is summarized independently using an LLM, then assembled into a single digest.
- **Resume on crash** — Kill the worker mid-run and restart it; completed steps stay completed, only the missing ones re-run.

## Key concepts

- **Durable checkpointing** — Every `agnt5.Step(ctx, name, func(context.Context) (T, error))` call is a checkpoint. Side effects go through `agnt5.Step` so the runtime can skip them on replay.
- **Fan-out / fan-in** — `fetch_stories` and `summarize_stories` each spawn one goroutine per story and wait for all of them, wrapped in a single `agnt5.Step` so the whole group checkpoints together (the Go SDK has no per-item fan-out helper yet, unlike Python's `ctx.parallel()`/TypeScript's `Promise.all`), before `assemble_digest` combines the results.
- **Explicit registration** — Unlike Python's `auto_register=True` or TypeScript's import-side-effect registration, Go has no auto-discovery: every function and workflow is registered explicitly in `main()` via `agnt5.RegisterFunction`/`agnt5.RegisterWorkflow`.

## Project structure

```
main.go              # entry point: builds the model/agent, registers components, runs the worker
src/quickstart/       # implementation package (mirrors Python's src/<package>/, TypeScript's src/)
  functions.go        # fetch_top_ids, fetch_story, summarize, assemble_digest
  workflows.go        # the digest workflow
```

`main.go` imports `src/quickstart` and calls its exported functions/types — Go has no package-private cross-file sharing the way a single flat directory would, so anything `main.go` needs (the `Summarizer` agent, the registered handlers) is exported with a capital letter.

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/quickstart my-digest
   cd my-digest
   ```

3. Download dependencies:
   ```bash
   go mod download
   ```

4. Set up environment variables (uses OpenAI by default; set `ANTHROPIC_API_KEY` and update the model in `main.go`'s `newSummarizerModel` to use Anthropic instead):
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev
   ```

   The terminal prints a Studio URL. Open it, pick the `digest` workflow, set the input to `{"limit": 5}`, and click **Run**.
