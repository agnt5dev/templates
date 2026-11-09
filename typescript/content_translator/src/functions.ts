/**
 * Steps for the translation workflow.
 *
 * Each `fn(...)` is a function the workflow runs inside `ctx.step(...)`: its
 * result is checkpointed, and a replay returns the checkpoint instead of
 * running the code again (see workflows.ts).
 */

import { setTimeout as sleep } from 'node:timers/promises';
import { Agent, LM, fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { idempotencyKey, logExecution, mockMode, readExecutionLog } from './demo.js';
import { sendOnce } from './outbox.js';

const MODEL = process.env.TRANSLATOR_MODEL || 'openai/gpt-6-luna';

export interface Article {
  slug: string;
  sections: Record<string, string>;
}

export interface Translation {
  section: string;
  lang: string;
  text: string;
}

export interface Published {
  lang: string;
  version: number;
  published: boolean;
  duplicate_skipped: boolean;
}

const ARTICLE: Article = {
  slug: 'launch-week-recap',
  sections: {
    intro: 'Launch week is over. Here is everything we shipped, in one place.',
    features: 'Workflows now survive crashes, wait for approvals, and sleep for days without holding a server.',
    pricing: 'Every plan now includes 10,000 workflow runs per month at no extra cost.',
  },
};
// The source article as it reads a week later: the pricing section was edited.
const ARTICLE_EDITS: Record<string, string> = {
  pricing: 'Every plan now includes 25,000 workflow runs per month at no extra cost.',
};
const GLOSSARY: Record<string, string> = { workflow: 'do-not-translate', run: 'do-not-translate' };

async function generate(ctx: Context, instructions: string, prompt: string, mock: string): Promise<string> {
  if (mockMode()) {
    await sleep(Number(process.env.TRANSLATOR_MOCK_LATENCY_MS ?? 1500));
    return mock;
  }
  const agent = new Agent({
    name: 'translator',
    model: LM.openai(),
    modelName: MODEL,
    temperature: 1, // gpt-6 accepts only its default temperature
    instructions,
  });
  return (await agent.run(prompt, ctx)).output.trim();
}

// Load the source article (a bundled sample).
export const loadArticle = fn('load_article').run(async (ctx: Context, input: { slug: string }): Promise<Article> => {
  logExecution(ctx.runId, 'load_article', input.slug);
  return ARTICLE;
});

// Fetch the product glossary. Fails `flakyFailures` times first; retries absorb it.
export const loadGlossary = fn('load_glossary')
  .retry({ maxAttempts: 4, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential' })
  .run(async (ctx: Context, input: { flakyFailures: number }): Promise<Record<string, string>> => {
    logExecution(ctx.runId, 'load_glossary', '', ctx.attempt);
    if (ctx.attempt < input.flakyFailures) {
      ctx.logger.warn(`Glossary service returned 503 (attempt ${ctx.attempt + 1}) - will retry`);
      throw new Error(`glossary service returned 503 on attempt ${ctx.attempt + 1}`);
    }
    return GLOSSARY;
  });

// Translate one section into one language. One LLM call, one checkpoint.
export const translateSection = fn('translate_section').run(
  async (
    ctx: Context,
    input: { section: string; text: string; lang: string; glossary: Record<string, string> },
  ): Promise<Translation> => {
    const { section, text, lang } = input;
    logExecution(ctx.runId, 'translate_section', `${section}:${lang}`);
    const keep = Object.entries(input.glossary)
      .filter(([, rule]) => rule === 'do-not-translate')
      .map(([term]) => term)
      .join(', ');
    const translated = await generate(
      ctx,
      `Translate into ${lang}. Keep these terms in English: ${keep}. Return only the translation.`,
      text,
      `[${lang}] ${text}`,
    );
    return { section, lang, text: translated };
  },
);

// Publish one language version of the article, once.
export const publishLanguage = fn('publish_language').run(
  async (
    ctx: Context,
    input: { slug: string; lang: string; sections: Translation[]; version?: number },
  ): Promise<Published> => {
    const version = input.version ?? 1;
    logExecution(ctx.runId, 'publish_language', `${input.lang}:v${version}`);
    const page = { slug: input.slug, lang: input.lang, version, sections: input.sections };
    const published = sendOnce(idempotencyKey(ctx, `${input.lang}:v${version}`), page);
    return { lang: input.lang, version, published, duplicate_skipped: !published };
  },
);

// A week later: which sections of the source article were edited? (simulated CMS)
export const checkSourceChanges = fn('check_source_changes').run(
  async (ctx: Context, input: { slug: string }): Promise<Record<string, string>> => {
    logExecution(ctx.runId, 'check_source_changes', input.slug);
    return ARTICLE_EDITS;
  },
);

// Summarize how many times each step's code actually ran in this run.
export const buildReport = fn('build_report').run(async (ctx: Context, input: { translationsNeeded: number }) => {
  const executions: Record<string, number> = {};
  for (const e of readExecutionLog(ctx.runId)) executions[e.step] = (executions[e.step] ?? 0) + 1;
  return {
    translations_needed: input.translationsNeeded,
    llm_translations_run: executions.translate_section ?? 0,
    step_executions: executions,
  };
});
