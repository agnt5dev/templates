"""Steps for the incident response workflow.

Each `@function` becomes a durable step when the workflow calls it through
`ctx.step(...)`: its result is checkpointed, and a replay returns the
checkpoint instead of running the code again.
"""
from __future__ import annotations

import asyncio
import os
from collections import Counter

from agnt5 import FunctionContext, function, lm

from incident_responder.demo import log_execution, mock_mode, read_execution_log
from incident_responder.outbox import idempotency_key, send_once

MODEL = os.getenv("INCIDENT_MODEL", "openai/gpt-6-luna")

# Simulated telemetry for the sample incident.
EVIDENCE = {
    "logs": "14:02:11 checkout-api ERROR pool exhausted: 50/50 connections in use (x1,204)\n"
    "14:02:13 checkout-api WARN request timeout after 30s (x388)",
    "metrics": "checkout-api p99 latency 180ms -> 30.4s at 14:01; error rate 0.2% -> 31%; db connections 50/50",
    "deploys": "14:00:05 checkout-api v2.31.0 rolled out (changed: db pool size 200 -> 50, retry middleware)",
}
MOCK_FINDINGS = {
    "logs": "Connection pool exhausted on checkout-api since 14:02; requests time out waiting for a connection.",
    "metrics": "Latency and errors jumped at 14:01, right as DB connections hit the 50 cap.",
    "deploys": "v2.31.0 shipped at 14:00 and cut the DB pool from 200 to 50 connections.",
}


async def _generate(system: str, prompt: str, mock: str) -> str:
    if mock_mode():
        await asyncio.sleep(float(os.getenv("INCIDENT_MOCK_LATENCY_S", "1.5")))
        return mock
    response = await lm.generate(model=MODEL, system_prompt=system, prompt=prompt)
    return response.text.strip()


class MetricsTimeout(Exception):
    """The (simulated) metrics backend timed out. Retryable."""


@function(retries=4, backoff="exponential")
async def analyze(ctx: FunctionContext, source: str, alert: dict, flaky_failures: int = 0) -> dict:
    """Investigate one evidence source (logs, metrics, or deploys) with an LLM.

    The metrics backend fails `flaky_failures` times first; retries absorb it.
    """
    log_execution(ctx.run_id, "analyze", source, attempt=ctx.attempt)
    if source == "metrics" and ctx.attempt < flaky_failures:
        ctx.logger.warning("Metrics backend timed out (attempt %d) - will retry", ctx.attempt + 1)
        raise MetricsTimeout(f"metrics query timed out on attempt {ctx.attempt + 1}")
    finding = await _generate(
        f"You are on call. In one sentence, what do these {source} say about the alert?",
        f"Alert: {alert['title']}\n\n{EVIDENCE[source]}",
        MOCK_FINDINGS[source],
    )
    return {"source": source, "finding": finding}


@function
async def propose_fix(ctx: FunctionContext, alert: dict, findings: list[dict]) -> dict:
    """Name the likely cause and propose one remediation."""
    log_execution(ctx.run_id, "propose_fix", alert["id"])
    notes = "\n".join(f"- {f['source']}: {f['finding']}" for f in findings)
    rationale = await _generate(
        "From these findings, state the likely root cause and the safest fix in two sentences.",
        f"Alert: {alert['title']}\n{notes}",
        "v2.31.0 cut the DB pool from 200 to 50, so checkout-api runs out of connections under load. "
        "Roll back checkout-api to v2.30.4.",
    )
    return {"action": "rollback", "service": alert["service"], "to_version": "v2.30.4", "rationale": rationale}


@function
async def apply_rollback(ctx: FunctionContext, fix: dict) -> dict:
    """Roll the service back. Must never run twice, so it carries an idempotency key."""
    log_execution(ctx.run_id, "apply_rollback", fix["service"])
    applied = send_once(idempotency_key(ctx), {"type": "rollback", **fix})
    return {"rollback_applied": applied, "duplicate_skipped": not applied}


@function
async def verify_recovery(ctx: FunctionContext, service: str) -> dict:
    """Check the service's health after the fix settles (simulated)."""
    log_execution(ctx.run_id, "verify_recovery", service)
    return {"service": service, "p99_ms": 175, "error_rate": 0.002, "recovered": True}


@function
async def post_postmortem(ctx: FunctionContext, alert: dict, findings: list[dict], fix: dict, health: dict) -> dict:
    """Write the postmortem with an LLM and post it to the incident channel, once."""
    log_execution(ctx.run_id, "post_postmortem", alert["id"])
    text = await _generate(
        "Write a 4-line incident postmortem: impact, cause, fix, follow-up.",
        f"Alert: {alert['title']}\nFindings: {findings}\nFix: {fix}\nHealth after fix: {health}",
        f"Impact: checkout errors up to 31% for ~20 min. Cause: {fix['rationale']} "
        f"Fix: rolled back to {fix['to_version']}. Follow-up: load-test pool size changes before rollout.",
    )
    posted = send_once(idempotency_key(ctx), {"type": "postmortem", "incident": alert["id"], "text": text})
    return {"postmortem_posted": posted, "duplicate_skipped": not posted, "text": text}


@function
async def build_report(ctx: FunctionContext) -> dict:
    """Summarize how many times each step's code actually ran in this run."""
    executions = Counter(e["step"] for e in read_execution_log(ctx.run_id))
    return {"rollbacks_run": executions["apply_rollback"], "step_executions": dict(executions)}
