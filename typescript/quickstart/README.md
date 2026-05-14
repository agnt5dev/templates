# Hacker News digest — AGNT5 quickstart (TypeScript)

Summarize the top Hacker News stories with an AGNT5 workflow. Watch each step
land in Studio. Kill the worker mid-run and see it resume.

## Prerequisites

- Node 22+
- `agnt5` CLI
- `OPENAI_API_KEY` in `.env`

## Run it

```bash
npm install
agnt5 dev
```

The terminal prints a Studio URL. Open it in your browser. In Studio:

1. Pick the `digest` workflow.
2. Set the input to `{"limit": 5}`.
3. Click **Run**.

The run appears live as:

```
digest (workflow)
├─ fetch_top_ids                  120ms
├─ fetch_story (×5 parallel)      ~180ms each
├─ summarize  (×5 parallel)       ~4s — gpt-5-mini
└─ assemble_digest                900ms
```

## Kill it and watch it resume

1. In Studio, trigger a longer run with input `{"limit": 10}`.
2. While it's still going, `Ctrl+C` the `agnt5 dev` terminal.
3. Restart: `agnt5 dev`.

Studio shows the run pick up exactly where it left off — completed steps stay
completed, only the missing ones re-run.

## Deploy

Create an account at [app.agnt5.com](https://app.agnt5.com), then:

```bash
agnt5 auth login
agnt5 deploy
```

Trigger `digest` from Studio. The trace appears the same way.

## What's in here

| File | Purpose |
|------|---------|
| `src/workflows.ts` | The `digest` workflow |
| `src/functions.ts` | `fetchTopIds`, `fetchStory`, `summarize`, `assembleDigest` |
| `app.ts` | Registers the workflow and steps with AGNT5 |
| `agnt5.yaml` | Project metadata for the CLI |

## Notes

- The Hacker News API is public; no token required.
- Default model is `openai/gpt-5-mini`. Change it on the `modelName` line in
  `src/functions.ts`.
- Every step call inside the workflow is a checkpoint. Keep new steps as
  `fn(...).run(...)` and call them through `ctx` so the runtime can skip them
  on replay.
