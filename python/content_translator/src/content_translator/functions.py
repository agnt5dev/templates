"""Steps for the translation workflow.

Each `@function` becomes a durable step when the workflow calls it through
`ctx.step(...)`: its result is checkpointed, and a replay returns the
checkpoint instead of running the code again.
"""
from __future__ import annotations

import asyncio
import os
from collections import Counter

from agnt5 import FunctionContext, function, lm

from content_translator.demo import log_execution, mock_mode, read_execution_log
from content_translator.outbox import idempotency_key, send_once

MODEL = os.getenv("TRANSLATOR_MODEL", "openai/gpt-6-luna")

ARTICLE = {
    "slug": "launch-week-recap",
    "sections": {
        "intro": "Launch week is over. Here is everything we shipped, in one place.",
        "features": "Workflows now survive crashes, wait for approvals, and sleep for days without holding a server.",
        "pricing": "Every plan now includes 10,000 workflow runs per month at no extra cost.",
    },
}
# The source article as it reads a week later: the pricing section was edited.
ARTICLE_EDITS = {"pricing": "Every plan now includes 25,000 workflow runs per month at no extra cost."}
GLOSSARY = {"workflow": "do-not-translate", "run": "do-not-translate"}


async def _generate(system: str, prompt: str, mock: str) -> str:
    if mock_mode():
        await asyncio.sleep(float(os.getenv("TRANSLATOR_MOCK_LATENCY_S", "1.5")))
        return mock
    response = await lm.generate(model=MODEL, system_prompt=system, prompt=prompt)
    return response.text.strip()


class GlossaryUnavailable(Exception):
    """The (simulated) terminology service returned a 503. Retryable."""


@function
async def load_article(ctx: FunctionContext, slug: str) -> dict:
    """Load the source article (a bundled sample)."""
    log_execution(ctx.run_id, "load_article", slug)
    return ARTICLE


@function(retries=4, backoff="exponential")
async def load_glossary(ctx: FunctionContext, flaky_failures: int = 0) -> dict:
    """Fetch the product glossary. Fails `flaky_failures` times first; retries absorb it."""
    log_execution(ctx.run_id, "load_glossary", attempt=ctx.attempt)
    if ctx.attempt < flaky_failures:
        ctx.logger.warning("Glossary service returned 503 (attempt %d) - will retry", ctx.attempt + 1)
        raise GlossaryUnavailable(f"glossary service returned 503 on attempt {ctx.attempt + 1}")
    return GLOSSARY


@function
async def translate_section(ctx: FunctionContext, section: str, text: str, lang: str, glossary: dict) -> dict:
    """Translate one section into one language. One LLM call, one checkpoint."""
    log_execution(ctx.run_id, "translate_section", f"{section}:{lang}")
    keep = ", ".join(term for term, rule in glossary.items() if rule == "do-not-translate")
    translated = await _generate(
        f"Translate into {lang}. Keep these terms in English: {keep}. Return only the translation.",
        text,
        f"[{lang}] {text}",
    )
    return {"section": section, "lang": lang, "text": translated}


@function
async def publish_language(ctx: FunctionContext, slug: str, lang: str, sections: list[dict], version: int = 1) -> dict:
    """Publish one language version of the article, once."""
    log_execution(ctx.run_id, "publish_language", f"{lang}:v{version}")
    page = {"slug": slug, "lang": lang, "version": version, "sections": sections}
    published = send_once(idempotency_key(ctx, f"{lang}:v{version}"), page)
    return {"lang": lang, "version": version, "published": published, "duplicate_skipped": not published}


@function
async def check_source_changes(ctx: FunctionContext, slug: str) -> dict:
    """A week later: which sections of the source article were edited? (simulated CMS)"""
    log_execution(ctx.run_id, "check_source_changes", slug)
    return ARTICLE_EDITS


@function
async def build_report(ctx: FunctionContext, translations_needed: int) -> dict:
    """Summarize how many times each step's code actually ran in this run."""
    executions = Counter(e["step"] for e in read_execution_log(ctx.run_id))
    return {
        "translations_needed": translations_needed,
        "llm_translations_run": executions["translate_section"],
        "step_executions": dict(executions),
    }
