/**
 * Deep Research Tools
 *
 * Tools for fetching web content and searching Wikipedia,
 * used by the Research Agent during subtopic investigation.
 */

import { tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

export const fetchWebpage = tool(
  'fetch_webpage',
  {
    description: 'Fetch and extract text content from a webpage for research purposes',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'The webpage URL to fetch' },
      },
      required: ['url'],
    },
  },
  async (ctx: Context, args: { url: string }) => {
    const { url } = args;
    ctx.logger.info(`Fetching webpage: ${url.slice(0, 100)}...`);

    const headers = { 'User-Agent': 'Mozilla/5.0 (AGNT5-DeepResearch/1.0)' };

    try {
      const response = await fetch(url, { headers, signal: AbortSignal.timeout(30_000) });
      if (!response.ok) {
        return `HTTP error ${response.status} fetching ${url}`;
      }

      const contentType = response.headers.get('content-type') ?? '';
      if (!contentType.includes('text/html')) {
        return `Content type '${contentType}' is not supported for URL: ${url}`;
      }

      const html = await response.text();

      // Strip tags and condense whitespace (no external HTML parser needed)
      const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
      const titleText = titleMatch ? titleMatch[1].trim() : 'Untitled';

      // Remove script/style blocks
      let text = html
        .replace(/<script[\s\S]*?<\/script>/gi, ' ')
        .replace(/<style[\s\S]*?<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        // Strip non-ASCII characters — the SDK telemetry truncates tool results at
        // 10 000 bytes using a fixed byte index; multi-byte Unicode chars (e.g. from
        // Wikipedia) can land on a non-char boundary and panic the Rust runtime.
        .replace(/[^\x00-\x7F]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

      // Truncate to 5 000 chars — conservative ceiling that keeps the total tool-result
      // payload (including the telemetry prefix) well below the 10 000-byte hard limit.
      const MAX = 5000;
      if (text.length > MAX) {
        const truncated = text.slice(0, MAX);
        const lastDot = truncated.lastIndexOf('.');
        text = lastDot > MAX * 0.8
          ? truncated.slice(0, lastDot + 1) + ' ... [truncated]'
          : truncated + ' ... [truncated]';
      }

      ctx.logger.info(`Fetched ${text.length} characters from ${url}`);
      return `Title: ${titleText}\nURL: ${url}\n\nContent:\n${text}`;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ctx.logger.error(`Error fetching ${url}: ${msg}`);
      return `Error fetching ${url}: ${msg}`;
    }
  },
);

export const wikipediaSearch = tool(
  'wikipedia_search',
  {
    description: 'Search Wikipedia for articles related to the research query',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search term or phrase to look up on Wikipedia' },
        max_results: { type: 'number', description: 'Maximum number of articles to return (default 3)' },
      },
      required: ['query'],
    },
  },
  async (ctx: Context, args: { query: string; max_results?: number }) => {
    const { query, max_results = 3 } = args;
    ctx.logger.info(`Wikipedia search: ${query.slice(0, 100)}...`);

    const params = new URLSearchParams({
      action: 'query',
      list: 'search',
      srsearch: query,
      format: 'json',
      srlimit: String(Math.min(max_results, 50)),
      srwhat: 'text',
    });

    const headers = { 'User-Agent': 'AGNT5-DeepResearch/1.0' };
    const MAX_RETRIES = 3;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const response = await fetch(
          `https://en.wikipedia.org/w/api.php?${params}`,
          { headers, signal: AbortSignal.timeout(30_000) },
        );

        if (response.status === 429) {
          const wait = Math.pow(2, attempt) * 3000; // 3s, 6s, 12s
          ctx.logger.warn(`Wikipedia rate-limited, retrying in ${wait / 1000}s (attempt ${attempt + 1}/${MAX_RETRIES})`);
          await new Promise(r => setTimeout(r, wait));
          continue;
        }

        if (!response.ok) {
          return `Wikipedia search failed with HTTP ${response.status} for query: ${query}`;
        }

        const data = (await response.json()) as Record<string, any>;

        if (data.error) {
          return `Wikipedia API error: ${JSON.stringify(data.error)}`;
        }

        const results: any[] = data?.query?.search ?? [];
        if (results.length === 0) {
          return `No Wikipedia articles found for query: ${query}`;
        }

        const formatted = results.map((r: any) => {
          const snippet = (r.snippet ?? '')
            .replace(/<span class="searchmatch">/g, '')
            .replace(/<\/span>/g, '')
            .replace(/&quot;/g, '"')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>');
          const urlTitle = (r.title ?? '').replace(/ /g, '_');
          const url = `https://en.wikipedia.org/wiki/${urlTitle}`;
          return `Title: ${r.title}\nURL: ${url}\nSnippet: ${snippet}`;
        });

        ctx.logger.info(`Found ${results.length} Wikipedia articles`);
        return `Wikipedia search results for '${query}':\n\n${formatted.join('\n---\n')}`;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        ctx.logger.error(`Wikipedia search error: ${msg}`);
        return `Wikipedia search failed for '${query}': ${msg}`;
      }
    }

    return `Wikipedia search failed after ${MAX_RETRIES} retries (rate limited) for query: ${query}`;
  },
);
