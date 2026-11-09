"""The `onboard_customer` workflow: a multi-day email sequence for one new signup.

The run lives for days (seconds, in the demo) and spends almost all of that
time asleep. A durable sleep doesn't hold a worker, so deploys and crashes in
between don't matter: the run wakes on schedule and nothing is sent twice.
"""
from __future__ import annotations

import os

from agnt5 import WorkflowContext, workflow

from onboarding_drip.demo import approved, crash_point
from onboarding_drip.functions import (
    build_report,
    check_activity,
    research_company,
    send_email,
    write_email,
)

# Durable sleeps in this demo are measured in "hours". Set to 3600 for real time;
# the default turns the 3-day wait into 72 seconds.
SECONDS_PER_HOUR = float(os.getenv("ONBOARDING_SECONDS_PER_HOUR", "1"))

DEFAULT_USER = {"name": "Dana", "email": "dana@northwind.io", "company": "Northwind Logistics", "role": "Head of Ops"}


@workflow
async def onboard_customer(
    ctx: WorkflowContext,
    user: dict | None = None,
    wait_days: float = 3.0,
    flaky_failures: int = 0,
    crash_at: str | None = None,
) -> dict:
    """Research, welcome, wait, check activity, follow up, approve and send an offer.

    Demo inputs:
        flaky_failures: make the email provider fail this many times on the welcome email.
        crash_at: kill the worker once at "after_research", "after_welcome", or "after_wait".
    """
    user = user or DEFAULT_USER

    brief = await ctx.step(research_company, user)
    await crash_point(ctx, crash_at, "after_research")

    welcome = await ctx.step(write_email, user, "welcome", brief, key="welcome")
    welcome_sent = await ctx.step(send_email, user["email"], welcome, flaky_failures, key="welcome")
    await crash_point(ctx, crash_at, "after_welcome")

    # Wait three days. Durable: the platform holds the timer, not a worker.
    await ctx.sleep(wait_days * 24 * SECONDS_PER_HOUR, name="wait_after_welcome")
    await crash_point(ctx, crash_at, "after_wait")

    activity = await ctx.step(check_activity, user["email"])
    followup = await ctx.step(write_email, user, "followup", str(activity), key="followup")
    followup_sent = await ctx.step(send_email, user["email"], followup, key="followup")

    # A sales rep signs off before a discount goes out.
    offer = await ctx.step(write_email, user, "offer", str(activity), key="offer")
    answer = await ctx.wait_for_user(
        f"Send this upgrade offer to {user['email']}?\n\n{offer['body']}",
        input_type="approval",
        options=[{"id": "approve", "label": "Send offer"}, {"id": "reject", "label": "Don't send"}],
    )
    offer_sent = {"kind": "offer", "sent": False, "reason": "rejected by sales"}
    if approved(answer):
        offer_sent = await ctx.step(send_email, user["email"], offer, key="offer")

    report = await ctx.step(build_report)
    return {
        "user": user["email"],
        "activity": activity,
        "emails": [welcome_sent, followup_sent, offer_sent],
        "execution_report": report,
    }
