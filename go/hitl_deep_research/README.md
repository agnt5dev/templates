# HITL Deep Research — AGNT5 Template (Go)

A research pipeline that combines three specialized AI agents with a **human-in-the-loop approval gate** before any research begins.

## What it does

1. **Plan** — A scoping agent analyzes your topic and produces a structured research plan.
2. **Approve** — The workflow pauses and presents the plan to you. You can approve it, edit it, or reject it. This pause is durable — it survives restarts and waits as long as needed.
3. **Research** — A research agent executes the approved plan using web and Wikipedia tools.
4. **Write** — A writing agent synthesizes the findings into a polished report.

## Key concepts

- **Human-in-the-loop (HITL)** — `ctx.AskUser(...)` suspends the workflow at a checkpoint and resumes only after a human responds. Its first call returns a `*WaitingForUserInputError` that the workflow propagates as its own return error so the runtime can suspend the run; on resume, the same call returns the recorded answer directly.
- **Durable workflows** — Each stage is wrapped in `agnt5.Step`. If the worker restarts mid-run, the workflow replays from the last completed step without repeating side effects.
- **Specialized agents** — Scoping, Research, and Writing agents each have a focused role, keeping concerns cleanly separated.

## Project structure

```
main.go                       # entry point: builds the model/agents, registers components, runs the worker
src/hitl_deep_research/         # implementation package (mirrors Python's src/<package>/, TypeScript's src/)
  tools.go                       # fetch_webpage_tool and wikipedia_search_tool
  agents.go                      # the scoping, research, and writing agents
  functions.go                   # plan/conduct/write pipeline stages
  workflows.go                   # the HITL-gated research workflow
```

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/hitl_deep_research my-deep-research
   cd my-deep-research
   ```

3. Download dependencies:
   ```bash
   go mod download
   ```

4. Set up environment variables:
   ```bash
   cat > .env << EOF
   OPENAI_API_KEY=your_openai_api_key_here
   EOF
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev
   ```

When the workflow reaches the approval step, open the Dev Dashboard to review and approve the research plan before research begins.
