/**
 * The `translate_article` workflow: one article in, five published languages out.
 *
 * Fifteen LLM translations, each its own checkpoint. Crash halfway and only
 * the missing translations run again. A week later the run wakes up and
 * re-translates just the sections that changed.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { approved, crashPoint, step } from './demo.js';
import {
  buildReport,
  checkSourceChanges,
  loadArticle,
  loadGlossary,
  publishLanguage,
  translateSection,
} from './functions.js';
import type { Article, Published, Translation } from './functions.js';

// Durable sleeps in this demo are measured in "days". Set to 86400 for real
// time; the default turns the 7-day wait into 70 seconds.
const MS_PER_DAY = Number(process.env.TRANSLATOR_SECONDS_PER_DAY ?? 10) * 1000;

const LANGUAGES = ['es', 'fr', 'de', 'ja', 'ar'];
const NEEDS_NATIVE_REVIEW = ['ja', 'ar'];

export interface TranslateArticleInput {
  slug?: string;
  refresh_after_days?: number;
  /** Make the glossary service fail this many times (retries absorb it). */
  flaky_failures?: number;
  /** Kill the worker once at "after_<lang>" (e.g. "after_fr") or "after_refresh_wait". */
  crash_at?: string;
}

export const translateArticle = workflow(
  'translate_article',
  async (ctx: Context, input: TranslateArticleInput = {}) => {
    const slug = input.slug ?? 'launch-week-recap';
    const article = await step<Article>(ctx, 'load_article', () => loadArticle(ctx, { slug }));
    const glossary = await step<Record<string, string>>(ctx, 'load_glossary', () =>
      loadGlossary(ctx, { flakyFailures: input.flaky_failures ?? 0 }),
    );

    // 1. One language at a time, its sections in parallel. Every translation
    //    is its own checkpoint, keyed by (section, language).
    const translate = (sections: Record<string, string>, lang: string, suffix = '') =>
      Promise.all(
        Object.entries(sections).map(([section, text]) =>
          step<Translation>(
            ctx, 'translate_section',
            () => translateSection(ctx, { section, text, lang, glossary }),
            `${section}-${lang}${suffix}`,
          ),
        ),
      );

    const translations: Record<string, Translation[]> = {};
    for (const lang of LANGUAGES) {
      translations[lang] = await translate(article.sections, lang);
      await crashPoint(ctx, input.crash_at, `after_${lang}`);
    }

    // 2. Some languages need a native speaker's sign-off. Each review is its
    //    own pause; the run is not in memory between them.
    const approvedLangs = LANGUAGES.filter((lang) => !NEEDS_NATIVE_REVIEW.includes(lang));
    for (const lang of NEEDS_NATIVE_REVIEW) {
      const preview = translations[lang].map((t) => t.text).join('\n');
      const answer = await ctx.waitForUser(`Native review (${lang}): publish this translation?\n\n${preview}`, {
        inputType: 'approval',
        options: [
          { id: 'approve', label: 'Publish' },
          { id: 'reject', label: 'Needs work' },
        ],
      });
      if (approved(answer)) approvedLangs.push(lang);
    }

    // 3. Publish each approved language, exactly once.
    const published: Published[] = [];
    for (const lang of approvedLangs) {
      published.push(
        await step<Published>(
          ctx, 'publish_language',
          () => publishLanguage(ctx, { slug, lang, sections: translations[lang] }),
          `${lang}-v1`,
        ),
      );
    }

    // 4. Wait a week, then refresh only what changed in the source.
    await ctx.sleep((input.refresh_after_days ?? 7) * MS_PER_DAY, 'refresh_wait');
    await crashPoint(ctx, input.crash_at, 'after_refresh_wait');

    const edits = await step<Record<string, string>>(ctx, 'check_source_changes', () =>
      checkSourceChanges(ctx, { slug }),
    );
    const refreshed: Published[] = [];
    for (const lang of approvedLangs) {
      const updates = await translate(edits, lang, '-v2');
      const merged = [...translations[lang].filter((t) => !(t.section in edits)), ...updates];
      refreshed.push(
        await step<Published>(
          ctx, 'publish_language',
          () => publishLanguage(ctx, { slug, lang, sections: merged, version: 2 }),
          `${lang}-v2`,
        ),
      );
    }

    const needed = LANGUAGES.length * Object.keys(article.sections).length +
      approvedLangs.length * Object.keys(edits).length;
    const report = await step(ctx, 'build_report', () => buildReport(ctx, { translationsNeeded: needed }));
    return { slug, approved_languages: approvedLangs, published, refreshed, execution_report: report };
  },
);
