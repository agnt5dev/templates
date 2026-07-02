/**
 * Deep Research Workflow with Human-in-the-Loop Approval
 *
 * A research pipeline using 3 specialized agents with HITL approval:
 *
 * Stage 1 — Plan:     Scoping Agent creates research plan with subtopics
 * Stage 2 — Approve:  HITL pause — user reviews, edits, or rejects the plan (durable)
 * Stage 3 — Research: Research Agent conducts systematic research across all subtopics
 * Stage 4 — Write:    Writing Agent synthesizes findings into a final report
 *
 * The HITL pause at Stage 2 is durable — it survives server restarts and can
 * wait indefinitely for user input.
 */

import { workflow, ContextImpl } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';
import { planResearch, conductResearch, writeReport } from './functions.js';

export const deepResearchWorkflow = workflow(
  'deep_research_workflow',
  async (ctx: Context, input: { message: string }) => {
    const { message } = input;
    const topic = message;
    const wfCtx = ctx as ContextImpl;

    ctx.logger.info(`Deep research workflow started — topic: ${topic.slice(0, 100)}...`);

    // ── Stage 1: Planning ────────────────────────────────────────────────────
    ctx.logger.info('Stage 1: Creating research plan');
    const researchPlan = await ctx.step('plan', () =>
      planResearch(ctx, { topic }),
    );
    ctx.logger.info('Research plan created');

    // ── Stage 2: HITL — User approval of the research plan ──────────────────
    ctx.logger.info('Stage 2: Waiting for human approval of research plan...');

    const approvalQuestion = `Please review the research plan below:

---
${researchPlan}
---

Do you approve this research plan to proceed with research?`;

    const decision = await wfCtx.waitForUser(approvalQuestion, {
      inputType: 'select',
      options: [
        { id: 'approve', label: 'Approve Plan' },
        { id: 'edit', label: 'Edit Plan' },
        { id: 'reject', label: 'Reject' },
      ],
    });

    ctx.logger.info(`Decision received: ${decision}`);

    if (decision === 'reject') {
      ctx.logger.info('Research plan rejected by user');
      return {
        status: 'rejected',
        topic,
        research_plan: researchPlan,
        message: 'Research plan was rejected. Please start a new session with updated requirements.',
      };
    }

    let approvedPlan = researchPlan;

    if (decision === 'edit') {
      ctx.logger.info('User chose to edit the research plan');
      const edited = await wfCtx.waitForUser(
        `Please provide your edited research plan.

Here is the original plan for reference:
---
${researchPlan}
---

Paste your revised plan below:`,
        { inputType: 'text' },
      );
      approvedPlan = edited ?? researchPlan;
      ctx.logger.info('Received edited research plan from user');
    }

    ctx.logger.info('Research plan approved, proceeding to research phase');

    // ── Stage 3: Research ────────────────────────────────────────────────────
    ctx.logger.info('Stage 3: Conducting research');
    const researchFindings = await ctx.step('research', () =>
      conductResearch(ctx, { topic, research_plan: approvedPlan }),
    );
    ctx.logger.info('Research findings gathered');

    // ── Stage 4: Write report ────────────────────────────────────────────────
    ctx.logger.info('Stage 4: Writing final report');
    const finalReport = await ctx.step('write', () =>
      writeReport(ctx, { topic, research_plan: approvedPlan, research_findings: researchFindings }),
    );

    ctx.logger.info('Deep research workflow completed successfully');

    return {
      status: 'completed',
      topic,
      report: finalReport,
    };
  },
);
