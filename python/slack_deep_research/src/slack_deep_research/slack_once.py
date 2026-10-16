"""
Post to Slack at most once, even when a step re-runs or Slack delivers an event twice.

AGNT5 records a step once it completes. If the worker crashes after Slack accepted a
message but before the step was recorded, the step runs again. Slack's chat.postMessage
has no idempotency key, so the bot reconciles instead: every bot message carries Slack
message metadata (kind, event_id, run_id), and before posting, the bot reads the thread
and reuses a matching message.

The same tag deduplicates Slack deliveries. AGNT5 doesn't deduplicate Slack retries, so
the first step of a run claims the Slack event_id with a "Planning research…" message.
A second delivery of the same event finds that claim and stops.

Needs the channels:history scope (groups:history for private channels) to read threads.
"""

from typing import Any

import httpx

SLACK_API = "https://slack.com/api"
EVENT_TYPE = "research_bot"


def _metadata(payload: dict[str, str]) -> dict[str, Any]:
    return {"event_type": EVENT_TYPE, "event_payload": payload}


async def _call(client: httpx.AsyncClient, method: str, token: str, **kwargs: Any) -> dict[str, Any]:
    response = await client.request(
        "GET" if "params" in kwargs else "POST",
        f"{SLACK_API}/{method}",
        headers={"Authorization": f"Bearer {token}"},
        **kwargs,
    )
    return response.json() if response.content else {"ok": False, "error": str(response.status_code)}


async def find_bot_message(
    client: httpx.AsyncClient, token: str, channel: str, thread_ts: str, match: dict[str, str]
) -> tuple[dict[str, Any] | None, str]:
    """Return (message, error) for the first bot message in the thread whose tag matches."""
    data = await _call(
        client,
        "conversations.replies",
        token,
        params={"channel": channel, "ts": thread_ts, "include_all_metadata": "true", "limit": 200},
    )
    if not data.get("ok"):
        return None, str(data.get("error") or "conversations.replies failed")
    for message in data.get("messages", []):
        metadata = message.get("metadata") or {}
        payload = metadata.get("event_payload") or {}
        if metadata.get("event_type") == EVENT_TYPE and all(payload.get(k) == v for k, v in match.items()):
            return message, ""
    return None, ""


async def post_once(
    client: httpx.AsyncClient,
    token: str,
    channel: str,
    thread_ts: str,
    text: str,
    payload: dict[str, str],
    match: dict[str, str],
    blocks: list | None = None,
) -> dict[str, Any]:
    """Post unless a bot message tagged with `match` is already in the thread."""
    existing, error = await find_bot_message(client, token, channel, thread_ts, match)
    if existing:
        return {
            "posted": False,
            "existing": True,
            "ts": existing.get("ts", ""),
            "payload": (existing.get("metadata") or {}).get("event_payload") or {},
        }
    body: dict[str, Any] = {
        "channel": channel,
        "thread_ts": thread_ts,
        "text": text,
        "metadata": _metadata(payload),
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if blocks:
        body["blocks"] = blocks
    data = await _call(client, "chat.postMessage", token, json=body)
    if not data.get("ok"):
        return {"posted": False, "reason": str(data.get("error") or "chat.postMessage failed")}
    result: dict[str, Any] = {"posted": True, "ts": data.get("ts", "")}
    if error:
        # Couldn't read the thread (for example missing_scope), so this post wasn't checked.
        result["unchecked"] = error
    return result


async def update_message(
    client: httpx.AsyncClient,
    token: str,
    channel: str,
    ts: str,
    text: str,
    payload: dict[str, str],
    blocks: list | None = None,
) -> dict[str, Any]:
    """Edit a bot message in place, keeping its tag. Safe to repeat."""
    body: dict[str, Any] = {"channel": channel, "ts": ts, "text": text, "metadata": _metadata(payload)}
    body["blocks"] = blocks or []
    data = await _call(client, "chat.update", token, json=body)
    if not data.get("ok"):
        return {"updated": False, "reason": str(data.get("error") or "chat.update failed")}
    return {"updated": True, "ts": ts}


async def claim_event(
    client: httpx.AsyncClient, token: str, channel: str, thread_ts: str, event_id: str, run_id: str
) -> dict[str, Any]:
    """
    Claim a Slack event for this run with a "Planning research…" message.

    Returns {"duplicate": True, "run_id": <other run>} if another run already claimed it,
    otherwise {"ts": <claim message ts>} (the existing claim when this step re-runs).
    """
    payload = {"kind": "claim", "event_id": event_id, "run_id": run_id}
    result = await post_once(
        client,
        token,
        channel,
        thread_ts,
        text="Planning research…",
        payload=payload,
        match={"kind": "claim", "event_id": event_id},
    )
    if result.get("existing"):
        other = result["payload"].get("run_id", "")
        if other and other != run_id:
            return {"duplicate": True, "run_id": other, "ts": result["ts"]}
    return result
