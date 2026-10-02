# AI Tutor Agent — AGNT5 Template

A multi-subject educational assistant that routes student questions to specialized tutors using the agent handoff pattern.

## What it does

- **Triage** — A triage agent analyzes the incoming question and detects the subject area (history, math, or general).
- **Handoff** — Control is transferred to the appropriate specialist agent, which provides a focused, expert response.
- **Specialize** — A history tutor and a math tutor each have dedicated instructions tailored to their domain.

## Key concepts

- **Agent handoffs** — The triage agent uses `handoff()` to transfer the conversation to a specialist. The specialist handles the question end-to-end and returns the final response.

## Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template python/tutor_agent my-tutor
   cd my-tutor
   ```

3. Install dependencies:
   ```bash
   uv sync
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

The template's `.gitignore` lists `.env`, so `agnt5 deploy` leaves that file out of the upload. A deployed project reads the key from a project secret instead.

A project made with `agnt5 create` is already linked to AGNT5. If you cloned this repository instead, run `agnt5 init` in it first. It links the directory to a new or existing project, which `agnt5 secrets set` and `agnt5 deploy` both need.

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

A deployment reads its secrets when it starts. After you add or change the key, deploy again to each environment that uses it: `agnt5 deploy` for preview, `agnt5 deploy --env production` for production.

Without the key, runs fail with `Invalid configuration: OPENAI_API_KEY must be set`.
