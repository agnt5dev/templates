/**
 * Function nodes for the coding agent workflow.
 *
 * Each node is registered with the AGNT5 runtime via fn().run().
 * All LM calls use Groq with structured JSON output.
 */

import 'dotenv/config';

import { fn, LM } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import type {
  Plan,
  GeneratedCode,
  ErrorAnalysis,
  SyncResult,
  ExecutionResult,
  FinalResponse,
} from './models.js';
import {
  PLAN_SCHEMA,
  GENERATED_CODE_SCHEMA,
  ERROR_ANALYSIS_SCHEMA,
} from './models.js';
import {
  PLANNER_SYSTEM_PROMPT,
  PLANNER_USER_PROMPT,
  CODER_SYSTEM_PROMPT,
  CODER_USER_PROMPT,
  TEST_SYSTEM_PROMPT,
  TEST_USER_PROMPT,
  MARKDOWN_SYSTEM_PROMPT,
  MARKDOWN_USER_PROMPT,
  ERROR_ANALYZER_SYSTEM_PROMPT,
  ERROR_ANALYZER_USER_PROMPT,
  CODEFIXER_SYSTEM_PROMPT,
  CODEFIXER_USER_PROMPT,
} from './prompts/index.js';
import { createSandboxImpl as createSandbox, writeFileImpl as writeFile, runCommandImpl as runCommand } from './tools.js';

// ============================================================================
// Module-level LM instance
// ============================================================================

const lm = LM.groq({ apiKey: process.env.GROQ_API_KEY });
const MODEL = 'groq/meta-llama/llama-4-scout-17b-16e-instruct';

// ============================================================================
// Helpers
// ============================================================================

/**
 * Strip markdown code fences that the LLM sometimes wraps around the code
 * value, e.g. ```python ... ``` or ``` ... ```.
 */
export function _cleanCode(code: string): string {
  code = code.trim();

  // Remove ```python ... ``` or ``` ... ``` wrappers
  const fencedMatch = code.match(/^```(?:python)?\s*\n([\s\S]*?)\n```$/);
  if (fencedMatch) {
    return fencedMatch[1].trim();
  }

  // Fallback: strip leading/trailing fence lines individually
  const lines = code.split('\n');
  const first = lines[0]?.trim() ?? '';
  const last = lines[lines.length - 1]?.trim() ?? '';

  const result = [...lines];
  if (first.startsWith('```')) result.shift();
  if (last === '```') result.pop();

  return result.join('\n').trim();
}

/**
 * Basic pre-sandbox syntax sanity check for Python source.
 *
 * We cannot run ast.parse() in TypeScript, so we do a lightweight check:
 * - Reject empty/whitespace-only strings
 * - Reject code that still contains markdown fence markers (unfixed)
 *
 * Deep syntax validation happens inside the E2B sandbox via pytest/Python
 * itself (collection errors surface as exit_code 2).
 */
export function _validatePythonSyntax(code: string): { valid: boolean; error: string } {
  if (!code || code.trim().length === 0) {
    return { valid: false, error: 'Code is empty' };
  }
  if (code.trim().startsWith('```')) {
    return { valid: false, error: 'Code still contains markdown fence markers' };
  }
  return { valid: true, error: '' };
}

/**
 * Extract probable third-party package names from Python source using regex.
 *
 * Looks for `import X` and `from X import ...` lines, then filters out
 * known stdlib module names and testing helpers.
 */
