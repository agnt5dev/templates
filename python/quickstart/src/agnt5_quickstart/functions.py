import os

import httpx
from agnt5 import FunctionContext, function, lm


class MissingAPIKeyError(Exception):
    """Raised when a required API key is not configured."""

    pass


@function
async def fetch_article(ctx: FunctionContext, url: str) -> str:
    """Fetch article content from a URL."""
    ctx.logger.info(f"Fetching {url}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text


@function
async def summarize(ctx: FunctionContext, content: str) -> str:
    """Summarize content using an LLM."""
    if not os.getenv("OPENAI_API_KEY"):
        raise MissingAPIKeyError(
            "OPENAI_API_KEY environment variable is required. "
            "Add it to your .env file: OPENAI_API_KEY=sk-your-key-here"
        )

    ctx.logger.info("Summarizing with LLM...")
    response = await lm.generate(
        model="openai/gpt-4o-mini",
        prompt=f"Summarize this article in 2-3 sentences:\n\n{content[:4000]}",
    )
    return response.text


@function
async def hello_world(ctx: FunctionContext, name: str) -> str:
    """Say hello to the world."""
    return f"Hello, {name}!"
