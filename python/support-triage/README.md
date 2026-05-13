# Support Triage Agent

**See AGNT5's magic in 5 minutes.**

Watch a workflow fail, recover automatically, pause for human approval, and post exactly once—all without writing retry loops or state management code. That's AGNT5.

## What You'll Build

A support automation workflow that:
1. Receives a support ticket
2. Fetches customer info (fails on first attempt, auto-retries!)
3. Analyzes the ticket with an AI agent
4. **Pauses for human approval** (survives restarts!)
5. Posts the reply (exactly once, guaranteed)

## Prerequisites

- Python 3.11+
- AGNT5 CLI installed (`pip install agnt5-cli`)

## Quick Start

### 1. Start the Dev Server

```bash
agnt5 dev up
```

### 2. Install Dependencies

```bash
cd sdk/templates/python/support-triage
pip install -e .
```

### 3. Start the Worker

```bash
python app.py
```

### 4. Submit a Ticket

```bash
curl -X POST http://localhost:34183/api/v1/workflows/support_triage/runs \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TCK-1001","subject":"Need refund","body":"Upgraded by mistake"}'
```

### 5. Watch in Dev Studio

Open http://localhost:34181 to see your workflow progress through each step.

---

## The Magic Moments

### 🔄 Automatic Recovery

1. Start a workflow
2. Watch `fetch_customer_info` **fail** on first attempt
3. **Platform automatically retries** with backoff
4. Second attempt succeeds

You didn't write any retry logic. The platform handles it.

### ⏸️ Human-in-the-Loop

1. Let the workflow reach the approval step
2. **Close your laptop**. Go to lunch.
3. Come back hours later
4. **The approval is still waiting** in Dev Studio
5. Approve it → workflow completes

### ✅ Exactly-Once Side Effects

1. Start a workflow, approve the reply
2. Check `.agnt5_demo/replies.log`
3. **Exactly one entry** — no duplicates

Even if the platform crashes and replays, side effects happen once.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. FETCH CUSTOMER INFO (automatic retry)                       │
│     └── fetch_customer_info(ticket_id)  # fails, then retries  │
│                                                                 │
│  2. ANALYZE TICKET (checkpointed)                               │
│     └── analyze_ticket(ticket, customer) # AI agent            │
│                                                                 │
│  3. HUMAN APPROVAL (durable pause)                              │
│     └── ctx.wait_for_user("Approve this reply?")               │
│                                                                 │
│  💤 CLOSE LAPTOP → come back hours later → still waiting       │
│                                                                 │
│  4. POST REPLY (exactly-once)                                   │
│     └── post_reply(ticket, message)  # idempotent              │
└─────────────────────────────────────────────────────────────────┘
```

### The Code (~50 lines)

```python
@workflow
async def support_triage(ctx: WorkflowContext, ticket: dict) -> dict:
    # Step 1: Fetch customer info (demonstrates automatic retry)
    customer = await ctx.task(fetch_customer_info, ticket_id=ticket["ticket_id"])

    # Step 2: Analyze ticket with AI agent (checkpointed)
    analysis = await ctx.task(analyze_ticket, ticket=ticket, customer=customer)

    # Step 3: Human approval (durable pause - survives restarts)
    decision = await ctx.wait_for_user(
        question=f"Approve this reply?\n\n{analysis['draft_reply']}",
        input_type="selection",
        options=[
            {"id": "approve", "label": "Send Reply"},
            {"id": "reject", "label": "Reject"},
        ],
    )

    if decision == "reject":
        return {"status": "rejected"}

    # Step 4: Post reply (exactly-once via idempotency)
    result = await ctx.task(post_reply, ticket_id=ticket["ticket_id"], message=analysis["draft_reply"])

    return {"status": "sent", "reply_id": result["reply_id"]}
```

---

## What AGNT5 Handled For You

You wrote 50 lines of Python. AGNT5 provided:

- ✅ **Automatic retry** — Transient failures retry with exponential backoff
- ✅ **Durable execution** — Workflow state persists across restarts
- ✅ **Step checkpointing** — Each `ctx.task()` call is memoized
- ✅ **Human-in-the-loop** — `wait_for_user()` pauses durably
- ✅ **Exactly-once semantics** — Side effects don't duplicate
- ✅ **Full observability** — Every step, retry, and decision in the timeline
- ✅ **Correlation IDs** — Trace requests across services

You didn't build:
- Retry loops
- State machines
- Database migrations
- Message queues
- Idempotency keys
- Checkpoint storage
- Event sourcing

---

## Using Real AI

By default, the demo uses mock responses (no API key needed). To use real LLM:

```bash
export AGNT5_USE_REAL_LLM=1
export OPENAI_API_KEY=sk-your-key-here
python app.py
```

Supports OpenAI and Anthropic models.

---

## Sample Tickets

Try these tickets to see different KB matches:

```bash
# Refund request
curl -X POST http://localhost:34183/api/v1/workflows/support_triage/runs \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TCK-1002","subject":"Refund request","body":"Cancel my subscription"}'

# Password reset
curl -X POST http://localhost:34183/api/v1/workflows/support_triage/runs \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TCK-1003","subject":"Cant log in","body":"Forgot my password"}'

# Upgrade question
curl -X POST http://localhost:34183/api/v1/workflows/support_triage/runs \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TCK-1004","subject":"Upgrade to Pro","body":"What features do I get?"}'
```

---

## Files

```
support-triage/
├── README.md              # This file
├── app.py                 # Worker entry point
├── demo.sh                # Interactive demo script
├── pyproject.toml         # Dependencies
├── src/support_triage/
│   ├── __init__.py
│   ├── workflows.py       # Main workflow (~50 lines)
│   ├── functions.py       # Fetch, analyze, post
│   ├── tools.py           # Agent tools and mock data
│   └── agent.py           # AI agent configuration
└── data/
    └── tickets.jsonl      # Sample tickets
```

---

## Next Steps

- **Add more tools**: Integrate real Zendesk, Intercom, or Freshdesk APIs
- **Expand KB**: Connect to your actual knowledge base or vector search
- **Add agents**: Use AGNT5 Agents for more complex reasoning
- **Deploy**: Push to AGNT5 Cloud or self-host with Docker

Questions? Join our [Discord](https://discord.gg/agnt5) or open an issue.
