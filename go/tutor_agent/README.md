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

## Run your workers

`agnt5 dev` runs a worker on your machine while you build. To keep the tutor running, run its worker on a host you choose, such as Railway or a server of your own. The worker connects out to AGNT5, so the host needs no public URL or open port.

A project made with `agnt5 create` is already linked to AGNT5. If you cloned this repository instead, run `agnt5 init` in it first to link it to a new or existing project.

1. In Studio, open the project's **Settings → Environments**. Open an environment's **⋯** menu, choose **Run your own workers**, select **Connect**, then **Create key** and copy the key.
2. On your host, set:
   - `AGNT5_ENVIRONMENT` to the environment's name.
   - `AGNT5_API_KEY_FILE` to the path of a file that holds only the key. Keep the key in your host's secret settings, not in the code.
   - `OPENAI_API_KEY`, in the host's secret settings too. The template's `.gitignore` lists `.env`, so the key in that file stays on your machine.
3. Install the dependencies with `go mod download`, start the worker with `go run .`, and keep it running. It shows on the project's **Workers** page once it connects.

[Run workers on your own host](https://agnt5.com/docs/run/self-hosted-workers) covers each setting, and [Run workers on Railway](https://agnt5.com/docs/integrations/railway-workers) walks through one host.

Then ask it a question in that environment:

```bash
agnt5 run agent triage_tutor --env <environment> --input '{"message":"What is 2+2?"}'
```

Without the key, runs fail with OpenAI's 401 error, `You didn't provide an API key`.