export function _extractThirdPartyImports(code: string): string[] {
  const SKIP = new Set([
    // Very common stdlib top-level names (non-exhaustive but covers 99% of cases)
    '__future__', '_thread', 'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat',
    'asyncio', 'asyncore', 'atexit', 'audioop', 'base64', 'bdb', 'binascii',
    'binhex', 'bisect', 'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk',
    'cmath', 'cmd', 'code', 'codecs', 'codeop', 'collections', 'colorsys',
    'compileall', 'concurrent', 'configparser', 'contextlib', 'contextvars',
    'copy', 'copyreg', 'cProfile', 'csv', 'ctypes', 'curses', 'dataclasses',
    'datetime', 'dbm', 'decimal', 'difflib', 'dis', 'doctest', 'email', 'encodings',
    'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch',
    'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext',
    'glob', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http',
    'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect', 'io',
    'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
    'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math',
    'mimetypes', 'mmap', 'modulefinder', 'multiprocessing', 'netrc', 'nis',
    'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev',
    'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil',
    'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint', 'profile',
    'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri',
    'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy',
    'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
    'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver',
    'spwd', 'sqlite3', 'sre_compile', 'sre_constants', 'sre_parse', 'ssl',
    'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess',
    'sunau', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile',
    'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading',
    'time', 'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace',
    'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types',
    'typing', 'typing_extensions', 'unicodedata', 'unittest', 'urllib',
    'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser',
    'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport',
    'zlib', 'zoneinfo',
    // Testing helpers
    'pytest', 'mock', 'unittest',
  ]);

  const names = new Set<string>();

  // Match: import foo, import foo.bar, from foo import ..., from foo.bar import ...
  const importRe = /^(?:import|from)\s+([A-Za-z_][A-Za-z0-9_.]*)/gm;
  let match: RegExpExecArray | null;
  while ((match = importRe.exec(code)) !== null) {
    const topLevel = match[1].split('.')[0];
    if (topLevel && !topLevel.startsWith('_')) {
      names.add(topLevel);
    }
  }

  return Array.from(names)
    .filter((n) => !SKIP.has(n))
    .sort();
}

// ============================================================================
// Function nodes
// ============================================================================

/**
 * Planner node — generates synchronized dev_plan + test_plan from a task description.
 */
export const plannerNode = fn('planner_node')
  .retry({ maxAttempts: 5, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(async (ctx: Context, input: { task_description: string }): Promise<Plan> => {
    const { task_description } = input;
    ctx.logger.info('Planning process started');
    ctx.logger.debug(`Task description length: ${task_description.length} chars`);

    const userPrompt = PLANNER_USER_PROMPT.replace('{task_description}', task_description);

    const response = await lm.generate({
      model: MODEL,
      messages: [
        { role: 'system', content: PLANNER_SYSTEM_PROMPT },
        { role: 'user', content: userPrompt },
      ],
      config: {
        temperature: 0,
        responseFormat: {
          formatType: 'json_schema',
          schemaName: 'Plan',
          schema: JSON.stringify(PLAN_SCHEMA),
          strict: true,
        },
      },
    });

    const plan = JSON.parse(response.text) as Plan;
    ctx.logger.info('Plan generated successfully');
    ctx.logger.debug(`Dev plan length: ${plan.dev_plan.length} chars`);
    ctx.logger.debug(`Test plan length: ${plan.test_plan.length} chars`);
    return plan;
  });

/**
 * Code generator node — produces initial code or fixes failing code.
 *
 * When execution_status is "tests_failed", uses the CODEFIXER prompt chain
 * together with the error analysis. Otherwise uses the CODER prompt chain.
 */
export const codeGeneratorNode = fn('code_generator_node')
  .retry({ maxAttempts: 5, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: {
        task_description: string;
        dev_plan: string;
        execution_status?: string;
        generated_code?: string;
        generated_tests?: string;
        error_logs?: string;
        error_analysis?: ErrorAnalysis;
      },
    ): Promise<GeneratedCode> => {
      const {
        task_description,
        dev_plan,
        execution_status = 'initial',
        generated_code = '',
        generated_tests = '',
        error_logs = '',
        error_analysis,
      } = input;

      let systemPrompt: string;
      let userPrompt: string;

      if (execution_status !== 'tests_failed') {
        ctx.logger.info('Generating initial code from plan');

        userPrompt = CODER_USER_PROMPT
          .replace('{task_description}', task_description)
          .replace('{development_plan}', dev_plan)
          .replace(
            '{test_suite}',
            generated_tests || 'Tests will be validated after implementation.',
          );
        systemPrompt = CODER_SYSTEM_PROMPT;
      } else {
        ctx.logger.info('Fixing code based on test failures');
        ctx.logger.debug(`Error logs (first 200): ${error_logs.slice(0, 200)}...`);

        // Format error analysis section for the fixer prompt
        let analysisText = '';
        if (error_analysis) {
          const failedList = error_analysis.failed_tests
            .map((t) => `- ${t}`)
            .join('\n');
          const causeList = error_analysis.root_causes
            .map((c) => `- ${c}`)
            .join('\n');
          const fixList = error_analysis.suggested_fixes
            .map((f) => `- ${f}`)
            .join('\n');

          analysisText = `
### ERROR ANALYSIS

**Failed Tests:**
${failedList}

**Root Causes:**
${causeList}

**Suggested Fixes:**
${fixList}

**Analysis Summary:**
${error_analysis.analysis_summary}

---
`;
        }

        userPrompt = CODEFIXER_USER_PROMPT
          .replace('{task_description}', task_description)
          .replace('{development_plan}', dev_plan)
          .replace('{dev_code}', generated_code)
          .replace('{test_code}', generated_tests)
          .replace('{error_logs}', error_logs)
          .replace('{error_analysis}', analysisText);
        systemPrompt = CODEFIXER_SYSTEM_PROMPT;
      }

      const response = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        config: {
          temperature: 0,
          responseFormat: {
            formatType: 'json_schema',
            schemaName: 'GeneratedCode',
            schema: JSON.stringify(GENERATED_CODE_SCHEMA),
            strict: true,
          },
        },
      });

      const raw = JSON.parse(response.text) as GeneratedCode;
      const cleaned = _cleanCode(raw.code);
      ctx.logger.info(`Code processed: ${cleaned.length} chars`);
      return { code: cleaned };
    },
  );

