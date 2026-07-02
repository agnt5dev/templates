import { fn, LM } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import type { FileReview, SecurityReview, TechStack } from './models.js';
import { FILE_REVIEW_SCHEMA, SECURITY_REVIEW_SCHEMA } from './models.js';
import { parseAdf } from './utils.js';
import {
  SYNTHESIZER_SYSTEM_PROMPT,
  SYNTHESIZER_USER_PROMPT,
  FILE_REVIEWER_SYSTEM_PROMPT,
  FILE_REVIEWER_USER_PROMPT,
  SECURITY_REVIEWER_SYSTEM_PROMPT,
  SECURITY_REVIEWER_USER_PROMPT,
  REPORT_SYNTHESIZER_SYSTEM_PROMPT,
  REPORT_SYNTHESIZER_USER_PROMPT,
} from './prompts/index.js';

const MODEL = 'openai/gpt-4.1-mini';

// ── Language / Framework detection maps ─────────────────────────────────────

const LANGUAGE_MAP: Record<string, string> = {
  '.py': 'Python',
  '.js': 'JavaScript',
  '.ts': 'TypeScript',
  '.jsx': 'JavaScript/JSX',
  '.tsx': 'TypeScript/TSX',
  '.java': 'Java',
  '.go': 'Go',
  '.rs': 'Rust',
  '.rb': 'Ruby',
  '.php': 'PHP',
  '.cs': 'C#',
  '.cpp': 'C++',
  '.c': 'C',
  '.swift': 'Swift',
  '.kt': 'Kotlin',
  '.scala': 'Scala',
  '.sh': 'Shell',
  '.html': 'HTML',
  '.css': 'CSS',
  '.sql': 'SQL',
  '.r': 'R',
};

const FRAMEWORK_INDICATORS: Record<string, string> = {
  django: 'Django',
  flask: 'Flask',
  fastapi: 'FastAPI',
  express: 'Express.js',
  react: 'React',
  vue: 'Vue.js',
  angular: 'Angular',
  spring: 'Spring Boot',
  rails: 'Ruby on Rails',
  laravel: 'Laravel',
  next: 'Next.js',
  nuxt: 'Nuxt.js',
  pytest: 'pytest',
  jest: 'Jest',
  sqlalchemy: 'SQLAlchemy',
  prisma: 'Prisma',
  mongoose: 'Mongoose',
  celery: 'Celery',
  graphql: 'GraphQL',
  grpc: 'gRPC',
};

// ── callJiraApi ──────────────────────────────────────────────────────────────

export const callJiraApi = fn('call_jira_api')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { url: string; auth: [string, string] }): Promise<Record<string, any>> => {
    const { url, auth } = input;
    const [email, token] = auth;
    ctx.logger.info(`Fetching Jira issue from ${url}`);
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
    ctx.logger.info(`Jira API response OK: ${response.status}`);
    return response.json() as Promise<Record<string, any>>;
  });

// ── callLinearApi ────────────────────────────────────────────────────────────

export const callLinearApi = fn('call_linear_api')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { ticket_id: string; linear_token: string }): Promise<Record<string, any>> => {
    const { ticket_id, linear_token } = input;
    ctx.logger.info(`Fetching Linear issue ${ticket_id}`);
    const url = 'https://api.linear.app/graphql';
    const query = {
      query: `
      {
          issue(id: "${ticket_id}") {
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
        Authorization: linear_token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(query),
    });
    if (!response.ok) {
      throw new Error(`Linear API error: ${response.status} ${response.statusText}`);
    }
    ctx.logger.info(`Linear API response OK: ${response.status}`);
    const data = await response.json() as Record<string, any>;
    ctx.logger.info(`Linear API response data: ${JSON.stringify(data)}`);
    return data;
  });

// ── callGithubApi ────────────────────────────────────────────────────────────

export const callGithubApi = fn('call_github_api')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { url: string; headers: Record<string, string> }): Promise<Record<string, any>> => {
    const { url, headers } = input;
    ctx.logger.info(`Fetching GitHub data from ${url}`);
    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status} ${response.statusText}`);
    }
    const data = (await response.json()) as Record<string, any>;
    ctx.logger.info(`GitHub API response OK: ${response.status}`);
    return data;
  });

