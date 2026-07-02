/**
 * Coding agent workflow.
 *
 * Orchestrates the full test-driven development loop:
 *   1. Plan — generate dev_plan + test_plan
 *   2. Iterate (up to max_retries times):
 *      a. Iteration 0: generate tests first, then code (tests-visible codegen)
 *      b. Iteration N>0: analyze errors, then fix code
 *      c. Sync code + tests to E2B sandbox
 *      d. Install third-party dependencies
 *      e. Run pytest
 *      f. Decision: success → docs → return | failure → next iteration
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import type { WorkflowResult, ErrorAnalysis } from './models.js';
import {
  plannerNode,
  codeGeneratorNode,
  testGeneratorNode,
  codeSyncNode,
  installDepsNode,
  codeExecutorNode,
  errorAnalyzerNode,
  finalResponseNode,
} from './functions.js';

export const codingAgentWorkflow = workflow(
  'coding_agent_workflow',
  async (
    ctx: Context,
    input: { task_description: string; max_retries?: number },
  ): Promise<WorkflowResult> => {
    const { task_description, max_retries = 15 } = input;

    ctx.logger.info('='.repeat(60));
    ctx.logger.info('INITIATING CODING AGENT WORKFLOW');
    ctx.logger.info('='.repeat(60));

    await ctx.set('task_description', task_description);
    await ctx.set('retries', 0);
    await ctx.set('execution_status', 'initial');

    ctx.logger.info(`Task: ${task_description.slice(0, 100)}...`);
    ctx.logger.info(`Max retries: ${max_retries}`);

    // ── STEP 1: PLANNING ──────────────────────────────────────────────────────
    ctx.logger.info('\n' + '='.repeat(60));
    ctx.logger.info('STEP 1: PLANNING');
    ctx.logger.info('='.repeat(60));

    let plan: { dev_plan: string; test_plan: string };
    try {
      plan = await ctx.step('planning', () =>
        plannerNode(ctx, { task_description }),
      );
    } catch (err) {
      const msg = (err as Error).message;
      ctx.logger.error(`Planning failed: ${msg}`);
      return {
        success: false,
        task: task_description,
        iterations: 0,
        error: `Planning failed: ${msg}`,
      };
    }

    await ctx.set('dev_plan', plan.dev_plan);
    await ctx.set('test_plan', plan.test_plan);
    ctx.logger.info('Planning complete');

    // ── ITERATION LOOP ────────────────────────────────────────────────────────
    for (let iteration = 0; iteration < max_retries; iteration++) {
      ctx.logger.info('\n' + '='.repeat(60));
      ctx.logger.info(`ITERATION ${iteration + 1}/${max_retries}`);
      ctx.logger.info('='.repeat(60));

      const executionStatus =
        (await ctx.get<string>('execution_status')) ?? 'initial';
      const devPlan = (await ctx.get<string>('dev_plan')) ?? '';
      const testPlan = (await ctx.get<string>('test_plan')) ?? '';

      ctx.logger.info('\nSTEP 2: CODE GENERATION');

      let generatedCode: string;
      let generatedTests: string;

      if (iteration === 0) {
        // First iteration: generate tests then code (code sees the tests)
        ctx.logger.info('Generating test suite first');
        const testResult = await ctx.step(
          `test_gen_iter_${iteration}`,
          () =>
            testGeneratorNode(ctx, {
              task_description,
              test_plan: testPlan,
            }),
        );
        generatedTests = testResult.code;

        ctx.logger.info('Generating implementation (guided by tests)');
        const codeResult = await ctx.step(
          `code_gen_iter_${iteration}`,
          () =>
            codeGeneratorNode(ctx, {
              task_description,
              dev_plan: devPlan,
              execution_status: 'initial',
              generated_tests: generatedTests,
            }),
        );
        generatedCode = codeResult.code;
      } else {
        // Subsequent iterations: analyze errors, then fix code
        ctx.logger.info('Fixing code based on test failures');
        ctx.logger.info('\nAnalyzing errors...');

        const prevCode = (await ctx.get<string>('generated_code')) ?? '';
        const prevTests = (await ctx.get<string>('generated_tests')) ?? '';
        const errorLogs = (await ctx.get<string>('error_logs')) ?? '';

        const errorAnalysis = await ctx.step(
          `error_analysis_iter_${iteration}`,
          () =>
            errorAnalyzerNode(ctx, {
              task_description,
              dev_plan: devPlan,
              generated_code: prevCode,
              generated_tests: prevTests,
              error_logs: errorLogs,
            }),
        );

        await ctx.set('error_analysis', errorAnalysis);
        ctx.logger.info(
          `Analysis complete: ${errorAnalysis.analysis_summary.slice(0, 100)}...`,
        );

        const codeResult = await ctx.step(
          `code_fix_iter_${iteration}`,
          () =>
            codeGeneratorNode(ctx, {
              task_description,
              dev_plan: devPlan,
              execution_status: executionStatus,
              generated_code: prevCode,
              generated_tests: prevTests,
              error_logs: errorLogs,
              error_analysis: errorAnalysis,
            }),
        );

        generatedCode = codeResult.code;
        generatedTests = prevTests;
      }

      await ctx.set('generated_code', generatedCode);
      await ctx.set('generated_tests', generatedTests);

      // ── STEP 3: CODE SYNC ──────────────────────────────────────────────────
      ctx.logger.info('\nSTEP 3: CODE SYNC');

      const existingSandboxId = await ctx.get<string>('sandbox_id');
      const syncResult = await ctx.step(
        `code_sync_iter_${iteration}`,
        () =>
          codeSyncNode(ctx, {
            main_code: generatedCode,
            test_code: generatedTests,
            sandbox_id: existingSandboxId,
          }),
      );

      let nextAction: string;
      let status: string;
      let errorLogs: string;
      let sandboxId = existingSandboxId ?? '';

      if (!syncResult.success) {
        ctx.logger.error(`Code sync failed: ${syncResult.message}`);
        await ctx.set('execution_status', 'tests_failed');
        const syncError = syncResult.message ?? 'Code sync failed';
        await ctx.set('error_logs', syncError);
        errorLogs = syncError;
        nextAction = 'retry_code';
        status = 'tests_failed';
      } else {
        sandboxId = syncResult.sandbox_id ?? '';
        await ctx.set('sandbox_id', sandboxId);
        ctx.logger.info(`Synced to sandbox: ${sandboxId}`);

        // ── STEP 4: DEPENDENCY INSTALLATION ───────────────────────────────────
        ctx.logger.info('\nSTEP 4: DEPENDENCY INSTALLATION');
        await ctx.step(
          `install_deps_iter_${iteration}`,
          () =>
            installDepsNode(ctx, {
              main_code: generatedCode,
              sandbox_id: sandboxId,
            }),
        );

        // ── STEP 5: TEST EXECUTION ─────────────────────────────────────────────
        ctx.logger.info('\nSTEP 5: TEST EXECUTION');
        const execResult = await ctx.step(
          `code_exec_iter_${iteration}`,
          () => codeExecutorNode(ctx, { sandbox_id: sandboxId }),
        );

        nextAction = execResult.next_action;
        status = execResult.status;
        errorLogs = execResult.error_logs ?? '';

        await ctx.set('execution_status', status);
        await ctx.set('error_logs', errorLogs);
      }

      // ── STEP 6: DECISION ───────────────────────────────────────────────────
      ctx.logger.info('\nSTEP 6: DECISION');

      if (nextAction === 'success') {
        ctx.logger.info('SUCCESS! All tests passed');
        ctx.logger.info('\nSTEP 7: DOCUMENTATION');

        const finalResult = await ctx.step(
          'final_response',
          () =>
            finalResponseNode(ctx, {
              task_description,
              generated_code: generatedCode,
            }),
        );

        ctx.logger.info('='.repeat(60));
        ctx.logger.info('WORKFLOW COMPLETE - SUCCESS');
        ctx.logger.info('='.repeat(60));

        return {
          success: true,
          task: task_description,
          iterations: iteration + 1,
          code: generatedCode,
          tests: generatedTests,
          sandbox_id: sandboxId,
          documentation: finalResult.markdown_content,
        };
      } else {
        // All non-success outcomes → retry
        const retries = ((await ctx.get<number>('retries')) ?? 0) + 1;
        await ctx.set('retries', retries);

        if (retries >= max_retries) {
          ctx.logger.warn(`Maximum retries (${max_retries}) reached`);
          ctx.logger.info('='.repeat(60));
          ctx.logger.info('WORKFLOW COMPLETE - MAX RETRIES');
          ctx.logger.info('='.repeat(60));
          return {
            success: false,
            task: task_description,
            iterations: iteration + 1,
            error: `Maximum retries (${max_retries}) exhausted`,
            error_logs: errorLogs,
            code: generatedCode,
            tests: generatedTests,
            sandbox_id: sandboxId,
          };
        }

        ctx.logger.warn(`Retrying (${retries}/${max_retries}) — ${status}`);
        // continue to next iteration
      }
    }

    // Should never be reached unless max_retries is 0
    ctx.logger.error('Unexpected workflow termination');
    const finalCode = (await ctx.get<string>('generated_code')) ?? undefined;
    const finalTests = (await ctx.get<string>('generated_tests')) ?? undefined;
    const finalSandboxId = (await ctx.get<string>('sandbox_id')) ?? undefined;

    return {
      success: false,
      task: task_description,
      iterations: max_retries,
      error: 'Workflow terminated unexpectedly',
      code: finalCode,
      tests: finalTests,
      sandbox_id: finalSandboxId,
    };
  },
);
