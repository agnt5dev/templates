"""
Plan approval in Slack: Approve / Reject buttons that resume the paused workflow.

Flow:
1. The workflow posts the research plan to the thread with two buttons. Each button's
   value carries the paused run's ID and deployment ID.
2. The workflow pauses on ctx.wait_for_user().
3. A click is delivered by the same Slack integration, as a form-encoded
   `payload=...` body. The workflow recognises it and calls AGNT5's resume API,
   which continues the paused run with "approve" or "reject".

Slack app setup: Interactivity & Shortcuts → On, Request URL = the integration URL
already used for Event Subscriptions. The worker needs APPROVAL_SERVICE_KEY (scopes:
run, workflow) to call the resume API.
"""

import json
import os
import re
from typing import Any
from urllib.parse import parse_qs

import httpx

from agnt5 import FunctionContext, function

from slack_deep_research.slack_once import claim_event, post_once, update_message

GATEWAY_URL = os.getenv("AGNT5_GATEWAY_URL", "https://gw.agnt5.com")
APPROVE, REJECT = "approve", "reject"


def to_slack_mrkdwn(text: str) -> str:
    """Agents write Markdown; Slack bolds with *single* asterisks and has no headings."""
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    return re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)


def plan_blocks(topic: str, plan: str, run_id: str, deployment_id: str, event_id: str = "") -> list[dict[str, Any]]:
    """Slack Block Kit message: the plan plus Approve / Reject buttons."""

    def button(answer: str, label: str, style: str) -> dict[str, Any]:
        return {
            "type": "button",
            "action_id": f"research_{answer}",
            "text": {"type": "plain_text", "text": label},
            "style": style,
            "value": json.dumps({"run": run_id, "deployment": deployment_id, "event": event_id, "answer": answer}),
        }

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Research plan:* {topic}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": to_slack_mrkdwn(plan)[:2900]}},
        {
            "type": "actions",
            "elements": [button(APPROVE, "Approve", "primary"), button(REJECT, "Reject", "danger")],
        },
    ]


def parse_interaction(envelope: dict[str, Any]) -> dict[str, Any] | None:
    """Return the Slack block_actions payload if this delivery is a button click."""
    body = envelope.get("body")
    if not isinstance(body, str) or not body.startswith("payload="):
        return None
    raw = parse_qs(body).get("payload", [""])[0]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if payload.get("type") != "block_actions" or not payload.get("actions"):
        return None
    return payload


async def resume_run(run_id: str, deployment_id: str, answer: str) -> dict[str, Any]:
    """Answer the paused run's wait_for_user() through AGNT5's resume API."""
    service_key = os.getenv("APPROVAL_SERVICE_KEY", "")
    if not service_key:
        return {"resumed": False, "reason": "APPROVAL_SERVICE_KEY not set"}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{GATEWAY_URL}/v1/workflows/resume/{run_id}",
            headers={"X-API-KEY": service_key, "X-DEPLOYMENT-ID": deployment_id},
            json={"user_response": answer},
        )
    if response.status_code >= 400:
        return {"resumed": False, "reason": f"{response.status_code}: {response.text[:200]}"}
    return {"resumed": True}


async def record_decision(interaction: dict[str, Any], bot_token: str, event_id: str, run_id: str, text: str) -> None:
    """Replace the buttons with the decision. chat.update keeps the claim tag on the message."""
    channel = (interaction.get("channel") or {}).get("id", "")
    ts = (interaction.get("container") or {}).get("message_ts") or (interaction.get("message") or {}).get("ts", "")
    if bot_token and channel and ts:
        async with httpx.AsyncClient(timeout=15) as client:
            result = await update_message(
                client, bot_token, channel, ts, text,
                payload={"kind": "claim", "event_id": event_id or run_id, "run_id": run_id},
            )
        if result.get("updated"):
            return
    await replace_buttons(interaction.get("response_url", ""), text)


async def replace_buttons(response_url: str, text: str) -> None:
    """Swap the buttons for the decision, so nobody clicks twice."""
    if not response_url:
        return
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(response_url, json={"replace_original": True, "text": text})


async def post_message(
    channel: str, bot_token: str, text: str, thread_ts: str | None = None, blocks: list | None = None
) -> dict[str, Any]:
    if not (bot_token and channel):
        return {"posted": False, "reason": "no token or channel"}
    payload: dict[str, Any] = {"channel": channel, "text": text, "unfurl_links": False, "unfurl_media": False}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    if blocks:
        payload["blocks"] = blocks
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {bot_token}"},
            json=payload,
        )
    data = response.json() if response.content else {}
    if not data.get("ok"):
        return {"posted": False, "reason": str(data.get("error") or response.status_code)}
    return {"posted": True, "ts": data.get("ts", "")}


@function(name="claim_event")
async def _claim_event(
    ctx: FunctionContext, channel: str, thread_ts: str, event_id: str, bot_token: str, run_id: str
) -> dict[str, Any]:
    """Claim this Slack event with a "Planning research…" message, or report a duplicate delivery."""
    if not (bot_token and channel and thread_ts):
        return {"posted": False, "reason": "no token or channel"}
    async with httpx.AsyncClient(timeout=15) as client:
        result = await claim_event(client, bot_token, channel, thread_ts, event_id or run_id, run_id)
    ctx.logger.info(f"Claim for event {event_id}: {result}")
    return result


@function(name="request_plan_approval")
async def _request_plan_approval(
    ctx: FunctionContext,
    channel: str,
    claim_ts: str,
    event_id: str,
    topic: str,
    plan: str,
    bot_token: str,
    run_id: str,
    deployment_id: str,
) -> dict[str, Any]:
    """Turn the claim message into the plan with Approve / Reject buttons. Editing is safe to repeat."""
    if not (bot_token and channel and claim_ts):
        return {"updated": False, "reason": "no token or channel"}
    async with httpx.AsyncClient(timeout=15) as client:
        result = await update_message(
            client,
            bot_token,
            channel,
            claim_ts,
            text=f"Research plan for: {topic}",
            payload={"kind": "claim", "event_id": event_id or run_id, "run_id": run_id},
            blocks=plan_blocks(topic, plan, run_id, deployment_id, event_id or run_id),
        )
    ctx.logger.info(f"Plan approval request: {result}")
    return result


@function(name="post_report")
async def _post_report(
    ctx: FunctionContext, channel: str, thread_ts: str, report: str, bot_token: str, run_id: str
) -> dict[str, Any]:
    """Post the report once: skip it if this run's report is already in the thread."""
    if not (bot_token and channel and thread_ts):
        return {"posted": False, "reason": "no token or channel"}
    async with httpx.AsyncClient(timeout=15) as client:
        result = await post_once(
            client,
            bot_token,
            channel,
            thread_ts,
            text=to_slack_mrkdwn(report),
            payload={"kind": "report", "run_id": run_id},
            match={"kind": "report", "run_id": run_id},
        )
    ctx.logger.info(f"Report post: {result}")
    return result