// ── synthesizeReviewReport ───────────────────────────────────────────────────

export const synthesizeReviewReport = fn('synthesize_review_report')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { code_review: string }): Promise<string> => {
    const { code_review } = input;
    ctx.logger.info('Synthesizing code review report');

    const lm = LM.openai();
    const resp = await lm.generate({
      model: MODEL,
      messages: [
        { role: 'system', content: SYNTHESIZER_SYSTEM_PROMPT },
        {
          role: 'user',
          content: SYNTHESIZER_USER_PROMPT.replace('{code_review}', code_review),
        },
      ],
      config: { temperature: 0 },
    });

    ctx.logger.info('Synthesis complete');
    return resp.text;
  });

// ── detectTechStackNode ──────────────────────────────────────────────────────

export const detectTechStackNode = fn('detect_tech_stack_node')
  .retry({ maxAttempts: 2, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { files: Array<Record<string, any>> }): Promise<TechStack> => {
    const { files } = input;
    const languages = new Set<string>();
    const frameworks = new Set<string>();
    const configFiles: string[] = [];
    let hasTests = false;

    for (const f of files) {
      const filename: string = (f['filename'] as string) ?? '';
      const patch: string = (f['patch'] as string) ?? '';

      const dotIdx = filename.lastIndexOf('.');
      const ext = dotIdx >= 0 ? filename.slice(dotIdx).toLowerCase() : '';
      if (ext && LANGUAGE_MAP[ext]) {
        languages.add(LANGUAGE_MAP[ext]);
      }

      const nameLower = filename.toLowerCase();
      if (['test', 'spec', '_test.', '.test.'].some((x) => nameLower.includes(x))) {
        hasTests = true;
      }

      const configSuffixes = [
        'requirements.txt',
        'package.json',
        'go.mod',
        'cargo.toml',
        'gemfile',
        'composer.json',
        'pom.xml',
        'build.gradle',
        '.env.example',
        'dockerfile',
        'docker-compose.yml',
      ];
      if (configSuffixes.some((c) => nameLower.endsWith(c))) {
        configFiles.push(filename);
      }

      const content = (filename + ' ' + patch).toLowerCase();
      for (const [indicator, framework] of Object.entries(FRAMEWORK_INDICATORS)) {
        if (content.includes(indicator)) {
          frameworks.add(framework);
        }
      }
    }

    const notes: string[] = [];
    if (!hasTests) notes.push('No test files detected in this PR');
    if (files.length > 20) notes.push(`Large PR: ${files.length} files changed`);

    const stack: TechStack = {
      languages: [...languages].sort(),
      frameworks: [...frameworks].sort(),
      test_files_present: hasTests,
      config_files: configFiles,
      notes: notes.length > 0 ? notes.join('; ') : 'Standard PR size',
    };

    ctx.logger.info(`Tech stack: ${stack.languages} | Frameworks: ${stack.frameworks}`);
    return stack;
  });

// ── fetchPrNode ──────────────────────────────────────────────────────────────

