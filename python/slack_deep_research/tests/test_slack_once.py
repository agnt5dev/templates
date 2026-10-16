"""Reconcile-before-post: duplicate deliveries and re-run steps must not post twice."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slack_deep_research.slack_once import claim_event, post_once, update_message  # noqa: E402

CHANNEL, THREAD = "C1", "1700000000.000100"


class FakeSlack:
    """Keeps one thread's messages, with metadata, like Slack does."""

    def __init__(self, history_error: str = ""):
        self.messages: list[dict] = [{"ts": THREAD, "text": "<@BOT> compare Raft and Paxos"}]
        self.posts = 0
        self.history_error = history_error

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "conversations.replies":
            if self.history_error:
                return httpx.Response(200, json={"ok": False, "error": self.history_error})
            return httpx.Response(200, json={"ok": True, "messages": self.messages})
        body = json.loads(request.content)
        if method == "chat.postMessage":
            self.posts += 1
            ts = f"1700000000.{self.posts:06d}"
            self.messages.append({"ts": ts, "text": body["text"], "metadata": body.get("metadata")})
            return httpx.Response(200, json={"ok": True, "ts": ts})
        if method == "chat.update":
            for m in self.messages:
                if m["ts"] == body["ts"]:
                    m["text"], m["metadata"] = body["text"], body.get("metadata", m.get("metadata"))
            return httpx.Response(200, json={"ok": True, "ts": body["ts"]})
        return httpx.Response(404)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def run(coro):
    return asyncio.run(coro)


def test_first_delivery_claims_the_event():
    slack = FakeSlack()

    async def go():
        async with slack.client() as c:
            return await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-a")

    result = run(go())
    assert result["posted"] is True and slack.posts == 1


def test_duplicate_delivery_from_another_run_is_skipped():
    slack = FakeSlack()

    async def go():
        async with slack.client() as c:
            await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-a")
            return await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-b")

    result = run(go())
    assert result == {"duplicate": True, "run_id": "run-a", "ts": "1700000000.000001"}
    assert slack.posts == 1


def test_rerun_of_the_claim_step_reuses_the_message():
    slack = FakeSlack()

    async def go():
        async with slack.client() as c:
            first = await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-a")
            again = await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-a")
            return first, again

    first, again = run(go())
    assert again["existing"] is True and again["ts"] == first["ts"]
    assert slack.posts == 1


def test_claim_tag_survives_the_plan_edit():
    slack = FakeSlack()

    async def go():
        async with slack.client() as c:
            claim = await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-a")
            await update_message(
                c, "xoxb", CHANNEL, claim["ts"], "Research plan",
                payload={"kind": "claim", "event_id": "Ev1", "run_id": "run-a"},
            )
            return await claim_event(c, "xoxb", CHANNEL, THREAD, "Ev1", "run-b")

    assert run(go())["duplicate"] is True
    assert slack.posts == 1


def test_report_is_posted_once_per_run():
    slack = FakeSlack()
    tag = {"kind": "report", "run_id": "run-a"}

    async def go():
        async with slack.client() as c:
            first = await post_once(c, "xoxb", CHANNEL, THREAD, "report", tag, tag)
            again = await post_once(c, "xoxb", CHANNEL, THREAD, "report", tag, tag)
            return first, again

    first, again = run(go())
    assert first["posted"] is True
    assert again == {"posted": False, "existing": True, "ts": first["ts"], "payload": tag}
    assert slack.posts == 1


def test_post_without_history_scope_still_posts_and_says_so():
    slack = FakeSlack(history_error="missing_scope")
    tag = {"kind": "report", "run_id": "run-a"}

    async def go():
        async with slack.client() as c:
            return await post_once(c, "xoxb", CHANNEL, THREAD, "report", tag, tag)

    result = run(go())
    assert result["posted"] is True and result["unchecked"] == "missing_scope"
