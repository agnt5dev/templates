"""Steps for the onboarding workflow.

Each `@function` becomes a durable step when the workflow calls it through
`ctx.step(...)`: its result is checkpointed, and a replay returns the
checkpoint instead of running the code again.
"""
from __future__ import annotations

import asyncio
import os
from collections import Counter

from agnt5 import FunctionContext, function, lm

from onboarding_drip.demo import log_execution, mock_mode, read_execution_log
from onboarding_drip.outbox import idempotency_key, send_once

MODEL = os.getenv("ONBOARDING_MODEL", "openai/gpt-6-luna")

# Simulated product analytics, keyed by email.
ACTIVITY = {
    "dana@northwind.io": {"logins": 2, "features_used": ["dashboards"], "teammates_invited": 0},
}


async def _generate(system: str, prompt: str, mock: str) -> str:
    if mock_mode():
        await asyncio.sleep(float(os.getenv("ONBOARDING_MOCK_LATENCY_S", "1.5")))
        return mock
    response = await lm.generate(model=MODEL, system_prompt=system, prompt=prompt)
    return response.text.strip()


class EmailServiceUnavailable(Exception):
    """The (simulated) email provider returned a 503. Retryable."""


@function
async def research_company(ctx: FunctionContext, user: dict) -> str:
    """Write a short brief on the new user's company. One LLM call."""
    log_execution(ctx.run_id, "research_company", user["company"])
    return await _generate(
        "In two sentences, describe what this company likely does and why it might use an analytics product.",
        f"Company: {user['company']}\nSignup role: {user['role']}",
        f"{user['company']} is a mid-sized logistics company. As {user['role']}, {user['name']} likely wants "
        "shipment dashboards their ops team can share.",
    )


@function
async def write_email(ctx: FunctionContext, user: dict, kind: str, context: str) -> dict:
    """Write one personalised email (welcome, follow-up, or offer). One LLM call."""
    log_execution(ctx.run_id, "write_email", kind)
    mocks = {
        "welcome": f"Hi {user['name']}, welcome aboard! Teams like yours at {user['company']} usually start "
        "with a shared shipments dashboard - here's a 3-minute guide.",
        "followup": f"Hi {user['name']}, you've built your first dashboard. Invite your ops team so they "
        "see the same numbers you do.",
        "offer": f"Hi {user['name']}, your trial ends soon. Upgrade this week and get 20% off the Team plan.",
    }
    body = await _generate(
        f"Write a short, warm {kind} email for a new user of an analytics product. Under 60 words.",
        f"User: {user['name']}, {user['role']} at {user['company']}\nContext: {context}",
        mocks[kind],
    )
    return {"kind": kind, "subject": f"[{kind}] {user['company']} x Acme Analytics", "body": body}


@function(retries=4, backoff="exponential")
async def send_email(ctx: FunctionContext, to: str, email: dict, flaky_failures: int = 0) -> dict:
    """Send one email through a flaky provider, exactly once.

    The provider fails `flaky_failures` times first; the retry policy absorbs
    it. The idempotency key stays the same on every retry, so a send that
    reached the provider before a failure is never sent again.
    """
    log_execution(ctx.run_id, "send_email", email["kind"], attempt=ctx.attempt)
    if ctx.attempt < flaky_failures:
        ctx.logger.warning("Email provider returned 503 (attempt %d) - will retry", ctx.attempt + 1)
        raise EmailServiceUnavailable(f"email provider returned 503 on attempt {ctx.attempt + 1}")
    sent = send_once(idempotency_key(ctx, email["kind"]), {"to": to, **email})
    return {"kind": email["kind"], "sent": sent, "duplicate_skipped": not sent}


@function
async def check_activity(ctx: FunctionContext, email: str) -> dict:
    """Read the user's product activity since signup (simulated analytics API)."""
    log_execution(ctx.run_id, "check_activity", email)
    return ACTIVITY.get(email, {"logins": 0, "features_used": [], "teammates_invited": 0})


@function
async def build_report(ctx: FunctionContext) -> dict:
    """Summarize how many times each step's code actually ran in this run."""
    executions = Counter(e["step"] for e in read_execution_log(ctx.run_id))
    return {
        "llm_calls_run": executions["research_company"] + executions["write_email"],
        "step_executions": dict(executions),
    }