export const fetchPrNode = fn('fetch_pr_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { pr_url: string }): Promise<Record<string, any>> => {
    const { pr_url } = input;
    const token = process.env.GITHUB_TOKEN;
    if (!token) throw new Error('Missing GITHUB_TOKEN in environment variables.');

    const match = pr_url.match(/^https:\/\/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
    if (!match) throw new Error(`Invalid PR URL: ${pr_url}`);

    const [, owner, repo, prNumber] = match;
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/pulls/${prNumber}`;
    const reqHeaders = {
      Authorization: `token ${token}`,
      Accept: 'application/vnd.github.v3+json',
    };

    ctx.logger.info(`Fetching PR #${prNumber} from ${owner}/${repo}`);
    const data = await callGithubApi(ctx, { url: apiUrl, headers: reqHeaders });

    // Paginate through ALL changed files (GitHub caps at 30/page by default)
    const files: Array<Record<string, any>> = [];
    const filesBaseUrl = `https://api.github.com/repos/${owner}/${repo}/pulls/${prNumber}/files`;
    let pageUrl: string | null = `${filesBaseUrl}?per_page=100&page=1`;
    while (pageUrl) {
      ctx.logger.info(`Fetching files page: ${pageUrl}`);
      const resp = await fetch(pageUrl, { headers: reqHeaders });
      if (!resp.ok) throw new Error(`GitHub files API error: ${resp.status} ${resp.statusText}`);
      const page = (await resp.json()) as Array<Record<string, any>>;
      files.push(...page);
      // Follow Link header for next page
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

    ctx.logger.info(`Fetched ${files.length} files across all pages`);

    const result = {
      repo: `${owner}/${repo}`,
      pr_number: parseInt(prNumber, 10),
      title: (data['title'] as string) ?? '',
      author: ((data['user'] as Record<string, any>)?.['login'] as string) ?? '',
      state: (data['state'] as string) ?? '',
      description: (data['body'] as string) ?? '',
      changed_files: (data['changed_files'] as number) ?? 0,
      additions: (data['additions'] as number) ?? 0,
      deletions: (data['deletions'] as number) ?? 0,
      files: files.map((f: Record<string, any>) => ({
        filename: (f['filename'] as string) ?? '',
        status: (f['status'] as string) ?? '',
        additions: (f['additions'] as number) ?? 0,
        deletions: (f['deletions'] as number) ?? 0,
        patch: (f['patch'] as string) ?? '',
        has_patch: Boolean(f['patch']),
      })),
    };

    ctx.logger.info(
      `PR #${prNumber} fetched: ${files.length} files, +${result.additions} -${result.deletions}`,
    );
    return result;
  });

// ── fetchTicketNode ──────────────────────────────────────────────────────────

export const fetchTicketNode = fn('fetch_ticket_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { ticket_url: string }): Promise<Record<string, any>> => {
    const { ticket_url } = input;

    if (!ticket_url || !ticket_url.trim()) {
      ctx.logger.info('No ticket URL provided, skipping ticket fetch');
      return { available: false, reason: 'No ticket URL provided' };
    }

    if (ticket_url.includes('atlassian.net')) {
      const jiraEmail = process.env.JIRA_EMAIL;
      const jiraToken = process.env.JIRA_API_TOKEN;
      const jiraDomain = process.env.JIRA_DOMAIN;

      if (!jiraEmail || !jiraToken || !jiraDomain) {
        ctx.logger.warn('Missing Jira credentials');
        return { available: false, reason: 'Missing Jira credentials' };
      }

      const match = ticket_url.match(/\/browse\/([A-Z0-9\-]+)/);
      if (!match) return { available: false, reason: `Invalid Jira URL: ${ticket_url}` };

      const ticketKey = match[1];
      const apiUrl = `${jiraDomain}/rest/api/3/issue/${ticketKey}`;
      const data = await callJiraApi(ctx, { url: apiUrl, auth: [jiraEmail, jiraToken] });
      const fields = (data['fields'] as Record<string, any>) ?? {};

      const description = parseAdf(fields['description'] as Record<string, any>).trim();

      ctx.logger.info(`Jira ticket ${ticketKey} fetched`);
      return {
        available: true,
        source: 'jira',
        key: data['key'] as string,
        summary: (fields['summary'] as string) ?? '',
        status: ((fields['status'] as Record<string, any>)?.['name'] as string) ?? '',
        priority: ((fields['priority'] as Record<string, any>)?.['name'] as string) ?? '',
        description: description || 'No description',
        url: ticket_url,
      };
    } else if (ticket_url.includes('linear.app')) {
      const linearToken = process.env.LINEAR_API_TOKEN;
      if (!linearToken) {
        ctx.logger.warn('Missing LINEAR_API_TOKEN');
        return { available: false, reason: 'Missing LINEAR_API_TOKEN' };
      }

      const match = ticket_url.match(/\/issue\/([A-Z0-9\-]+)/);
      if (!match) return { available: false, reason: `Invalid Linear URL: ${ticket_url}` };

      const ticketKey = match[1];
      const data = await callLinearApi(ctx, { ticket_id: ticketKey, linear_token: linearToken });
      const issue = (data['data'] as Record<string, any>)?.['issue'] as Record<string, any> | undefined;

      if (!issue) return { available: false, reason: `Linear issue ${ticketKey} not found` };

      ctx.logger.info(`Linear ticket ${ticketKey} fetched`);
      return {
        available: true,
        source: 'linear',
        key: issue['identifier'] as string,
        summary: issue['title'] as string,
        status: ((issue['state'] as Record<string, any>)?.['name'] as string) ?? '',
        priority: issue['priority'] != null ? String(issue['priority']) : 'Not set',
        description: (issue['description'] as string) || 'No description',
        url: issue['url'] as string,
      };
    } else {
      return { available: false, reason: `Unrecognized ticket platform: ${ticket_url}` };
    }
  });

