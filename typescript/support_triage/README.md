# Support triage — AGNT5 template

A durable workflow that triages a customer support ticket: it classifies the ticket, looks up the order, asks a human before approving a large refund, and has a tool-calling agent draft the reply.

## What it does

- **Classify** — Sorts the ticket into `refund`, `bug` or `question` and flags urgent ones.
- **Look up the order** — Fetches the order the ticket names, retried with exponential backoff.
- **Ask before large refunds** — Refunds over $100 pause the workflow until a reviewer approves or rejects them in Studio.
- **Draft the reply** — A support agent calls its `get_policy` tool and writes a reply that uses the policy.

## Key concepts

- **Durable steps** — Every `ctx.step(...)` is a checkpoint, so a restarted worker skips finished steps, model calls included.
- **Human in the loop** — `ctx.waitForUser(..., { inputType: 'approval' })` pauses the run without holding it in memory.
- **Workflow state** — `ctx.set('status', ...)` records where the run is (`classifying`, `awaiting_approval`, `drafting`, `done`).
- **Mock mode** — Without an `OPENAI_API_KEY` (or with `MOCK_MODE=1`) the agent runs on a scripted model, so the whole workflow runs without an API key. With a key it uses `openai/gpt-6-luna`.

## Setup

1. Install Node.js 22 or later.

2. Clone or create from template:
   ```bash
   agnt5 create --template typescript/support_triage my-triage
   cd my-triage
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Set up environment variables, and add your `OPENAI_API_KEY` to `.env` to use a real model:
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev
   ```

## Run it

```bash
agnt5 run workflow triage_ticket --input '{"ticket_id": "T-1", "customer": "Ana", "message": "I want a refund for the cable", "order_id": "ORD-1001"}'
```

Use `"order_id": "ORD-2002"` (a $250 order) to see the run wait for approval in Studio.

## Deploy

```bash
agnt5 secrets set --name OPENAI_API_KEY --type api_key
agnt5 deploy
```

`agnt5 deploy` goes to the preview environment; run it there with `agnt5 run workflow triage_ticket --env preview --input '...'`.

## Test

```bash
npm test
npm run typecheck
```

The tests run the workflow in-process with the scripted model against `tests/cases.json`, the same cases the Python template uses.

See the [AGNT5 docs](https://agnt5.com/docs) for more.
