"""The `respond_to_incident` workflow: alert in, investigated and fixed incident out.

The dangerous step is the rollback. It sits behind a human approval and
carries an idempotency key, so a crash or retry can never roll back twice.
"""
from __future__ import annotations

import asyncio
import os

from agnt5 import WorkflowContext, workflow

from incident_responder.demo import approved, crash_point
from incident_responder.functions import (
    analyze,
    apply_rollback,
    build_report,
    post_postmortem,
    propose_fix,
    verify_recovery,
)

# Durable sleeps in this demo are measured in "minutes". Set to 60 for real time;
# the default turns the 10-minute settle time into 30 seconds.
SECONDS_PER_MINUTE = float(os.getenv("INCIDENT_SECONDS_PER_MINUTE", "3"))

DEFAULT_ALERT = {
    "id": "INC-4471",
    "title": "checkout-api error rate above 25% for 5 minutes",
    "service": "checkout-api",
}


@workflow
async def respond_to_incident(
    ctx: WorkflowContext,
    alert: dict | None = None,
    settle_minutes: float = 10.0,
    flaky_failures: int = 0,
    crash_at: str | None = None,
) -> dict:
    """Investigate in parallel, propose, approve, roll back, wait, verify, write up.

    Demo inputs:
        flaky_failures: make the metrics backend fail this many times (retries absorb it).
        crash_at: kill the worker once at "after_analysis" or "after_rollback".
    """
    alert = alert or DEFAULT_ALERT

    # 1. Three LLM investigations in parallel, each its own checkpoint.
    findings = await asyncio.gather(
        *[
            ctx.step(analyze, source, alert, flaky_failures, key=source)
            for source in ("logs", "metrics", "deploys")
        ]
    )
    await crash_point(ctx, crash_at, "after_analysis")

    fix = await ctx.step(propose_fix, alert, list(findings))

    # 2. On call approves the rollback. The run is not in memory while it waits.
    answer = await ctx.wait_for_user(
        f"{alert['id']}: roll back {fix['service']} to {fix['to_version']}?\n\n{fix['rationale']}",
        input_type="approval",
        options=[{"id": "approve", "label": "Roll back"}, {"id": "reject", "label": "Don't roll back"}],
    )
    if not approved(answer):
        return {"incident": alert["id"], "rollback": "rejected by on call", "findings": list(findings)}

    # 3. The risky action, exactly once.
    rollback = await ctx.step(apply_rollback, fix)
    await crash_point(ctx, crash_at, "after_rollback")

    # 4. Let the system settle. Durable: no worker is held while it waits.
    await ctx.sleep(settle_minutes * SECONDS_PER_MINUTE, name="settle_after_rollback")

    health = await ctx.step(verify_recovery, fix["service"])
    postmortem = await ctx.step(post_postmortem, alert, list(findings), fix, health)

    report = await ctx.step(build_report)
    return {
        "incident": alert["id"],
        "fix": fix,
        "rollback": rollback,
        "health": health,
        "postmortem": postmortem,
        "execution_report": report,
    }
