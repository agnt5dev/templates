import fs from 'node:fs';
import path from 'node:path';

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { contextBuilderAgent, reviewerAgent } from './agents.js';
import {
  fetchPrNode,
  detectTechStackNode,
  reviewFileNode,
  securityReviewNode,
} from './functions.js';
import { CONTEXT_BUILDER_USER_PROMPT } from './prompts/index.js';

const PR_SIZE_WARNING_THRESHOLD = 30;

export const codeReviewerWorkflow = workflow(
  'code_reviewer_workflow',
  async (
    ctx: Context,
    input: { pr_url: string; ticket_url?: string },
  ): Promise<Record<string, any>> => {
    const { pr_url, ticket_url = '' } = input;

    ctx.logger.info('Starting code review workflow');

    await ctx.set('pr_url', pr_url);
    await ctx.set('ticket_url', ticket_url);
    await ctx.set('status', 'in_progress');

    // ── STEP 1: context_builder agent + fetch_pr_node in parallel ─────────────
    // context_builder_agent autonomously calls its tools (pr_fetcher,
    // detect_ticket_source, jira/linear_ticket_fetcher) to build a rich
    // context summary of the PR and ticket requirements.
    // fetchPrNode runs in parallel to get structured file data needed
    // to split work into per-file parallel review steps.
    ctx.logger.info('Step 1/4: Context Builder Agent + structured PR fetch (parallel)');

    const [contextResult, prData] = await Promise.all([
      contextBuilderAgent.run(
        CONTEXT_BUILDER_USER_PROMPT
          .replace('{pr_url}', pr_url)
          .replace('{ticket_url}', ticket_url || 'No ticket URL provided'),
        ctx,
      ),
      ctx.step('fetch_pr', () => fetchPrNode(ctx, { pr_url })),
    ]);

    const contextSummary: string = contextResult.output;
    await ctx.set('context_summary', contextSummary);
    await ctx.set('pr_data', prData);

    const fileCount = (prData['changed_files'] as number) ?? 0;
    ctx.logger.info(`Context built — PR #${prData['pr_number']} · ${fileCount} files`);

    console.log('\n' + '='.repeat(60));
    console.log('🤖 CONTEXT BUILDER AGENT OUTPUT');
    console.log('='.repeat(60));
    console.log(contextSummary);
    console.log('='.repeat(60) + '\n');

    if (fileCount > PR_SIZE_WARNING_THRESHOLD) {
      ctx.logger.warn(
        `Large PR: ${fileCount} files. Per-file parallel reviews will cover all of them.`,
      );
    }

    // ── STEP 2: Tech stack detection ──────────────────────────────────────────
    ctx.logger.info('Step 2/4: Detecting tech stack');

    const techStack = await ctx.step('detect_tech_stack', () =>
      detectTechStackNode(ctx, { files: (prData['files'] as Array<Record<string, any>>) ?? [] }),
    );
    await ctx.set('tech_stack', techStack);
    ctx.logger.info(
      `Tech stack: ${techStack['languages']} | Frameworks: ${techStack['frameworks']}`,
    );

    // ── STEP 3: Per-file reviews + security review — all in parallel ──────────
    // Each file review sees exactly one file's diff → no hallucination possible.
    // Security review sees all diffs together for cross-file vulnerability detection.
    const reviewableFiles = ((prData['files'] as Array<Record<string, any>>) ?? []).filter(
      (f) => f['has_patch'],
    );
    ctx.logger.info(
      `Step 3/4: Reviewing ${reviewableFiles.length}/${fileCount} files in parallel + security review`,
    );

    const prContext = {
      title: prData['title'] as string,
      description: prData['description'] as string,
      repo: prData['repo'] as string,
    };
    // Minimal ticket context for per-file prompts (full context goes to reviewer_agent)
    const ticketContext: Record<string, any> = { available: false };

    const fileReviewPromises = reviewableFiles.map((f, i) =>
      ctx.step(`review_file_${i}`, () =>
        reviewFileNode(ctx, {
          file_data: f,
          pr_context: prContext,
          tech_stack: techStack,
          ticket_context: ticketContext,
        }),
      ),
    );

    const securityPromise = ctx.step('security_review', () =>
      securityReviewNode(ctx, {
        files: reviewableFiles,
        pr_context: prContext,
        tech_stack: techStack,
        ticket_context: ticketContext,
      }),
    );

    let fileReviews: Array<Record<string, any>>;
    let securityReview: Record<string, any>;

    if (fileReviewPromises.length > 0) {
      const allResults = await Promise.all([...fileReviewPromises, securityPromise]);
      fileReviews = allResults.slice(0, -1) as Array<Record<string, any>>;
      securityReview = allResults[allResults.length - 1] as Record<string, any>;
    } else {
      securityReview = await securityPromise;
      fileReviews = [];
    }

    await ctx.set('file_reviews', fileReviews);
    await ctx.set('security_review', securityReview);

    const totalFindings = fileReviews.reduce(
      (acc, fr) => acc + ((fr['findings'] as any[]) ?? []).length,
      0,
    );
    ctx.logger.info(
      `Reviews complete: ${totalFindings} findings across ${fileReviews.length} files · security risk=${securityReview['overall_risk']}`,
    );

    console.log('\n' + '='.repeat(60));
    console.log('📋 PER-FILE REVIEW RESULTS');
    console.log('='.repeat(60));
    for (const fr of fileReviews) {
      const findings = (fr['findings'] as any[]) ?? [];
      console.log(`  ${fr['filename']} — ${findings.length} finding(s): ${fr['summary'] ?? ''}`);
    }
    console.log(`\n🔒 Security Risk: ${String(securityReview['overall_risk'] ?? 'unknown').toUpperCase()}`);
    console.log(`   ${securityReview['summary'] ?? ''}`);
    console.log(`\nTotal findings: ${totalFindings}`);
    console.log('='.repeat(60) + '\n');

    // ── STEP 4: reviewer_agent synthesizes everything into the final report ────
    // The agent gets the full context summary (ticket requirements, PR overview)
    // plus all structured per-file findings and security findings.
    ctx.logger.info('Step 4/4: Reviewer Agent synthesizing final report');

    const severityCounts: Record<string, number> = {
      critical: 0,
      major: 0,
      minor: 0,
      nitpick: 0,
    };
    for (const fr of fileReviews) {
      for (const finding of (fr['findings'] as any[]) ?? []) {
        const sev = (finding['severity'] as string) ?? 'minor';
        severityCounts[sev] = (severityCounts[sev] ?? 0) + 1;
      }
    }
    for (const finding of (securityReview['findings'] as any[]) ?? []) {
      const sev = (finding['severity'] as string) ?? 'minor';
      severityCounts[sev] = (severityCounts[sev] ?? 0) + 1;
    }

    let fileReviewsText = '';
    for (const fr of fileReviews) {
      const findings = (fr['findings'] as any[]) ?? [];
      fileReviewsText += `\n**${fr['filename']}** (${fr['language'] ?? 'unknown'}) — ${fr['summary'] ?? ''}\n`;
      for (const f of findings) {
        const loc = f['line_reference'] ? ` (${f['line_reference']})` : '';
        fileReviewsText += `  - [${String(f['severity']).toUpperCase()}] ${f['category']}: ${f['description']} → ${f['suggestion']}${loc}\n`;
      }
      if (findings.length === 0) {
        fileReviewsText += '  - No issues found\n';
      }
    }

    const secFindings = (securityReview['findings'] as any[]) ?? [];
    let secText =
      `Overall Risk: ${String(securityReview['overall_risk'] ?? 'unknown').toUpperCase()}\n` +
      `${securityReview['summary'] ?? ''}\n`;
    for (const f of secFindings) {
      const loc = f['line_reference'] ? ` (${f['line_reference']})` : '';
      secText += `  - [${String(f['severity']).toUpperCase()}] ${f['description']} → ${f['suggestion']}${loc}\n`;
    }

    const techText =
      `Languages: ${((techStack['languages'] as string[]) ?? ['unknown']).join(', ')}\n` +
      `Frameworks: ${((techStack['frameworks'] as string[]) ?? ['none']).join(', ')}\n` +
      `Tests in PR: ${techStack['test_files_present'] ? 'Yes' : 'No'}\n` +
      `Notes: ${techStack['notes'] ?? ''}`;

    const prMetaText =
      `Title: ${prData['title'] ?? ''}\n` +
      `Author: ${prData['author'] ?? ''}\n` +
      `Repo: ${prData['repo'] ?? ''}\n` +
      `PR #: ${prData['pr_number'] ?? ''}\n` +
      `State: ${prData['state'] ?? ''}\n` +
      `Description: ${((prData['description'] as string) ?? '').slice(0, 500)}\n` +
      `Files changed: ${prData['changed_files'] ?? 0} (+${prData['additions'] ?? 0} / -${prData['deletions'] ?? 0})`;

    const synthesisMessage = `Synthesize the following code review findings into a final Markdown report.

## PR Metadata
${prMetaText}

## PR + Ticket Context (from Context Builder Agent)
${contextSummary}

## Tech Stack
${techText}

## Per-File Review Findings (${fileReviews.length} files reviewed)
Severity summary: ${JSON.stringify(severityCounts)}
${fileReviewsText}

## Security Review
${secText}

Write a complete, professional Markdown report with executive summary, findings grouped by severity, security section, and a clear merge recommendation (APPROVE / REQUEST CHANGES / BLOCK).`;

    const reportResult = await reviewerAgent.run(synthesisMessage, ctx);
    const report: string = reportResult.output;

    console.log('\n' + '='.repeat(60));
    console.log('🤖 REVIEWER AGENT OUTPUT');
    console.log('='.repeat(60));
    console.log(report);
    console.log('='.repeat(60) + '\n');

    // Save report
    let savedReportPath: string | null = null;
    try {
      const prMatch = pr_url.match(/^https:\/\/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
      if (prMatch) {
        const [, owner, repoName, prNum] = prMatch;
        const reportsDir = path.resolve('reports');
        fs.mkdirSync(reportsDir, { recursive: true });
        const reportPath = path.join(reportsDir, `${owner}_${repoName}_pr_${prNum}_review.md`);
        const header =
          `# Code Review Report\n\n` +
          `**PR**: ${pr_url}\n` +
          `**Ticket**: ${ticket_url || 'N/A'}\n` +
          `**Files reviewed**: ${fileReviews.length}/${fileCount}\n` +
          `**Security risk**: ${String(securityReview['overall_risk'] ?? 'unknown').toUpperCase()}\n` +
          `**Findings**: ${JSON.stringify(severityCounts)}\n\n` +
          `---\n\n`;
        fs.writeFileSync(reportPath, header + report, 'utf8');
        ctx.logger.info(`Report saved to: ${reportPath}`);
        savedReportPath = reportPath;
      }
    } catch (e) {
      ctx.logger.warn(`Failed to save report: ${e}`);
    }

    await ctx.set('status', 'completed');
    ctx.logger.info('Code review workflow complete');

    return {
      status: 'success',
      pr_url,
      ticket_url,
      pr_number: prData['pr_number'],
      repo: prData['repo'],
      files_reviewed: fileReviews.length,
      total_files: fileCount,
      security_risk: securityReview['overall_risk'] ?? 'unknown',
      severity_counts: severityCounts,
      tech_stack: techStack,
      context_summary: contextSummary,
      report,
      report_file: savedReportPath,
    };
  },
);
