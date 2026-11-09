"""The `translate_article` workflow: one article in, five published languages out.

Fifteen LLM translations, each its own checkpoint. Crash halfway and only the
missing translations run again. A week later the run wakes up and re-translates
just the sections that changed.
"""
from __future__ import annotations

import asyncio
import os

from agnt5 import WorkflowContext, workflow

from content_translator.demo import approved, crash_point
from content_translator.functions import (
    build_report,
    check_source_changes,
    load_article,
    load_glossary,
    publish_language,
    translate_section,
)

# Durable sleeps in this demo are measured in "days". Set to 86400 for real time;
# the default turns the 7-day wait into 70 seconds.
SECONDS_PER_DAY = float(os.getenv("TRANSLATOR_SECONDS_PER_DAY", "10"))

LANGUAGES = ["es", "fr", "de", "ja", "ar"]
NEEDS_NATIVE_REVIEW = ["ja", "ar"]


@workflow
async def translate_article(
    ctx: WorkflowContext,
    slug: str = "launch-week-recap",
    refresh_after_days: float = 7.0,
    flaky_failures: int = 0,
    crash_at: str | None = None,
) -> dict:
    """Translate, review, publish, wait a week, re-translate what changed.

    Demo inputs:
        flaky_failures: make the glossary service fail this many times (retries absorb it).
        crash_at: kill the worker once at "after_<lang>" (e.g. "after_fr") or "after_refresh_wait".
    """
    article = await ctx.step(load_article, slug)
    glossary = await ctx.step(load_glossary, flaky_failures)

    # 1. One language at a time, its sections in parallel. Every translation is
    #    its own checkpoint, keyed by (section, language).
    translations: dict[str, list[dict]] = {}
    for lang in LANGUAGES:
        translations[lang] = list(
            await asyncio.gather(
                *[
                    ctx.step(translate_section, section, text, lang, glossary, key=f"{section}-{lang}")
                    for section, text in article["sections"].items()
                ]
            )
        )
        await crash_point(ctx, crash_at, f"after_{lang}")

    # 2. Some languages need a native speaker's sign-off. Each review is its own
    #    pause; the run is not in memory between them.
    approved_langs = [lang for lang in LANGUAGES if lang not in NEEDS_NATIVE_REVIEW]
    for lang in NEEDS_NATIVE_REVIEW:
        preview = "\n".join(t["text"] for t in translations[lang])
        answer = await ctx.wait_for_user(
            f"Native review ({lang}): publish this translation?\n\n{preview}",
            input_type="approval",
            options=[{"id": "approve", "label": "Publish"}, {"id": "reject", "label": "Needs work"}],
        )
        if approved(answer):
            approved_langs.append(lang)

    # 3. Publish each approved language, exactly once.
    published = [
        await ctx.step(publish_language, slug, lang, translations[lang], key=f"{lang}-v1")
        for lang in approved_langs
    ]

    # 4. Wait a week, then refresh only what changed in the source.
    await ctx.sleep(refresh_after_days * SECONDS_PER_DAY, name="refresh_wait")
    await crash_point(ctx, crash_at, "after_refresh_wait")

    edits = await ctx.step(check_source_changes, slug)
    refreshed = []
    for lang in approved_langs:
        updates = await asyncio.gather(
            *[
                ctx.step(translate_section, section, text, lang, glossary, key=f"{section}-{lang}-v2")
                for section, text in edits.items()
            ]
        )
        merged = [t for t in translations[lang] if t["section"] not in edits] + list(updates)
        refreshed.append(await ctx.step(publish_language, slug, lang, merged, 2, key=f"{lang}-v2"))

    needed = len(LANGUAGES) * len(article["sections"]) + len(approved_langs) * len(edits)
    report = await ctx.step(build_report, needed)
    return {
        "slug": slug,
        "approved_languages": approved_langs,
        "published": published,
        "refreshed": refreshed,
        "execution_report": report,
    }
