# Expense processor — AGNT5 durability template

A workflow that turns a batch of receipts into ledger entries and reimbursement emails, built so you can crash it on purpose and watch it recover.

## What it does

1. **Reads 12 receipts with an LLM**, one durable step per receipt.
2. **Converts them to USD** through a flaky exchange-rate service, with automatic retries.
3. **Posts expenses under $500** to the accounting ledger.
4. **Asks a manager** to approve the rest, and waits for the answer.
5. **Waits out a 48-hour payout window** (48 seconds in the demo).
6. **Emails each employee** their reimbursement.

## What it shows

| Durability feature | Where |
|---|---|
| Finished steps are never redone, LLM calls included | Crash after receipt 7: only receipts 8–12 are read again |
| Automatic retries with backoff | `convert_to_usd` fails twice, then succeeds |
| A human approval doesn't hold a worker | The run pauses for a manager and resumes from the approval |
| A durable sleep doesn't hold a worker | The payout window is a platform timer, not a sleeping process |
| Side effects carry an idempotency key | Ledger entries and emails are keyed, so a re-run step can't apply them twice |

Every step appends a line to `.data/execution_log.jsonl` when its code actually runs. The workflow's result ends with an `execution_report` that counts those lines, so you can see what replay skipped.

## Setup

1. Install [uv](https://docs.astral.sh/uv/), then create the project:
   ```bash
   agnt5 create --template python/expense_processor my-expenses
   cd my-expenses
   uv sync
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   The example file turns on mock mode (`EXPENSES_MOCK_MODE=1`), so no API key is needed. To read receipts with a real model, comment that line out and set `OPENAI_API_KEY`.

3. Start the worker:
   ```bash
   agnt5 dev
   ```

4. In a second terminal, run the workflow:
   ```bash
   agnt5 run workflow process_expenses --input '{}'
   ```
   When the run pauses for approval, open it in Studio (the link is printed by `agnt5 dev`) and click **Approve**.

## Break it on purpose

Use a fresh `batch_id` for each run so earlier runs don't get in the way.

### 1. A flaky dependency (local)

```bash
agnt5 run workflow process_expenses --input '{"batch_id": "demo-1", "flaky_failures": 2}'
```

`convert_to_usd` fails twice and succeeds on the third attempt. The retries come from the step's policy, `@function(retries=4, backoff="exponential")`, so the workflow code never sees the failures. The worker log shows each failed attempt, and the execution report shows `convert_to_usd` ran 3 times.

### 2. Pause for a human (local)

Run the workflow and let it pause for approval. The run isn't held in the worker while it waits. When you click **Approve** in Studio, the platform dispatches it again: the worker log shows every earlier step as `Replaying cached step`, and only the steps after the approval run.

### 3. Crash in the middle of the LLM work (deployed)

Crash recovery needs a deployed worker, so deploy the project first. A deployment doesn't read `.env`, so set the demo settings as project secrets:

```bash
echo 1 | agnt5 secrets set --name EXPENSES_MOCK_MODE --project <project-id> --type other --stdin
echo /tmp/expenses | agnt5 secrets set --name EXPENSES_DATA_DIR --project <project-id> --type other --stdin
agnt5 deploy
```

Then run:

```bash
agnt5 run workflow process_expenses --env preview --input '{"batch_id": "demo-3", "crash_at": "receipt_7"}'
```

The worker exits right after receipt 7 is read, and the platform starts a new one. The platform notices the dead worker when its lease runs out, so the run sits idle for a few minutes before it resumes. Then:

- Receipts 1–7 come back from their checkpoints. In the run's events in Studio, attempt 2 starts `extract_receipt` only for receipts 8–12.
- After you approve, the result's `execution_report.llm_extractions_run` is **12**, not 19.

### 4. A durable sleep (deployed)

After the approval, the run waits out the payout window. In the run's events, the sleep shows as `timer.scheduled`, then `timer.fired` 48 seconds later, followed by `run.resumed`. No worker runs while it waits; the platform holds the timer and sends the run back when it fires.

## Rules for replay-safe code

The workflow function re-runs from the top on every resume. Steps return their checkpoints; everything else runs again.

- **Put side effects and slow work in steps** (`ctx.step(...)`). Don't call APIs, models, or the clock directly in the workflow body.
- **Give repeated steps a key** (`key=receipt["id"]`). The key ties a checkpoint to the item, not to its position in a loop.
- **Pass an idempotency key to external systems.** A step can run more than once if it is retried or the worker dies before its result is saved. `ctx.activation.idempotency_key` stays the same across those runs; `post_to_ledger` and `notify_reimbursements` use it.
- **Use `ctx.sleep` and `ctx.wait_for_user` for waiting.** They release the worker and survive restarts; `asyncio.sleep` doesn't.

## Files

- `src/expense_processor/workflows.py` — the `process_expenses` workflow.
- `src/expense_processor/functions.py` — the steps.
- `src/expense_processor/accounting.py` — a local stand-in for the ledger and email APIs.
- `src/expense_processor/demo.py` — the crash switch and execution log (demo only).

Learn more at [docs.agnt5.com](https://docs.agnt5.com).
