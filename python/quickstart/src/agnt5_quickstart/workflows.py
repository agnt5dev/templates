from agnt5 import WorkflowContext, workflow

from agnt5_quickstart.functions import MissingAPIKeyError, fetch_article, summarize


@workflow
async def research(ctx: WorkflowContext, url: str) -> dict:
    """Fetch an article and summarize it."""
    # Step 1: Fetch (checkpointed)
    content = await ctx.task(fetch_article, url=url)
    ctx.logger.info(f"Fetched article from {url}")

    # Step 2: Summarize (checkpointed)
    try:
        summary = await ctx.task(summarize, content=content)
        ctx.logger.info(f"Summarized article from {url}")
    except MissingAPIKeyError as e:
        ctx.logger.warning(str(e))
        return {
            "url": url,
            "error": str(e),
            "status": "failed",
            "step": "summarize",
        }

    return {"url": url, "summary": summary, "status": "success"}


@workflow
async def hello_world_wf(ctx: WorkflowContext, name: str) -> dict:
    """Say hello to the world."""
    ctx.logger.info(f"Hello, {name}!")

    greeting = f"Hello, {name}!"
    ctx.logger.info(f"Received greeting: {greeting}")

    return {"greeting": greeting, "status": "success"}
