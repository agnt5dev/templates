# AI Tutor Agent — AGNT5 TypeScript Template

A multi-subject educational assistant that routes student questions to specialized tutors using the agent handoff pattern.

## What it does

- **Triage** — A triage agent analyzes the incoming question and determines the subject area.
- **Handoff** — Control is transferred to the appropriate specialist agent, which provides a focused, expert response.
- **Specialize** — A history tutor and a math tutor each have dedicated instructions tailored to their domain.

## Key concepts

- **Agent handoffs** — The triage agent uses `handoff()` to transfer the conversation to a specialist. The specialist handles the question end-to-end and returns the final response.
- **Lazy singletons** — Each agent is created once on first use, with the triage agent initialized after the specialists since it holds references to them.

## Setup

1. Install Node.js 22+:
   ```bash
   node --version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template typescript/tutor_agent my-tutor
   cd my-tutor
   ```

3. Install dependencies:
   ```bash
   npm install
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

Without the key, runs fail with OpenAI's 401 error, `Incorrect API key provided: ''`.
