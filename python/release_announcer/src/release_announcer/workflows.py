"""The `announce_release` workflow: merged PRs in, an announcement and a follow-up out.

Kill the worker at any point and restart it: finished steps (the PR summaries
included) return their checkpoints, the approval and the one-day wait survive
the restart, and nothing is posted twice.
"""
from __future__ import annotations

import asyncio
import os

from agnt5 import WorkflowContext, workflow

from release_announcer.demo import approved, crash_point
from release_announcer.functions import (
    build_report,
    check_links,
    draft_announcement,
    draft_followup,
    load_prs,
    publish,
    summarize_pr,
)

# Durable sleeps in this demo are measured in "hours". Set to 3600 for real time;
# the default turns the 24-hour follow-up delay into 24 seconds.
SECONDS_PER_HOUR = float(os.getenv("RELEASE_SECONDS_PER_HOUR", "1"))


@workflow
async def announce_release(
    ctx: WorkflowContext,
    release: str = "v1.4.0",
    followup_after_hours: float = 24.0,
    flaky_failures: int = 0,
    crash_at: str | None = None,
) -> dict:
    """Summarize PRs, draft, check links, approve, publish, wait, follow up.

    Demo inputs:
        flaky_failures: make the link checker fail this many times (retries absorb it).
        crash_at: kill the worker once at "after_summaries" or "after_draft".
    """
    prs = await ctx.step(load_prs, release)

    # 1. One LLM call per PR, all in parallel. Each is its own checkpoint, keyed
    #    by PR number so a replay matches results to PRs, not to their order.
    summaries = await asyncio.gather(
        *[ctx.step(summarize_pr, pr, key=f"pr-{pr['number']}") for pr in prs]
    )
    await crash_point(ctx, crash_at, "after_summaries")

    draft = await ctx.step(draft_announcement, release, list(summaries))
    await crash_point(ctx, crash_at, "after_draft")

    # 2. A flaky dependency. The step's retry policy absorbs the failures.
    links = await ctx.step(check_links, draft, flaky_failures)

    # 3. A maintainer signs off. The run is not in memory while it waits.
    answer = await ctx.wait_for_user(
        f"Publish the {release} announcement?\n\n{draft}",
        input_type="approval",
        options=[{"id": "approve", "label": "Publish"}, {"id": "reject", "label": "Reject"}],
    )
    if not approved(answer):
        return {"release": release, "published": False, "reason": "rejected by maintainer"}

    # 4. Post it, exactly once.
    announcement = await ctx.step(publish, "changelog", release, draft, key="changelog")

    # 5. Wait a day. Durable: no worker is held while it sleeps.
    await ctx.sleep(followup_after_hours * SECONDS_PER_HOUR, name="followup_delay")

    followup_text = await ctx.step(draft_followup, release)
    followup = await ctx.step(publish, "community", release, followup_text, key="followup")

    report = await ctx.step(build_report, len(prs))
    return {
        "release": release,
        "links": links,
        "announcement": announcement,
        "followup": followup,
        "execution_report": report,
    }
