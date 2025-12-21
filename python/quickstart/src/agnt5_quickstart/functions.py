import httpx
from agnt5 import Context, function, lm


@function
async def fetch_article(ctx: Context, url: str) -> str:
    """Fetch article content from a URL."""
    ctx.logger.info(f"Fetching {url}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text


@function
async def summarize(ctx: Context, content: str) -> str:
    """Summarize content using an LLM."""
    ctx.logger.info("Summarizing with LLM...")
    response = await lm.generate(
        model="openai/gpt-4o-mini",
        prompt=f"Summarize this article in 2-3 sentences:\n\n{content[:4000]}",
    )
    return response.text