// ── reviewFileNode ───────────────────────────────────────────────────────────

export const reviewFileNode = fn('review_file_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: {
        file_data: Record<string, any>;
        pr_context: Record<string, any>;
        tech_stack: Record<string, any>;
        ticket_context: Record<string, any>;
      },
    ): Promise<Record<string, any>> => {
      const { file_data, pr_context, tech_stack, ticket_context } = input;
      const filename = (file_data['filename'] as string) ?? 'unknown';
      const patch = (file_data['patch'] as string) ?? '';

      if (!patch) {
        ctx.logger.info(`Skipping ${filename} — no diff available`);
        const emptyReview: FileReview = {
          filename,
          language: 'unknown',
          findings: [],
          summary: 'No diff available for this file — binary or renamed file.',
        };
        return emptyReview;
      }

      ctx.logger.info(`Reviewing ${filename}`);

      let ticketSummary = 'No ticket provided';
      if (ticket_context['available']) {
        const desc = ((ticket_context['description'] as string) ?? '').slice(0, 300);
        ticketSummary = `${ticket_context['key'] ?? ''}: ${ticket_context['summary'] ?? ''} — ${desc}`;
      }

      const techStr = `Languages: ${((tech_stack['languages'] as string[]) ?? []).join(', ')} | Frameworks: ${((tech_stack['frameworks'] as string[]) ?? []).join(', ')}`;

      const userContent = FILE_REVIEWER_USER_PROMPT
        .replace('{pr_title}', (pr_context['title'] as string) ?? '')
        .replace('{pr_description}', ((pr_context['description'] as string) ?? '').slice(0, 500))
        .replace('{tech_stack}', techStr)
        .replace('{ticket_context}', ticketSummary)
        .replace('{filename}', filename)
        .replace('{status}', (file_data['status'] as string) ?? 'modified')
        .replace('{additions}', String((file_data['additions'] as number) ?? 0))
        .replace('{deletions}', String((file_data['deletions'] as number) ?? 0))
        .replace('{patch}', patch);

      const lm = LM.openai();
      const resp = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: FILE_REVIEWER_SYSTEM_PROMPT },
          { role: 'user', content: userContent },
        ],
        config: {
          temperature: 0,
          responseFormat: {
            formatType: 'json_schema',
            schemaName: 'FileReview',
            schema: JSON.stringify(FILE_REVIEW_SCHEMA),
            strict: true,
          },
        },
      });

      let result: FileReview | null = null;
      try {
        result = JSON.parse(resp.text) as FileReview;
      } catch {
        // ignore
      }

      if (result === null) {
        ctx.logger.warn(`No structured output for ${filename}, using empty review`);
        const fallback: FileReview = {
          filename,
          language: 'unknown',
          findings: [],
          summary: 'Structured output unavailable for this file.',
        };
        return fallback;
      }

      ctx.logger.info(`${filename}: ${result.findings.length} findings`);
      return result;
    },
  );

