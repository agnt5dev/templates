# Slack Deep Research — AGNT5 Template

A Slack bot that researches a question in the thread it was asked in. It posts a research plan with **Approve** and **Reject** buttons first, and only researches after someone approves.

## What it does

1. **Claim** — The bot posts "Planning research…" to the thread, tagged with Slack's `event_id`. A second delivery of the same Slack event finds the tag and stops.
2. **Plan** — A scoping agent turns the question into subtopics. The bot edits its message into the plan with **Approve** and **Reject** buttons.
3. **Approve** — The workflow pauses on `ctx.wait_for_user()`. A button click reaches the same AGNT5 integration, and the workflow resumes the paused run through AGNT5's resume API.
4. **Research** — A research agent searches Wikipedia and reads the most relevant pages.
5. **Report** — A writing agent writes a Slack-formatted report, and the bot posts it to the thread once.

## Key concepts

- **Human-in-the-loop** — `ctx.wait_for_user()` pauses the run until the plan is approved or rejected.
- **Recorded steps** — Each stage is a `ctx.step`. Completed steps are restored instead of running again, for example when the run resumes after the click. A step that was interrupted may run again.
- **Posting once** — Slack's `chat.postMessage` has no idempotency key and AGNT5 doesn't deduplicate Slack retries, so every bot message carries Slack message metadata and the bot reads the thread before it posts (`slack_once.py`).

## Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create the project from this template:
   ```bash
   agnt5 create --template python/slack_deep_research my-research-bot
   cd my-research-bot
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` and `APPROVAL_SERVICE_KEY`. Create the service key with:
   ```bash
   agnt5 service-keys create --name slack-approver --project <project-id> --scopes run,workflow
   ```

## Run locally without Slack

```bash
agnt5 dev -d
agnt5 run workflow slack_deep_research --input '{"body":{"event":{"type":"app_mention","text":"<@U0BOT> compare Raft and Paxos: leader election, and which systems use each","channel":"C0TEST","ts":"1"}}}'
```

The run plans, then pauses. Approve it the way the button does:

```bash
curl -X POST "https://gw.agnt5.com/v1/workflows/resume/<run-id>" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $APPROVAL_SERVICE_KEY" \
  -H "X-DEPLOYMENT-ID: $(cat .agnt5/dev-deployment-id)" \
  -d '{"user_response": "approve"}'
```

The run continues and returns the full `report`. Nothing is posted to Slack locally.

## Connect to Slack

1. Add the keys as project secrets and deploy:
   ```bash
   agnt5 secrets set --name OPENAI_API_KEY --type api_key
   agnt5 secrets set --name APPROVAL_SERVICE_KEY --type api_key
   agnt5 deploy --env production
   ```
2. Follow the [Slack integration guide](https://agnt5.com/docs/integrations/event-sources/slack) and choose:
   - **Bot token scopes:** `app_mentions:read`, `chat:write`, `channels:history` (and `groups:history` for private channels)
   - **Bot events:** `app_mention`
   - **Interactivity:** on, with the same Request URL as Event Subscriptions
   - **Target in Studio:** your production deployment and the `slack_deep_research` workflow
3. Mention the bot in a channel it's in, and approve the plan it posts.

## Tests

```bash
uv run --extra dev pytest
```

The tests run the post-once logic against a fake Slack.

See the [Slack deep research cookbook](https://agnt5.com/cookbooks/slack-deep-research-agent-v3) for a walkthrough.
