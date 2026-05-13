"""Steps for the Hacker News digest workflow.

Each `@function` is a durable step. When called via `ctx.task(...)` inside a
workflow, it checkpoints — a worker restart skips steps that already completed.
"""
from __future__ import annotations

import httpx

from agnt5 import Agent, FunctionContext, function

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

SUMMARIZER_PROMPT = """You are summarizing a Hacker News story for a busy
engineer. Given a title and (if available) a URL, write 1-2 plain sentences
covering what the story is and why it might matter. No marketing language."""

summarizer = Agent(
    name="hn_summarizer",
    model="openai/gpt-5-mini",
    instructions=SUMMARIZER_PROMPT,
)


@function
async def fetch_top_ids(ctx: FunctionContext, limit: int = 5) -> list[int]:
    """Return the first `limit` IDs from the HN top-stories feed."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(HN_TOP)
        resp.raise_for_status()
        ids = resp.json()
    ctx.logger.info("Fetched %d top IDs, taking first %d", len(ids), limit)
    return ids[:limit]


@function
async def fetch_story(ctx: FunctionContext, story_id: int) -> dict:
    """Fetch one HN story by ID."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(HN_ITEM.format(id=story_id))
        resp.raise_for_status()
        story = resp.json() or {}
    return {
        "id": story_id,
        "title": story.get("title", "(no title)"),
        "url": story.get("url"),
        "score": story.get("score", 0),
        "by": story.get("by"),
    }


@function
async def summarize(ctx: FunctionContext, story: dict) -> dict:
    """Summarize one story with a small model call."""
    prompt = f"Title: {story['title']}\nURL: {story.get('url') or '(no link)'}"
    result = await summarizer.run(user_message=prompt, context=ctx)
    return {
        "id": story["id"],
        "title": story["title"],
        "url": story.get("url"),
        "summary": result.output.strip(),
    }


@function
async def assemble_digest(ctx: FunctionContext, summaries: list[dict]) -> dict:
    """Combine the per-story summaries into a single readable digest."""
    lines = ["# Hacker News digest\n"]
    for i, s in enumerate(summaries, start=1):
        link = f" — {s['url']}" if s.get("url") else ""
        lines.append(f"{i}. **{s['title']}**{link}\n   {s['summary']}\n")
    body = "\n".join(lines)
    return {
        "count": len(summaries),
        "digest": body,
    }
