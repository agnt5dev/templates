from agnt5 import WorkflowContext, workflow

from agnt5_quickstart.functions import fetch_article, summarize


@workflow
async def research(ctx: WorkflowContext, url: str) -> dict:
    """Fetch an article and summarize it."""
    # Step 1: Fetch (checkpointed)
    content = await ctx.task(fetch_article, url=url)
    ctx.log(f"Fetched article from {url}")

    # Step 2: Summarize (checkpointed)
    summary = await ctx.task(summarize, content=content)
    ctx.log(f"Summarized article from {url}")

    return {"url": url, "summary": summary}
