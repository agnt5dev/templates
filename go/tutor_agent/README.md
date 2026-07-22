# AI Tutor Agent — AGNT5 Template (Go)

A multi-subject educational assistant that routes student questions to specialized tutors using the agent handoff pattern.

## What it does

- **Triage** — A triage agent analyzes the incoming question and detects the subject area (history, math, or general).
- **Handoff** — Control is transferred to the appropriate specialist agent, which provides a focused, expert response.
- **Specialize** — A history tutor and a math tutor each have dedicated instructions tailored to their domain.

## Key concepts

- **Agent handoffs** — The triage agent uses `agnt5.NewHandoff(agent, opts...)` to build a transfer target, passed to `WithAgentHandoffs`. The specialist handles the question end-to-end and returns the final response.
- **Explicit registration** — Go has no auto-discovery: every agent and workflow is registered explicitly in `main()` via `agnt5.RegisterAgent`/`agnt5.RegisterWorkflow`.

## Project structure

```
main.go                # entry point: builds the model/agents, registers components, runs the worker
src/tutor_agent/        # implementation package (mirrors Python's src/<package>/, TypeScript's src/)
  agents.go              # the triage, history, and math tutor agents
  workflows.go           # the tutor chat workflow
```

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/tutor_agent my-tutor
   cd my-tutor
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
