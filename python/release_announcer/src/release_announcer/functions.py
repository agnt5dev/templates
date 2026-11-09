"""Steps for the release announcement workflow.

Each `@function` becomes a durable step when the workflow calls it through
`ctx.step(...)`: its result is checkpointed, and a replay returns the
checkpoint instead of running the code again.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path

from agnt5 import FunctionContext, function, lm

from release_announcer.demo import log_execution, mock_mode, read_execution_log
from release_announcer.outbox import idempotency_key, send_once

MODEL = os.getenv("RELEASE_MODEL", "openai/gpt-6-luna")
PRS_FILE = Path(__file__).parent / "prs.json"


async def _generate(system: str, prompt: str, mock: str) -> str:
    if mock_mode():
        await asyncio.sleep(float(os.getenv("RELEASE_MOCK_LATENCY_S", "1.5")))
        return mock
    response = await lm.generate(model=MODEL, system_prompt=system, prompt=prompt)
    return response.text.strip()


class LinkCheckerUnavailable(Exception):
    """The (simulated) link checker timed out. Retryable."""


@function
async def load_prs(ctx: FunctionContext, release: str) -> list[dict]:
    """Load the pull requests merged for this release (a bundled sample)."""
    log_execution(ctx.run_id, "load_prs", release)
    return json.loads(PRS_FILE.read_text())


@function
async def summarize_pr(ctx: FunctionContext, pr: dict) -> dict:
    """Summarize one PR for users. One LLM call, one checkpoint."""
    log_execution(ctx.run_id, "summarize_pr", f"#{pr['number']}")
    summary = await _generate(
        "Summarize this pull request in one sentence for end users. No jargon.",
        f"{pr['title']}\n\n{pr['body']}",
        pr["mock_summary"],
    )
    return {"number": pr["number"], "title": pr["title"], "summary": summary}


@function
async def draft_announcement(ctx: FunctionContext, release: str, summaries: list[dict]) -> str:
    """Turn the PR summaries into one announcement."""
    log_execution(ctx.run_id, "draft_announcement", release)
    bullets = "\n".join(f"- {s['summary']} (#{s['number']})" for s in summaries)
    return await _generate(
        "Write a short, friendly release announcement from these changes. Keep the bullet list.",
        f"Release {release}\n{bullets}",
        f"{release} is out! Here's what changed:\n{bullets}",
    )


@function(retries=4, backoff="exponential")
async def check_links(ctx: FunctionContext, draft: str, flaky_failures: int = 0) -> dict:
    """Check the PR links in the draft. Fails `flaky_failures` times first."""
    log_execution(ctx.run_id, "check_links", attempt=ctx.attempt)
    if ctx.attempt < flaky_failures:
        ctx.logger.warning("Link checker timed out (attempt %d) - will retry", ctx.attempt + 1)
        raise LinkCheckerUnavailable(f"link checker timed out on attempt {ctx.attempt + 1}")
    return {"links_checked": draft.count("#"), "broken": 0}


@function
async def publish(ctx: FunctionContext, channel: str, release: str, text: str) -> dict:
    """Post `text` to `channel`, once. A re-run of this step is refused as a duplicate."""
    log_execution(ctx.run_id, "publish", channel)
    sent = send_once(idempotency_key(ctx, channel), {"channel": channel, "release": release, "text": text})
    return {"channel": channel, "published": sent, "duplicate_skipped": not sent}


@function
async def draft_followup(ctx: FunctionContext, release: str) -> str:
    """A day later: draft a 'what people are saying' follow-up."""
    log_execution(ctx.run_id, "draft_followup", release)
    return await _generate(
        "Write a two-sentence follow-up post thanking users for feedback on the release.",
        f"Release {release} shipped yesterday.",
        f"Thanks for all the feedback on {release}! Dark mode and the faster cold starts are the clear favourites so far.",
    )


@function
async def build_report(ctx: FunctionContext, pr_count: int) -> dict:
    """Summarize how many times each step's code actually ran in this run."""
    executions = Counter(e["step"] for e in read_execution_log(ctx.run_id))
    return {
        "prs": pr_count,
        "llm_summaries_run": executions["summarize_pr"],
        "step_executions": dict(executions),
    }