/**
 * Test generator node — produces a pytest test suite from a test plan.
 */
export const testGeneratorNode = fn('test_generator_node')
  .retry({ maxAttempts: 5, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: { task_description: string; test_plan: string },
    ): Promise<GeneratedCode> => {
      const { task_description, test_plan } = input;
      ctx.logger.info('Generating test suite');

      const userPrompt = TEST_USER_PROMPT
        .replace('{task_description}', task_description)
        .replace('{test_plan}', test_plan);

      const response = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: TEST_SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        config: {
          temperature: 0,
          responseFormat: {
            formatType: 'json_schema',
            schemaName: 'GeneratedCode',
            schema: JSON.stringify(GENERATED_CODE_SCHEMA),
            strict: true,
          },
        },
      });

      const raw = JSON.parse(response.text) as GeneratedCode;
      const tests = _cleanCode(raw.code);
      ctx.logger.info(`Tests generated: ${tests.length} chars`);
      return { code: tests };
    },
  );

/**
 * Code sync node — validates syntax and writes main.py + test.py to sandbox.
 *
 * Creates a new E2B sandbox when no sandboxId is provided.
 * Returns SyncResult with success flag and sandbox_id.
 */
export const codeSyncNode = fn('code_sync_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: { main_code: string; test_code: string; sandbox_id?: string },
    ): Promise<SyncResult> => {
      const { main_code, test_code, sandbox_id: existingSandboxId } = input;
      ctx.logger.info('Syncing code and tests to sandbox');

      if (!main_code || !test_code) {
        throw new Error('Cannot sync: main_code or test_code is empty');
      }

      // Validate syntax locally before burning a sandbox round-trip
      for (const [filename, src] of [
        ['main.py', main_code],
        ['test.py', test_code],
      ] as Array<[string, string]>) {
        const { valid, error } = _validatePythonSyntax(src);
        if (!valid) {
          ctx.logger.error(`Syntax error in ${filename}: ${error}`);
          return {
            success: false,
            sandbox_id: existingSandboxId,
            message: `Syntax error in ${filename}: ${error}`,
          };
        }
      }

      // Create or reuse sandbox
      let sandboxId = existingSandboxId;
      if (!sandboxId) {
        ctx.logger.info('Creating new E2B sandbox');
        const result = await createSandbox(ctx);
        sandboxId = result.sandbox_id;
        if (!sandboxId) {
          throw new Error('Failed to create sandbox — no ID returned');
        }
        ctx.logger.info(`Created sandbox: ${sandboxId}`);
      } else {
        ctx.logger.info(`Using existing sandbox: ${sandboxId}`);
      }

      ctx.logger.debug('Writing main.py...');
      await writeFile(ctx, sandboxId, 'main.py', main_code);

      ctx.logger.debug('Writing test.py...');
      await writeFile(ctx, sandboxId, 'test.py', test_code);

      ctx.logger.info('Code and tests synced successfully');
      return {
        success: true,
        sandbox_id: sandboxId,
        message: 'Code and tests synced successfully',
      };
    },
  );

/**
 * Install dependencies node — detects third-party imports and pip-installs them.
 */