// ── securityReviewNode ───────────────────────────────────────────────────────

export const securityReviewNode = fn('security_review_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: {
        files: Array<Record<string, any>>;
        pr_context: Record<string, any>;
        tech_stack: Record<string, any>;
        ticket_context: Record<string, any>;
      },
    ): Promise<Record<string, any>> => {
      const { files, pr_context, tech_stack, ticket_context } = input;
      ctx.logger.info('Running security review pass');

      const reviewable = files.filter((f) => f['patch']);
      if (reviewable.length === 0) {
        ctx.logger.info('No diffs available for security review');
        const empty: SecurityReview = {
          findings: [],
          overall_risk: 'low',
          summary: 'No diffs available to review.',
        };
        return empty;
      }

      const allDiffs = reviewable
        .slice(0, 15)
        .map(
          (f) =>
            `### ${f['filename']} (+${f['additions'] ?? 0} -${f['deletions'] ?? 0})\n\`\`\`\n${f['patch']}\n\`\`\``,
        )
        .join('\n\n');

      const techStr = `Languages: ${((tech_stack['languages'] as string[]) ?? []).join(', ')} | Frameworks: ${((tech_stack['frameworks'] as string[]) ?? []).join(', ')}`;
      let ticketSummary = 'No ticket provided';
      if (ticket_context['available']) {
        ticketSummary = `${ticket_context['key'] ?? ''}: ${ticket_context['summary'] ?? ''}`;
      }

      const userContent = SECURITY_REVIEWER_USER_PROMPT
        .replace('{pr_title}', (pr_context['title'] as string) ?? '')
        .replace('{repo}', (pr_context['repo'] as string) ?? '')
        .replace('{tech_stack}', techStr)
        .replace('{all_diffs}', allDiffs)
        .replace('{ticket_context}', ticketSummary);

      const lm = LM.openai();
      const resp = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: SECURITY_REVIEWER_SYSTEM_PROMPT },
          { role: 'user', content: userContent },
        ],
        config: {
          temperature: 0,
          responseFormat: {
            formatType: 'json_schema',
            schemaName: 'SecurityReview',
            schema: JSON.stringify(SECURITY_REVIEW_SCHEMA),
            strict: true,
          },
        },
      });

      let result: SecurityReview | null = null;
      try {
        result = JSON.parse(resp.text) as SecurityReview;
      } catch {
        // ignore
      }

      if (result === null) {
        ctx.logger.warn('No structured output for security review, using empty result');
        const fallback: SecurityReview = {
          findings: [],
          overall_risk: 'low',
          summary: 'Structured output unavailable for security review.',
        };
        return fallback;
      }

      ctx.logger.info(`Security review done: ${result.findings.length} findings, risk=${result.overall_risk}`);
      return result;
    },
  );

// ── buildReportNode ──────────────────────────────────────────────────────────

