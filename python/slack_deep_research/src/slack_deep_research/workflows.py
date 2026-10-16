"""
Slack Deep Research Workflow

Triggered by Slack messages (app_mention or direct message), this workflow
runs a fully automated research pipeline without Human-in-the-Loop approval:

1. Extract research topic from the Slack message
2. Plan - Scoping Agent creates a structured research plan
3. Research - Research Agent gathers information using Wikipedia and web tools
4. Write - Writing Agent synthesizes findings into a Slack-friendly summary
5. Post - Send the report back to the originating Slack channel/thread
"""

import json
import os
from typing import Any

from agnt5 import WorkflowContext, workflow
from agnt5.types import event

from slack_deep_research.approval import (
    APPROVE,
    _claim_event,
    _post_report,
    _request_plan_approval,
    parse_interaction,
    record_decision,
    resume_run,
)
from slack_deep_research.functions import _conduct_research, _plan_research, _write_report


# ---------------------------------------------------------------------------
# Slack envelope helpers (adapted from kitchen-sink)
# ---------------------------------------------------------------------------

def _parse_webhook_body(envelope: dict[str, Any]) -> dict[str, Any]:
    body = envelope.get("body", {})
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {"text": body}
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    return {}


def _nested_dict(value: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return current if isinstance(current, dict) else {}


def _first_string(value: dict[str, Any], *keys: str) -> str:
    for key in keys:
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item
    return ""


def _extract_slack_message(envelope: dict[str, Any]) -> dict[str, str]:
    body = _parse_webhook_body(envelope)
    slack_event = _nested_dict(body, "event")
    text = (
        _first_string(slack_event, "text")
        or _first_string(body, "text")
        or _first_string(envelope, "text")
    )
    event_type = (
        _first_string(envelope, "event_type")
        or (
            f"slack.{slack_event['type']}"
            if isinstance(slack_event.get("type"), str)
            else ""
        )
        or "slack.message"
    )
    return {
        "event_type": event_type,
        "message": text,
        "channel": _first_string(slack_event, "channel") or _first_string(body, "channel"),
        "user": (
            _first_string(slack_event, "user", "username", "bot_id")
            or _first_string(body, "user", "username")
        ),
        "subtype": _first_string(slack_event, "subtype"),
        "bot_id": _first_string(slack_event, "bot_id"),
        "thread_ts": _first_string(slack_event, "thread_ts", "ts"),
        # Slack's stable id for this event; the same across retried deliveries.
        "event_id": _first_string(body, "event_id"),
    }


def _should_process(message: dict[str, str]) -> tuple[bool, str]:
    if message.get("bot_id"):
        return False, "bot message"
    if message.get("subtype"):
        return False, f"unsupported subtype: {message['subtype']}"
    if not (message.get("message") or "").strip():
        return False, "empty message"
    # When a bot is @mentioned in a channel, Slack fires both app_mention and
    # message events for the same message. Skip the message event for public/
    # private channels (channel IDs start with C or G) — app_mention handles
    # those. Only process message events from DMs (channel IDs start with D).
    channel = message.get("channel", "")
    if message.get("event_type") == "slack.message" and channel and not channel.startswith("D"):
        return False, "channel message handled by app_mention"
    return True, ""


def _extract_topic(message: dict[str, str]) -> str:
    """Strip bot mentions (@BotName ...) from the message text to get the research topic."""
    text = (message.get("message") or "").strip()
    # Remove leading @mention tokens (e.g. "<@U12345> research X" → "research X")
    import re
    text = re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()
    # Remove a leading "research" keyword if present to get the bare topic
    topic = re.sub(r"^research\s+((on|about|into)\s+)?", "", text, flags=re.IGNORECASE).strip()
    # Drop Slack formatting wrapped around the whole question, e.g. *`compare ...`*
    topic = re.sub(r"^[*_`~]+|[*_`~]+$", "", topic).strip()
    return topic or text


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

@workflow(
    name="slack_deep_research",
    triggers=[event("slack.app_mention"), event("slack.message")],
)
async def slack_deep_research(ctx: WorkflowContext, **envelope) -> dict:
    """
    Triggered by Slack app_mention or message events.

    Runs an automated deep research pipeline on the message topic and
    posts the findings back to the originating Slack channel/thread.
    The plan is approved in Slack (Approve / Reject buttons) before any research runs.
    """
    # A click on the plan's Approve / Reject buttons: resume the paused run and stop.
    interaction = parse_interaction(envelope)
    if interaction:
        return await _handle_approval_click(ctx, interaction, envelope.get("bot_token") or "")

    message = _extract_slack_message(envelope)
    ctx.logger.info(
        "Slack %s from %s in %s: %s"
        % (
            message["event_type"],
            message["user"] or "unknown user",
            message["channel"] or "unknown channel",
            (message["message"] or "")[:120],
        )
    )

    should_process, skip_reason = _should_process(message)
    if not should_process:
        ctx.logger.info(f"Skipping: {skip_reason}")
        return {"status": "skipped", "reason": skip_reason}

    topic = _extract_topic(message)
    ctx.logger.info(f"Research topic: {topic[:200]}")
    bot_token = envelope.get("bot_token") or os.getenv("SLACK_BOT_TOKEN", "")
    channel = message.get("channel", "")
    thread_ts = message.get("thread_ts") or ""

    # Claim this Slack event before any work. AGNT5 doesn't deduplicate Slack retries,
    # so a second delivery of the same event finds the claim and stops here.
    claim = await ctx.step(_claim_event, channel, thread_ts, message["event_id"], bot_token, ctx.run_id)
    if claim.get("duplicate"):
        ctx.logger.info(f"Skipping: duplicate delivery of {message['event_id']} (run {claim['run_id']})")
        return {"status": "skipped", "reason": "duplicate delivery", "original_run": claim["run_id"]}

    # Stage 1: Plan
    ctx.logger.info("Stage 1: Creating research plan")
    research_plan = await ctx.step(_plan_research, topic)

    # Stage 2: Turn the claim message into the plan with buttons, then pause until someone clicks.
    await ctx.step(
        _request_plan_approval,
        channel,
        claim.get("ts", ""),
        message["event_id"],
        topic,
        research_plan,
        bot_token,
        ctx.run_id,
        os.getenv("AGNT5_DEPLOYMENT_ID", ""),
    )
    decision = await ctx.wait_for_user(
        question=f"Approve this research plan?\n\n{research_plan}",
        input_type="approval",
        options=[{"id": "approve", "label": "Approve"}, {"id": "reject", "label": "Reject"}],
    )
    if (decision or "").strip().lower() not in (APPROVE, "approved"):
        # The click already replaced the buttons with "Rejected by @user".
        ctx.logger.info(f"Research plan rejected: {decision!r}")
        return {"status": "rejected", "topic": topic, "plan": research_plan}
    ctx.logger.info("Research plan approved")

    # Stage 3: Research
    ctx.logger.info("Stage 3: Conducting research")
    research_findings = await ctx.step(_conduct_research, topic, research_plan)

    # Stage 4: Write report
    ctx.logger.info("Stage 4: Writing Slack-friendly report")
    report = await ctx.step(_write_report, topic, research_plan, research_findings)

    # Stage 5: Post the report once, even if this step runs again after a crash.
    post_result = await ctx.step(_post_report, channel, thread_ts, report, bot_token, ctx.run_id)

    ctx.logger.info("Deep research workflow completed")
    return {
        "status": "completed",
        "topic": topic,
        "report": report,
        "slack_post": post_result,
    }


async def _handle_approval_click(ctx: WorkflowContext, interaction: dict[str, Any], bot_token: str) -> dict:
    action = interaction["actions"][0]
    try:
        value = json.loads(action.get("value") or "{}")
    except json.JSONDecodeError:
        return {"status": "skipped", "reason": "unrecognised button"}
    run_id, deployment_id, answer = value.get("run"), value.get("deployment"), value.get("answer")
    if not (run_id and deployment_id and answer):
        return {"status": "skipped", "reason": "unrecognised button"}

    user = (interaction.get("user") or {}).get("id", "")
    ctx.logger.info(f"Plan {answer} by {user or 'unknown user'} for run {run_id}")
    result = await resume_run(run_id, deployment_id, answer)
    if result["resumed"]:
        verdict = "Approved" if answer == APPROVE else "Rejected"
        await record_decision(
            interaction,
            bot_token,
            value.get("event", ""),
            run_id,
            f"{verdict} by <@{user}>." + (" Researching now…" if answer == APPROVE else ""),
        )
    else:
        # For example a second click: the run is no longer paused. Leave the message as is.
        ctx.logger.warning(f"Resume failed: {result['reason']}")
    return {"status": "approval_click", "run_id": run_id, "answer": answer, **result}


__all__ = ["slack_deep_research"]
