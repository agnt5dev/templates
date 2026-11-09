"""The run must not pause for a click unless Slack is showing the plan's buttons."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slack_deep_research import approval, workflows  # noqa: E402
from slack_deep_research.approval import PlanNotShownError  # noqa: E402

CHANNEL, THREAD = "C1", "1700000000.000100"


class FakeSlack:
    """One thread. chat.update and chat.postMessage can be made to fail."""

    def __init__(self, update_error: str = "", post_error: str = ""):
        self.update_error, self.post_error = update_error, post_error
        self.messages: list[dict] = [{"ts": THREAD, "text": "<@BOT> research raft"}]
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        self.calls.append(method)
        if method == "conversations.replies":
            return httpx.Response(200, json={"ok": True, "messages": self.messages})
        body = json.loads(request.content)
        if method == "chat.postMessage":
            if self.post_error:
                return httpx.Response(200, json={"ok": False, "error": self.post_error})
            ts = f"1700000000.{len(self.messages):06d}"
            self.messages.append({"ts": ts, "text": body["text"], "metadata": body.get("metadata")})
            return httpx.Response(200, json={"ok": True, "ts": ts})
        if method == "chat.update":
            if self.update_error:
                return httpx.Response(200, json={"ok": False, "error": self.update_error})
            return httpx.Response(200, json={"ok": True, "ts": body["ts"]})
        return httpx.Response(404)


class Logger:
    def __getattr__(self, _level):
        return lambda *args, **kwargs: None


class FakeContext:
    """Runs steps inline, once each, and records the pause."""

    run_id = "run-a"
    logger = Logger()

    def __init__(self):
        self.steps: list[str] = []
        self.paused = False

    async def step(self, fn, *args):
        self.steps.append(fn.__name__)
        if fn is approval._post_report:
            raise AssertionError("not reached in these tests")
        if fn.__name__ == "_plan_research":
            return "1. Look things up"
        return await fn.__wrapped__(self, *args)

    async def wait_for_user(self, **_kwargs):
        self.paused = True
        return "reject"


@pytest.fixture
def slack(monkeypatch):
    def install(**errors) -> FakeSlack:
        fake = FakeSlack(**errors)
        real_client = httpx.AsyncClient

        def mocked(**kwargs):
            return real_client(transport=httpx.MockTransport(fake.handler), **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", mocked)  # approval and slack_once share the module
        return fake

    return install


def envelope(bot_token: str = "xoxb-test") -> dict:
    event = {"type": "app_mention", "text": "<@U1> research raft", "channel": CHANNEL, "user": "U2", "ts": THREAD}
    return {"bot_token": bot_token, "body": {"event_id": "Ev1", "event": event}}


def run_workflow(ctx: FakeContext, env: dict):
    return asyncio.run(workflows.slack_deep_research.__wrapped__(ctx, **env))


def test_plan_shown_then_pauses_for_the_click(slack):
    slack()
    ctx = FakeContext()
    result = run_workflow(ctx, envelope())
    assert ctx.paused and result["status"] == "rejected"


def test_rejected_plan_update_fails_the_run_instead_of_pausing(slack):
    fake = slack(update_error="invalid_blocks")
    ctx = FakeContext()
    with pytest.raises(PlanNotShownError, match="invalid_blocks"):
        run_workflow(ctx, envelope())
    assert not ctx.paused
    notices = [m for m in fake.messages if (m.get("metadata") or {}).get("event_payload", {}).get("kind") == "error"]
    assert len(notices) == 1 and "couldn't post the research plan" in notices[0]["text"]


def test_failed_claim_stops_before_planning(slack):
    slack(post_error="not_in_channel")
    ctx = FakeContext()
    with pytest.raises(PlanNotShownError, match="not_in_channel"):
        run_workflow(ctx, envelope())
    assert "_plan_research" not in ctx.steps and not ctx.paused


def test_without_slack_the_run_still_pauses_for_the_resume_api(slack):
    fake = slack()
    ctx = FakeContext()
    run_workflow(ctx, envelope(bot_token=""))
    assert ctx.paused and fake.calls == []
