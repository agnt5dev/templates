# Hacker News digest — AGNT5 quickstart

A fan-out workflow that summarizes the top Hacker News stories, with every step visible live in Studio and durable across restarts.

## What it does

- **Fetch top stories** — Pulls the current top Hacker News story IDs, then fetches each story in parallel.
- **Summarize in parallel** — Each story is summarized independently using an LLM, then assembled into a single digest.
- **Resume on crash** — Kill the worker mid-run and restart it; completed steps stay completed, only the missing ones re-run.

## Key concepts

- **Durable checkpointing** — Every `ctx.task(...)` call is a checkpoint. Side effects go through `ctx.task` so the runtime can skip them on replay.
- **Fan-out / fan-in** — `fetch_story` and `summarize` run once per story, in parallel, before `assemble_digest` combines the results.

## Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template python/quickstart my-digest
   cd my-digest
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev
   ```

   The terminal prints a Studio URL. Open it, pick the `digest` workflow, set the input to `{"limit": 5}`, and click **Run**.
