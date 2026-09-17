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
  InvalidTest,
  TestRepair,
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
  TEST_REPAIR_SYSTEM_PROMPT,
  TEST_REPAIR_USER_PROMPT,
} from './prompts/index.js';
import { createSandboxImpl as createSandbox, writeFileImpl as writeFile, runCommandImpl as runCommand } from './tools.js';

// ============================================================================
// Module-level LM instance
// ============================================================================

const lm = LM.groq({ apiKey: process.env.GROQ_API_KEY });
const MODEL = 'groq/qwen/qwen3.8-27b';
// Upper bound on generated output. Left unset, the provider's default cuts long
// code off mid-expression, and the half-written file fails every retry.
const MAX_OUTPUT_TOKENS = 8192;

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
 * Pre-sandbox sanity check for Python source.
 *
 * Node cannot run ast.parse() (the Python template does), so this is
 * structural. The checks run on the code with string and comment contents
 * removed, so a fence or a bracket inside a string is data, not syntax: a
 * text-processing task's tests legitimately contain both. What is caught is
 * what a truncated or malformed model response actually looks like: nothing, a
 * fence outside any string, an unterminated string, mismatched brackets. A
 * syntax error that slips through still fails when the suite runs in the
 * sandbox; checking here keeps a broken candidate from replacing working tests
 * (AGNT5-1165, the port of the Go validator).
 */
export function _validatePythonSyntax(code: string): { valid: boolean; error: string } {
  if (!code || code.trim().length === 0) {
    return { valid: false, error: 'Code is empty' };
  }
  const stripped = _stripPythonLiterals(code);
  if (stripped === null) {
    return { valid: false, error: 'Code has an unterminated string literal' };
  }
  if (stripped.includes('```')) {
    return { valid: false, error: 'Code still contains markdown fence markers' };
  }
  const brackets = _checkBrackets(stripped);
  if (brackets) return { valid: false, error: brackets };
  return { valid: true, error: '' };
}

/**
 * The code with every comment removed and every string literal's contents
 * replaced by an empty literal, so later checks see only syntax. Newlines are
 * kept so line-based logic still lines up. Returns null for an unterminated
 * string -- the truncated-response shape -- rather than guessing.
 */
export function _stripPythonLiterals(code: string): string | null {
  let out = '';
  const n = code.length;
  let i = 0;
  while (i < n) {
    const c = code[i];
    if (c === '#') {
      while (i < n && code[i] !== '\n') i++;
      continue;
    }
    if (c === "'" || c === '"') {
      const triple = code.startsWith(c.repeat(3), i);
      const quoteLen = triple ? 3 : 1;
      out += c.repeat(quoteLen * 2); // an empty literal of the same kind
      i += quoteLen;
      let closed = false;
      while (i < n) {
        if (code[i] === '\\') { i += 2; continue; }
        if (code[i] === '\n') {
          if (!triple) break; // a single-quoted string cannot span lines
          out += '\n';
        }
        if (code[i] === c && (!triple || code.startsWith(c.repeat(3), i))) {
          i += quoteLen;
          closed = true;
          break;
        }
        i++;
      }
      if (!closed) return null;
      continue;
    }
    out += c;
    i++;
  }
  return out;
}

/** Delimiters must open and close in matching pairs; a plain count let `f([)]` through. */
export function _checkBrackets(stripped: string): string | null {
  const closers: Record<string, string> = { ')': '(', ']': '[', '}': '{' };
  const stack: string[] = [];
  for (const c of stripped) {
    if (c === '(' || c === '[' || c === '{') stack.push(c);
    else if (c === ')' || c === ']' || c === '}') {
      if (!stack.length || stack[stack.length - 1] !== closers[c]) {
        return `Code has mismatched brackets near '${c}', so it is truncated or malformed`;
      }
      stack.pop();
    }
  }
  if (stack.length) return `Code has ${stack.length} unclosed bracket(s), so it is truncated or malformed`;
  return null;
}

// An assert whose whole condition is a constant that always holds, with or
// without a message. `assert True == predicate()` does not match.
const VACUOUS_ASSERTION = /^assert\s*\(?\s*(True|1|not\s+False)\s*\)?\s*(,.*)?$/;
// The other ways a test states an expectation.
const ASSERTION_CALL = /(^|[^\w.])(pytest\.raises|self\.assert[A-Za-z]+|self\.fail|raise)\b/;

/**
 * Whether a test body claims anything at all. A test rewritten to `pass`,
 * `return` or `assert True` turns a failing suite green without fixing the
 * code -- the exact move the guardrails below promise to prevent. Looks at the
 * code with strings and comments stripped, so `pass  # assert old == 5` is seen
 * for the empty test it is (AGNT5-1165).
 */
export function _stillAsserts(testSource: string): boolean {
  const stripped = _stripPythonLiterals(testSource);
  if (stripped === null) return false;
  for (const line of stripped.split('\n')) {
    const stmt = line.trim();
    if (/^assert(?![\w])/.test(stmt)) {
      if (!VACUOUS_ASSERTION.test(stmt)) return true;
      continue;
    }
    if (ASSERTION_CALL.test(stmt)) return true;
  }
  return false;
}

