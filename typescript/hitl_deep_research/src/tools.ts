/**
 * Deep Research Tools
 *
 * Tools for fetching web content and searching Wikipedia,
 * used by the Research Agent during subtopic investigation.
 */

import { tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';
import * as dns from 'node:dns';
import * as http from 'node:http';
import * as https from 'node:https';
import { BlockList, isIP } from 'node:net';

// The webpage tool fetches whatever URL the model hands it, so the connection
// enforces a destination policy rather than trusting the argument: a prompt
// that says "read http://169.254.169.254/latest/meta-data/" would otherwise
// make the worker fetch cloud credentials and hand them back as research
// (AGNT5-1165, the TypeScript port of the Go fix in AGNT5-1160).
//
// node:http and node:https are used instead of fetch because they accept a
// custom `lookup`: the hostname is resolved exactly once, every address is
// validated, and the socket goes to one of those addresses. Validating first
// and letting fetch resolve again would leave a window for DNS rebinding -- a
// public answer for the check, a private one for the connection. Redirects
// are followed by hand so every hop goes through the same lookup.

export const MAX_WEBPAGE_BYTES = 2 * 1024 * 1024;
const MAX_REDIRECTS = 5;

// Everything that is the machine or its network rather than the public
// internet. Link-local covers the cloud metadata endpoints.
const privateRanges = new BlockList();
for (const [subnet, prefix] of [
  ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8], ['169.254.0.0', 16],
  ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.168.0.0', 16], ['198.18.0.0', 15], ['224.0.0.0', 4], ['240.0.0.0', 4],
] as Array<[string, number]>) {
  privateRanges.addSubnet(subnet, prefix, 'ipv4');
}
for (const [subnet, prefix] of [['::', 128], ['::1', 128], ['fc00::', 7], ['fe80::', 10], ['ff00::', 8]] as Array<[string, number]>) {
  privateRanges.addSubnet(subnet, prefix, 'ipv6');
}

export function isPrivateAddress(ip: string): boolean {
  const family = isIP(ip);
  if (family === 0) return true; // unparseable is not something to connect to
  // An IPv4 address carried inside IPv6 (::ffff:127.0.0.1) is the IPv4 address.
  const mapped = ip.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/i);
  if (mapped) return privateRanges.check(mapped[1], 'ipv4');
  return privateRanges.check(ip, family === 6 ? 'ipv6' : 'ipv4');
}

type LookupCallback = (err: NodeJS.ErrnoException | null, address: any, family?: number) => void;

// Resolve once, refuse if any answer is private, hand back only validated
// addresses. Rejecting on any private answer, rather than skipping it, closes
// the mixed-answer variant of rebinding. net.connect may ask with `all: true`
// (address selection) or for a single address; both shapes are served.
export function publicOnlyLookup(hostname: string, options: any, callback: LookupCallback): void {
  const opts = typeof options === 'object' && options !== null ? options : {};
  dns.lookup(hostname, { ...opts, all: true }, (err, addresses) => {
    if (err) return callback(err, undefined);
    const list = addresses as unknown as Array<{ address: string; family: number }>;
    if (!list.length) return callback(new Error(`${hostname} resolved to no addresses`), undefined);
    for (const a of list) {
      if (isPrivateAddress(a.address)) {
        return callback(new Error(`refusing to connect to ${hostname}: it resolves to the private address ${a.address}`), undefined);
      }
    }
    if (opts.all) return callback(null, list);
    callback(null, list[0].address, list[0].family);
  });
}

export function checkResearchUrl(raw: string): { url: URL } | { refusal: string } {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return { refusal: 'not a valid URL' };
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return { refusal: `unsupported URL scheme ${url.protocol.replace(':', '')}: only http and https are fetched` };
  }
  if (!url.hostname) return { refusal: 'URL has no host' };
  return { url };
}

interface PolicedResponse {
  status: number;
  contentType: string;
  body: string;
  truncated: boolean;
}

// A literal address in the URL never reaches `lookup`: net.connect sees that
// the host is already an IP and connects to it directly. So the most common
// SSRF payload -- http://169.254.169.254/ -- bypassed the hook entirely, which
// a production probe caught after a unit test of the hook alone had passed.
// Literals are checked here; names are checked in the lookup.
export function refuseLiteralPrivateAddress(url: URL): string | null {
  const host = url.hostname.replace(/^\[|\]$/g, ''); // IPv6 literals are bracketed
  if (isIP(host) !== 0 && isPrivateAddress(host)) {
    return `refusing to connect to ${host}: it is the private address ${host}`;
  }
  return null;
}

// One request through the policed lookup, body read up to MAX_WEBPAGE_BYTES.
function requestPoliced(url: URL, headers: Record<string, string>, timeoutMs: number): Promise<{ status: number; headers: http.IncomingHttpHeaders; body: string; truncated: boolean }> {
  return new Promise((resolve, reject) => {
    const literal = refuseLiteralPrivateAddress(url);
    if (literal) return reject(new Error(literal));
    const client = url.protocol === 'https:' ? https : http;
    const req = client.request(url, { method: 'GET', headers, lookup: publicOnlyLookup, timeout: timeoutMs }, (res) => {
      const chunks: Buffer[] = [];
      let total = 0;
      let truncated = false;
      res.on('data', (chunk: Buffer) => {
        if (truncated) return;
        const room = MAX_WEBPAGE_BYTES - total;
        if (chunk.length >= room) {
          chunks.push(chunk.subarray(0, room));
          truncated = true;
          res.destroy(); // stop reading; an endless page is otherwise read whole
          return;
        }
        chunks.push(chunk);
        total += chunk.length;
      });
      const finish = () => resolve({ status: res.statusCode ?? 0, headers: res.headers, body: Buffer.concat(chunks).toString('utf8'), truncated });
      res.on('end', finish);
      res.on('close', finish);
      res.on('error', (e) => (truncated ? finish() : reject(e)));
    });
    req.on('timeout', () => req.destroy(new Error(`timed out after ${timeoutMs}ms`)));
    req.on('error', reject);
    req.end();
  });
}

// fetchPoliced follows up to MAX_REDIRECTS redirects, each hop through the
// same policed lookup and scheme check.
export async function fetchPoliced(start: URL, headers: Record<string, string>, timeoutMs = 30_000): Promise<PolicedResponse> {
  let url = start;
  for (let hop = 0; ; hop++) {
    const res = await requestPoliced(url, headers, timeoutMs);
    if (res.status >= 300 && res.status < 400 && res.headers.location) {
      if (hop >= MAX_REDIRECTS) throw new Error(`stopped after ${MAX_REDIRECTS} redirects`);
      const next = checkResearchUrl(new URL(res.headers.location, url).toString());
      if ('refusal' in next) throw new Error(`redirect refused: ${next.refusal}`);
      url = next.url;
      continue;
    }
    return { status: res.status, contentType: String(res.headers['content-type'] ?? ''), body: res.body, truncated: res.truncated };
  }
}

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

    const checked = checkResearchUrl(url);
    if ('refusal' in checked) {
      ctx.logger.error(`Refused webpage fetch for ${url.slice(0, 100)}: ${checked.refusal}`);
      return `Refused to fetch ${url}: ${checked.refusal}`;
    }

    try {
      const response = await fetchPoliced(checked.url, headers);
      if (response.status < 200 || response.status >= 300) {
        return `HTTP error ${response.status} fetching ${url}`;
      }

      const contentType = response.contentType;
      if (!contentType.includes('text/html')) {
        return `Content type '${contentType}' is not supported for URL: ${url}`;
      }

      const html = response.body;

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
