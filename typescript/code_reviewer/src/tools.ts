import { tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';
import { parseAdf } from './utils.js';

// ── Plain implementation functions (also called from functions.ts) ────────────

export async function callJiraApiImpl(
  _ctx: Context,
  url: string,
  auth: [string, string],
): Promise<Record<string, any>> {
  const [email, token] = auth;
  const credentials = Buffer.from(`${email}:${token}`).toString('base64');
  const response = await fetch(url, {
    headers: {
      Authorization: `Basic ${credentials}`,
      Accept: 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error(`Jira API error: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<Record<string, any>>;
}

export async function callLinearApiImpl(
  _ctx: Context,
  ticketId: string,
  linearToken: string,
): Promise<Record<string, any>> {
  const url = 'https://api.linear.app/graphql';
  const query = {
    query: `
    {
        issue(id: "${ticketId}") {
            id
            identifier
            title
            description
            url
            state { name }
            assignee { name }
            team { name key }
            priority
            createdAt
            updatedAt
            dueDate
        }
    }
    `,
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: linearToken,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(query),
  });
  if (!response.ok) {
    throw new Error(`Linear API error: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<Record<string, any>>;
}

export async function callGithubApiImpl(
  _ctx: Context,
  url: string,
  headers: Record<string, string>,
): Promise<Record<string, any>> {
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`GitHub API error: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<Record<string, any>>;
}

// ── Tool: jira_ticket_fetcher ─────────────────────────────────────────────────

export const jiraTicketFetcher = tool(
  'jira_ticket_fetcher',
  {
    description: 'Fetch Jira issue details via REST API (v3).',
    inputSchema: {
      type: 'object' as const,
      properties: {
        ticket_url: {
          type: 'string',
          description: 'Full Jira ticket URL (e.g., https://company.atlassian.net/browse/PROJ-123)',
        },
      },
      required: ['ticket_url'],
    },
  },
  async (ctx: Context, args: { ticket_url: string }) => {
    const { ticket_url } = args;
    const jiraEmail = process.env.JIRA_EMAIL;
    const jiraToken = process.env.JIRA_API_TOKEN;
    const jiraDomain = process.env.JIRA_DOMAIN;

    if (!jiraEmail || !jiraToken || !jiraDomain) {
      const msg = 'Missing Jira credentials (JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN)';
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const match = ticket_url.match(/\/browse\/([A-Z0-9\-]+)/);
    if (!match) {
      const msg = `Invalid Jira ticket URL: ${ticket_url}`;
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const ticketKey = match[1];
    const apiUrl = `${jiraDomain}/rest/api/3/issue/${ticketKey}`;

    ctx.logger.info(`Fetching Jira issue ${ticketKey} from ${apiUrl}`);
    const data = await callJiraApiImpl(ctx, apiUrl, [jiraEmail, jiraToken]);
    const fields = (data['fields'] as Record<string, any>) ?? {};

    const descriptionText = parseAdf(fields['description'] as Record<string, any>).trim();

    const result = {
      key: data['key'] as string,
      summary: fields['summary'] as string,
      status: (fields['status'] as Record<string, any>)?.['name'] as string,
      assignee: fields['assignee']
        ? ((fields['assignee'] as Record<string, any>)?.['displayName'] as string)
        : null,
      priority: (fields['priority'] as Record<string, any>)?.['name'] as string,
      project: (fields['project'] as Record<string, any>)?.['name'] as string,
      description: descriptionText || null,
      url: ticket_url,
    };

    ctx.logger.info(`Jira issue ${ticketKey} fetched successfully.`);
    return result;
  },
);

// ── Tool: linear_ticket_fetcher ───────────────────────────────────────────────

export const linearTicketFetcher = tool(
  'linear_ticket_fetcher',
  {
    description: 'Fetch Linear issue details using GraphQL API.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        ticket_url: {
          type: 'string',
          description: 'Full Linear ticket URL (e.g., https://linear.app/team/issue/PROJ-123)',
        },
      },
      required: ['ticket_url'],
    },
  },
  async (ctx: Context, args: { ticket_url: string }) => {
    const { ticket_url } = args;
    const linearToken = process.env.LINEAR_API_TOKEN;

    if (!linearToken) {
      const msg = 'Missing LINEAR_API_TOKEN in environment variables.';
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const match = ticket_url.match(/\/issue\/([A-Z0-9\-]+)/);
    if (!match) {
      const msg = `Invalid Linear ticket URL: ${ticket_url}`;
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const ticketKey = match[1];
    ctx.logger.info(`Fetching Linear issue ${ticketKey}`);

    const data = await callLinearApiImpl(ctx, ticketKey, linearToken);
    const issue = (data['data'] as Record<string, any>)?.['issue'] as Record<string, any> | undefined;

    if (!issue) {
      const msg = `No issue found for Linear key: ${ticketKey}`;
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const result = {
      key: issue['identifier'] as string,
      summary: issue['title'] as string,
      status: (issue['state'] as Record<string, any>)?.['name'] as string,
      assignee: (issue['assignee'] as Record<string, any>)?.['name'] as string | undefined,
      priority: issue['priority'] != null ? String(issue['priority']) : null,
      project: (issue['team'] as Record<string, any>)?.['name'] as string,
      description: issue['description'] as string | undefined,
      url: issue['url'] as string,
    };

    ctx.logger.info(`Linear issue ${ticketKey} fetched successfully.`);
    return result;
  },
);

// ── Tool: pr_fetcher ──────────────────────────────────────────────────────────

export const prFetcher = tool(
  'pr_fetcher',
  {
    description: 'Fetch Pull Request metadata and ALL file diffs from GitHub REST API. Paginates through all changed files so no file is missed.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        pr_url: {
          type: 'string',
          description: 'Full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)',
        },
      },
      required: ['pr_url'],
    },
  },
  async (ctx: Context, args: { pr_url: string }) => {
    const { pr_url } = args;
    const token = process.env.GITHUB_TOKEN;

    if (!token) {
      const msg = 'Missing GITHUB_TOKEN in environment variables.';
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const match = pr_url.match(/^https:\/\/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
    if (!match) {
      const msg = `Invalid PR URL: ${pr_url}`;
      ctx.logger.error(msg);
      throw new Error(msg);
    }

    const [, owner, repo, prNumber] = match;
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/pulls/${prNumber}`;
    const reqHeaders = {
      Authorization: `token ${token}`,
      Accept: 'application/vnd.github.v3+json',
    };

    ctx.logger.info(`Fetching PR #${prNumber} from ${owner}/${repo}`);
    const prMeta = await callGithubApiImpl(ctx, apiUrl, reqHeaders);

    // Paginate through ALL changed files (GitHub returns 30/page by default)
    const files: Array<Record<string, any>> = [];
    const filesBaseUrl = `https://api.github.com/repos/${owner}/${repo}/pulls/${prNumber}/files`;
    let pageUrl: string | null = `${filesBaseUrl}?per_page=100&page=1`;
    while (pageUrl) {
      ctx.logger.info(`Fetching files page: ${pageUrl}`);
      const resp = await fetch(pageUrl, { headers: reqHeaders });
      if (!resp.ok) throw new Error(`GitHub files API error: ${resp.status} ${resp.statusText}`);
      const page = (await resp.json()) as Array<Record<string, any>>;
      files.push(...page);
      const linkHeader = resp.headers.get('Link') ?? '';
      pageUrl = null;
      for (const part of linkHeader.split(',')) {
        if (part.includes('rel="next"')) {
          const m = part.match(/<([^>]+)>/);
          if (m) pageUrl = m[1];
          break;
        }
      }
    }

    const result = {
      repo: `${owner}/${repo}`,
      pr_number: parseInt(prNumber, 10),
      title: prMeta['title'] as string,
      author: (prMeta['user'] as Record<string, any>)?.['login'] as string,
      state: prMeta['state'] as string,
      created_at: prMeta['created_at'] as string,
      merged_at: prMeta['merged_at'] as string | null,
      description: prMeta['body'] as string | null,
      changed_files: prMeta['changed_files'] as number,
      additions: prMeta['additions'] as number,
      deletions: prMeta['deletions'] as number,
      files: files.map((f: Record<string, any>) => ({
        filename: f['filename'] as string,
        status: f['status'] as string,
        additions: f['additions'] as number,
        deletions: f['deletions'] as number,
        changes: f['changes'] as number,
        patch: (f['patch'] as string) ?? '',
        has_patch: Boolean(f['patch']),
      })),
    };

    ctx.logger.info(
      `PR #${prNumber} fetched: ${files.length} files across all pages, +${prMeta['additions']} -${prMeta['deletions']}`,
    );
    return result;
  },
);

// ── Tool: detect_ticket_source ────────────────────────────────────────────────

export const detectTicketSource = tool(
  'detect_ticket_source',
  {
    description: 'Determine ticketing platform (Jira or Linear) based on URL pattern.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        ticket_url: {
          type: 'string',
          description: 'Ticket URL to analyze',
        },
      },
      required: ['ticket_url'],
    },
  },
  async (ctx: Context, args: { ticket_url: string }) => {
    const { ticket_url } = args;
    if (ticket_url.includes('atlassian.net')) {
      ctx.logger.info('Detected Jira ticket URL');
      return 'jira';
    } else if (ticket_url.includes('linear.app')) {
      ctx.logger.info('Detected Linear ticket URL');
      return 'linear';
    } else {
      const msg = `Unsupported ticketing platform URL: ${ticket_url}`;
      ctx.logger.error(msg);
      throw new Error(msg);
    }
  },
);