// ============================================================================
// Test repair guardrails
// ============================================================================

/** Reduce a pytest id such as `test.py::test_x[P3Y-9.0]` to `test_x`. */
export function _baseTestName(name: string): string {
  return (name.split('::').pop() ?? name).split('[')[0].trim();
}

const _indentOf = (line: string): number => line.length - line.trimStart().length;
const _bracketDelta = (line: string): number =>
  (line.match(/[)\]}]/g) ?? []).length - (line.match(/[(\[{]/g) ?? []).length;

/**
 * Map each test function to its [start, end) line range, decorators included.
 *
 * Node can't parse Python here (the Python template uses `ast`), so blocks are
 * found by indentation and bracket balance: the decorators above a
 * `def test…` line — including multi-line ones such as
 * `@pytest.mark.parametrize(...)`, where expectations often live — then the
 * signature, then every following line indented deeper or blank. That covers
 * the plain top-level and class-level functions a generated pytest file uses.
 */
function _testFunctionSpans(code: string): Map<string, [number, number]> {
  const lines = code.split('\n');
  const spans = new Map<string, [number, number]>();
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(\s*)(?:async\s+)?def\s+(test\w*)\s*\(/);
    if (!m) continue;
    const indent = m[1].length;

    // Walk up through decorators; a positive depth means we're inside one
    // that opened further up.
    let start = i;
    let depth = 0;
    for (let j = i - 1; j >= 0; j--) {
      const text = lines[j].trim();
      const delta = _bracketDelta(text);
      if (depth === 0) {
        if (text.startsWith('@') && _indentOf(lines[j]) === indent) {
          start = j;
          continue;
        }
        if (delta > 0 && text !== '') {
          depth += delta;
          start = j;
          continue;
        }
        break;
      }
      depth = Math.max(0, depth + delta);
      start = j;
    }

    // The signature may span lines; then the body is everything deeper.
    let end = i + 1;
    let sig = -_bracketDelta(lines[i]);
    while (sig > 0 && end < lines.length) {
      sig -= _bracketDelta(lines[end]);
      end++;
    }
    while (end < lines.length && (lines[end].trim() === '' || _indentOf(lines[end]) > indent)) end++;
    while (end > i + 1 && lines[end - 1].trim() === '') end--;
    spans.set(m[2], [start, end]);
  }
  return spans;
}

function _testSources(code: string): Map<string, string> {
  const lines = code.split('\n');
  const out = new Map<string, string>();
  for (const [name, [start, end]] of _testFunctionSpans(code)) {
    out.set(name, lines.slice(start, end).join('\n').trim());
  }
  return out;
}

/** The file with every test function removed, blank lines ignored. */
function _codeOutsideTests(code: string): string {
  const lines = code.split('\n');
  const inside = new Set<number>();
  for (const [start, end] of _testFunctionSpans(code).values()) {
    for (let k = start; k < end; k++) inside.add(k);
  }
  return lines
    .filter((l, k) => !inside.has(k) && l.trim() !== '')
    .map((l) => l.trimEnd())
    .join('\n');
}

/**
 * Accept a repaired suite only if it corrects flagged tests and nothing else.
 *
 * The guardrails live here, not only in the prompt, so the agent cannot make a
 * failing run pass by deleting, weakening or rewriting tests it wasn't asked to.
 */
export function _checkTestRepair(
  original: string,
  candidate: string,
  targets: Set<string>,
): { accepted: boolean; reason: string; repaired: string[] } {
  const syntax = _validatePythonSyntax(candidate);
  if (!syntax.valid) return { accepted: false, reason: `repaired tests are invalid: ${syntax.error}`, repaired: [] };
  const before = _testSources(original);
  const after = _testSources(candidate);
  const removed = [...before.keys()].filter((n) => !after.has(n)).sort();
  const added = [...after.keys()].filter((n) => !before.has(n)).sort();
  if (removed.length || added.length) {
    return {
      accepted: false,
      reason: `test set changed (removed [${removed.join(', ')}], added [${added.join(', ')}])`,
      repaired: [],
    };
  }
  const changed = [...before.keys()].filter((n) => before.get(n) !== after.get(n)).sort();
  const unflagged = changed.filter((n) => !targets.has(n));
  if (unflagged.length) {
    return { accepted: false, reason: `changed tests that were not flagged: [${unflagged.join(', ')}]`, repaired: [] };
  }
  if (_codeOutsideTests(original) !== _codeOutsideTests(candidate)) {
    return { accepted: false, reason: 'changed code outside the flagged tests', repaired: [] };
  }
  if (!changed.length) return { accepted: false, reason: 'no flagged test was changed', repaired: [] };
  // A flagged test may be corrected, not neutered: rewriting it to `pass` or
  // `assert True` makes the suite green while the code stays broken. The
  // docstring above has always promised this; nothing checked it.
  for (const name of changed) {
    if (!_stillAsserts(after.get(name) ?? '')) {
      return { accepted: false, reason: `repaired test ${name} no longer asserts anything`, repaired: [] };
    }
  }
  return { accepted: true, reason: '', repaired: changed };
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
        maxOutputTokens: MAX_OUTPUT_TOKENS,
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
          maxOutputTokens: MAX_OUTPUT_TOKENS,
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
          maxOutputTokens: MAX_OUTPUT_TOKENS,
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

      // createSandbox reconnects to an existing ID and falls back to a new
      // sandbox when it cannot -- but this node only called it when there
      // was no ID, so an expired sandbox (they live 300s; this workflow
      // retries for longer) was reused forever and every later sync failed
      // against one that no longer existed. It is called every time now, and
      // the ID that comes back is the live one (AGNT5-1165).
      const created = await createSandbox(ctx, existingSandboxId);
      let sandboxId = created.sandbox_id;
      if (!sandboxId) {
        throw new Error(`Failed to create sandbox: ${created.error ?? 'no ID returned'}`);
      }

      // writeFile reports failure in its result rather than throwing, and
      // those results used to be discarded.
      const writeBoth = async (target: string): Promise<string | undefined> => {
        for (const [path, content] of [['main.py', main_code], ['test.py', test_code]] as Array<[string, string]>) {
          ctx.logger.debug(`Writing ${path}...`);
          // writeFileImpl reports through its return string: "File written
          // successfully: <path>" or "Error writing file <path>: <reason>".
          // It never throws, which is why a dead sandbox went unnoticed here.
          const written = await writeFile(ctx, target, path, content);
          if (typeof written === 'string' && written.startsWith('Error')) {
            return written;
          }
        }
        return undefined;
      };

      let error = await writeBoth(sandboxId);
      if (error) {
        ctx.logger.warn(`Sandbox write failed (${error}), recreating the sandbox`);
        const replacement = await createSandbox(ctx);
        if (!replacement.sandbox_id) {
          return { success: false, sandbox_id: sandboxId, message: `sandbox write failed (${error}) and a replacement could not be created` };
        }
        sandboxId = replacement.sandbox_id;
        error = await writeBoth(sandboxId);
        if (error) return { success: false, sandbox_id: sandboxId, message: error };
      }

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
          maxOutputTokens: MAX_OUTPUT_TOKENS,
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
      if (analysis.invalid_tests?.length) {
        ctx.logger.warn(
          `${analysis.invalid_tests.length} test(s) contradict the task: ` +
            analysis.invalid_tests.map((t) => t.test_name).join(', '),
        );
      }
      return analysis;
    },
  );

/**
 * Test repair node — corrects tests the error analysis found to contradict the
 * task. Rejected repairs keep the original tests: a wrong repair is worse than
 * none.
 */
export const testRepairNode = fn('test_repair_node')
  .retry({ maxAttempts: 3, initialIntervalMs: 1000 })
  .backoff({ type: 'exponential', multiplier: 2 })
  .run(
    async (
      ctx: Context,
      input: { task_description: string; generated_tests: string; invalid_tests: InvalidTest[] },
    ): Promise<TestRepair> => {
      const { task_description, generated_tests, invalid_tests } = input;
      const targets = new Set(invalid_tests.map((t) => _baseTestName(t.test_name)));
      ctx.logger.info(`Repairing ${targets.size} test(s) with invalid expectations: ${[...targets].join(', ')}`);
      const listing = invalid_tests
        .map((t) => `- \`${t.test_name}\`: ${t.reason} Correct expectation: ${t.correct_expectation}`)
        .join('\n');

      // Function replacers: the inserted text is code, and a string replacement
      // would interpret any `$&` or `$1` inside it.
      const userPrompt = TEST_REPAIR_USER_PROMPT
        .replace('{task_description}', () => task_description)
        .replace('{generated_tests}', () => generated_tests)
        .replace('{invalid_tests}', () => listing);

      const response = await lm.generate({
        model: MODEL,
        messages: [
          { role: 'system', content: TEST_REPAIR_SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        config: {
          temperature: 0,
          maxOutputTokens: MAX_OUTPUT_TOKENS,
          responseFormat: {
            formatType: 'json_schema',
            schemaName: 'GeneratedCode',
            schema: JSON.stringify(GENERATED_CODE_SCHEMA),
            strict: true,
          },
        },
      });

      const candidate = _cleanCode((JSON.parse(response.text) as GeneratedCode).code);
      const check = _checkTestRepair(generated_tests, candidate, targets);
      if (!check.accepted) {
        ctx.logger.warn(`Test repair rejected, keeping the original tests: ${check.reason}`);
        return { accepted: false, code: generated_tests, repaired: [], reason: check.reason };
      }
      ctx.logger.info(`Repaired tests: ${check.repaired.join(', ')}`);
      return { accepted: true, code: candidate, repaired: check.repaired, reason: '' };
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
          maxOutputTokens: MAX_OUTPUT_TOKENS,
        },
      });

      const markdownContent = response.text;
      ctx.logger.info('Documentation generated successfully');
      return { markdown_content: markdownContent };
    },
  );
