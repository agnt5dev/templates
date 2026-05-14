"""The `digest` workflow — fan out across the top Hacker News stories.

Every `ctx.task(...)` is a durable checkpoint. If the worker crashes after some
stories have been summarized, the runtime re-runs only the missing ones — model
calls included.
"""
from __future__ import annotations

import asyncio

from agnt5 import WorkflowContext, workflow

from agnt5_quickstart.functions import (
    assemble_digest,
    fetch_story,
    fetch_top_ids,
    summarize,
)


@workflow
async def digest(ctx: WorkflowContext, limit: int = 5) -> dict:
    """Fetch the top `limit` HN stories, summarize them in parallel, assemble.

    Trace shape:
        digest (workflow)
        ├─ fetch_top_ids
        ├─ fetch_story (×N parallel)
        ├─ summarize   (×N parallel)
        └─ assemble_digest
    """
    ctx.logger.info("Starting digest for top %d stories", limit)

    # 1. One checkpoint: pull the IDs.
    ids = await ctx.task(fetch_top_ids, limit=limit)

    # 2. Fan out: each fetch_story is its own checkpoint. asyncio.gather runs
    #    them concurrently. A worker restart resumes from whichever of these
    #    had completed.
    stories = await asyncio.gather(*[
        ctx.task(fetch_story, story_id=i) for i in ids
    ])

    # 3. Fan out again on summarization. The Agent inside each `summarize`
    #    call passes `context=ctx`, so model calls also checkpoint.
    summaries = await asyncio.gather(*[
        ctx.task(summarize, story=s) for s in stories
    ])

    # 4. Combine. One last checkpoint, then return.
    return await ctx.task(assemble_digest, summaries=summaries)