export const buildReportNode = fn('build_report_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: {
        file_reviews: Array<Record<string, any>>;
        security_review: Record<string, any>;
        pr_data: Record<string, any>;
        ticket_data: Record<string, any>;
        tech_stack: Record<string, any>;
      },
    ): Promise<string> => {
      const { file_reviews, security_review, pr_data, ticket_data, tech_stack } = input;
      ctx.logger.info('Building final report');

      // Count severity across all findings
      const severityCounts: Record<string, number> = {
        critical: 0,
        major: 0,
        minor: 0,
        nitpick: 0,
      };
      for (const fr of file_reviews) {
        for (const finding of (fr['findings'] as any[]) ?? []) {
          const sev = (finding['severity'] as string) ?? 'minor';
          severityCounts[sev] = (severityCounts[sev] ?? 0) + 1;
        }
      }
      for (const finding of (security_review['findings'] as any[]) ?? []) {
        const sev = (finding['severity'] as string) ?? 'minor';
        severityCounts[sev] = (severityCounts[sev] ?? 0) + 1;
      }

      // Format file reviews for prompt
      let fileReviewsText = '';
      for (const fr of file_reviews) {
        const findings = (fr['findings'] as any[]) ?? [];
        fileReviewsText += `\n**${fr['filename']}** (${fr['language'] ?? 'unknown'}) — ${fr['summary'] ?? ''}\n`;
        for (const f of findings) {
          fileReviewsText += `  - [${String(f['severity']).toUpperCase()}] ${f['category']}: ${f['description']} → ${f['suggestion']}`;
          if (f['line_reference']) {
            fileReviewsText += ` (${f['line_reference']})`;
          }
          fileReviewsText += '\n';
        }
        if (findings.length === 0) {
          fileReviewsText += '  - No issues found\n';
        }
      }

      // Format security review
      const secFindings = (security_review['findings'] as any[]) ?? [];
      let securityText = `Overall Risk: ${String(security_review['overall_risk'] ?? 'unknown').toUpperCase()}\n${security_review['summary'] ?? ''}\n`;
      for (const f of secFindings) {
        securityText += `  - [${String(f['severity']).toUpperCase()}] ${f['description']} → ${f['suggestion']}\n`;
        if (f['line_reference']) {
          securityText += `    Location: ${f['line_reference']}\n`;
        }
      }

      const prMetadata =
        `Title: ${pr_data['title'] ?? ''}\n` +
        `Author: ${pr_data['author'] ?? ''}\n` +
        `Repo: ${pr_data['repo'] ?? ''}\n` +
        `PR #${pr_data['pr_number'] ?? ''}\n` +
        `Files: ${pr_data['changed_files'] ?? 0} changed (+${pr_data['additions'] ?? 0} -${pr_data['deletions'] ?? 0})\n` +
        `Description: ${((pr_data['description'] as string) ?? '').slice(0, 400)}\n` +
        `Severity counts: ${JSON.stringify(severityCounts)}`;

      let ticketText = 'No ticket provided';
      if (ticket_data['available']) {
        ticketText =
          `[${String(ticket_data['source'] ?? '').toUpperCase()}] ${ticket_data['key'] ?? ''}: ${ticket_data['summary'] ?? ''}\n` +
          `Status: ${ticket_data['status'] ?? ''} | Priority: ${ticket_data['priority'] ?? ''}\n` +
          `Description: ${((ticket_data['description'] as string) ?? '').slice(0, 500)}`;
      }

      const techText =
        `Languages: ${((tech_stack['languages'] as string[]) ?? ['unknown']).join(', ')}\n` +
        `Frameworks: ${((tech_stack['frameworks'] as string[]) ?? ['none detected']).join(', ')}\n` +
        `Tests in PR: ${tech_stack['test_files_present'] ? 'Yes' : 'No'}\n` +
        `Notes: ${tech_stack['notes'] ?? ''}`;

      const userContent = REPORT_SYNTHESIZER_USER_PROMPT
        .replace('{pr_metadata}', prMetadata)
        .replace('{ticket_context}', ticketText)
        .replace('{tech_stack}', techText)
        .replace('{file_reviews}', fileReviewsText)
        .replace('{security_review}', securityText);

      const lm = LM.openai();
      const resp = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: REPORT_SYNTHESIZER_SYSTEM_PROMPT },
          { role: 'user', content: userContent },
        ],
        config: { temperature: 0 },
      });

      ctx.logger.info('Final report built');
      return resp.text;
    },
  );
