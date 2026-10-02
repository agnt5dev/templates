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

1. Install Go 1.26.5+ (required by `github.com/agnt5dev/sdk-go`):
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

## Deploy

`agnt5 deploy` leaves `.env` out of the upload, so a deployed project needs the key as a project secret.

1. Add `OPENAI_API_KEY` as a secret, in Studio under **Settings → Secrets**, or from the project directory:
   ```bash
   agnt5 secrets set --name OPENAI_API_KEY --type api_key
   ```
   The CLI prompts for the value without echoing it. To pipe the value in instead, add `--stdin`.

2. Deploy:
   ```bash
   agnt5 deploy
   ```
   This creates a preview deployment, which stops after an hour. Add `--env production` to deploy to production.

A deployment reads its secrets when it starts. If you add or change the key while a deployment is running, run `agnt5 deploy` again to pick it up.

Without the key, runs fail with OpenAI's 401 error, `You didn't provide an API key`.