export const installDepsNode = fn('install_deps_node')
  .retry({ maxAttempts: 2, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: { main_code: string; sandbox_id: string },
    ): Promise<boolean> => {
      const { main_code, sandbox_id } = input;

      const pkgs = _extractThirdPartyImports(main_code);
      if (pkgs.length === 0) {
        ctx.logger.info('No third-party dependencies detected');
        return true;
      }

      ctx.logger.info(`Installing dependencies: ${pkgs.join(', ')}`);
      const result = await runCommand(
        ctx,
        sandbox_id,
        `pip install -q ${pkgs.join(' ')} 2>&1 | tail -5`,
        120000,
      );

      if (result.success) {
        ctx.logger.info(`Dependencies installed: ${pkgs.join(', ')}`);
      } else {
        ctx.logger.warn(
          `pip install completed with warnings: ${result.stdout.slice(0, 200)}`,
        );
      }
      return true;
    },
  );

/**
 * Code executor node — runs pytest inside the sandbox and returns ExecutionResult.
 */
export const codeExecutorNode = fn('code_executor_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: { sandbox_id: string },
    ): Promise<ExecutionResult> => {
      const { sandbox_id } = input;
      ctx.logger.info('Executing tests in sandbox');

      if (!sandbox_id) {
        throw new Error('No sandbox_id provided');
      }

      try {
        const execResult = await runCommand(
          ctx,
          sandbox_id,
          'pytest test.py --tb=short -q 2>&1',
          30000,
        );

        const { exit_code, stdout, stderr } = execResult;
        ctx.logger.debug(`Exit code: ${exit_code}`);
        ctx.logger.debug(`Stdout (first 200): ${stdout.slice(0, 200)}...`);

        if (exit_code === 0) {
          ctx.logger.info('All tests passed!');
          return {
            status: 'tests_passed',
            next_action: 'success',
            test_results: execResult as any,
            error_logs: undefined,
          };
        } else {
          // exit_code 1 = test failures
          // exit_code 2 = collection error (syntax/import errors in generated code)
          // both are recoverable — let the error analyzer + fixer handle them
          const errorOutput = stdout || stderr;
          ctx.logger.warn(
            `Tests failed (exit code ${exit_code}) — retry needed\nstdout: ${stdout.slice(0, 200)}`,
          );
          return {
            status: 'tests_failed',
            next_action: 'retry_code',
            test_results: execResult as any,
            error_logs: errorOutput,
          };
        }
      } catch (err) {
        const msg = (err as Error).message;
        ctx.logger.error(`Test execution failed: ${msg}`);
        return {
          status: 'tests_failed',
          next_action: 'retry_code',
          test_results: undefined,
          error_logs: msg,
        };
      }
    },
  );

/**
 * Error analyzer node — analyzes pytest failures and produces structured ErrorAnalysis.
 */
export const errorAnalyzerNode = fn('error_analyzer_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: {
        task_description: string;
        dev_plan: string;
        generated_code: string;
        generated_tests: string;
        error_logs: string;
      },
    ): Promise<ErrorAnalysis> => {
      const {
        task_description,
        dev_plan,
        generated_code,
        generated_tests,
        error_logs,
      } = input;

      ctx.logger.info('Analyzing test failures');
      ctx.logger.debug(`Error logs length: ${error_logs.length} chars`);

      const userPrompt = ERROR_ANALYZER_USER_PROMPT
        .replace('{task_description}', task_description)
        .replace('{development_plan}', dev_plan)
        .replace('{generated_code}', generated_code)
        .replace('{generated_tests}', generated_tests)
        .replace('{error_logs}', error_logs);

      const response = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: ERROR_ANALYZER_SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        config: {
          temperature: 0,
          responseFormat: {
            formatType: 'json_schema',
            schemaName: 'ErrorAnalysis',
            schema: JSON.stringify(ERROR_ANALYSIS_SCHEMA),
            strict: true,
          },
        },
      });

      const analysis = JSON.parse(response.text) as ErrorAnalysis;
      ctx.logger.info('Error analysis complete');
      ctx.logger.debug(`Failed tests: ${analysis.failed_tests.length}`);
      ctx.logger.debug(`Root causes: ${analysis.root_causes.length}`);
      return analysis;
    },
  );

/**
 * Final response node — generates markdown documentation for the completed task.
 */
export const finalResponseNode = fn('final_response_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: { task_description: string; generated_code: string },
    ): Promise<FinalResponse> => {
      const { task_description, generated_code } = input;
      ctx.logger.info('Generating documentation');

      const userPrompt = MARKDOWN_USER_PROMPT
        .replace('{task_description}', task_description)
        .replace('{generated_code}', generated_code);

      const response = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: MARKDOWN_SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        config: {
          temperature: 0,
        },
      });

      const markdownContent = response.text;
      ctx.logger.info('Documentation generated successfully');
      return { markdown_content: markdownContent };
    },
  );
