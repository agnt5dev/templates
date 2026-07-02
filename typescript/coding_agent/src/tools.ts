/**
 * E2B Sandbox tools — exact TypeScript replication of the Python E2BSandboxTools class.
 *
 * Tools registered:
 *   create_sandbox  — create or reconnect to an E2B sandbox
 *   write_file      — write a file into the sandbox
 *   read_file       — read a file from the sandbox
 *   list_files      — list files/directories in the sandbox
 *   delete_file     — delete a file or directory from the sandbox
 *   run_command     — run a shell command in the sandbox
 *   run_code        — run code directly (python/js/ts) in the sandbox
 *
 * Requires E2B_API_KEY in environment.
 */

import { Sandbox } from '@e2b/code-interpreter';
import { tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

const apiKey = () => process.env.E2B_API_KEY;

// ── Helpers ────────────────────────────────────────────────────────────

async function connect(sandboxId: string): Promise<Sandbox> {
  return Sandbox.connect(sandboxId, { apiKey: apiKey() });
}

// ── Tool implementations ───────────────────────────────────────────────

export async function createSandboxImpl(
  ctx: Context,
  sandbox_id?: string,
  metadata?: Record<string, string>,
  envs?: Record<string, string>,
): Promise<{ status?: string; sandbox_id?: string; error?: string }> {
  try {
    if (sandbox_id) {
      ctx.logger.info(`Reconnecting to existing sandbox: ${sandbox_id}`);
      try {
        await Sandbox.connect(sandbox_id, { apiKey: apiKey() });
        return { status: `Reconnected to sandbox: ${sandbox_id}`, sandbox_id };
      } catch (e) {
        ctx.logger.warn(`Reconnection failed: ${e}, creating new sandbox`);
      }
    }

    ctx.logger.info('Creating new E2B sandbox');
    const opts: any = { apiKey: apiKey() };
    if (metadata) opts.metadata = metadata;
    if (envs) opts.envs = envs;

    const sb = await Sandbox.create(opts);
    const id = sb.sandboxId;
    ctx.logger.info(`✅ Sandbox created: ${id}`);
    return { status: `Sandbox created successfully: ${id}`, sandbox_id: id };
  } catch (e) {
    ctx.logger.error(`Failed to create sandbox: ${e}`);
    return { error: `Sandbox creation failed: ${String(e)}` };
  }
}

export async function writeFileImpl(
  ctx: Context,
  sandbox_id: string,
  path: string,
  content: string,
): Promise<string> {
  if (!sandbox_id) return 'Error: sandbox_id is required';
  try {
    ctx.logger.debug(`Writing file: ${path} (${content.length} chars)`);
    const sb = await connect(sandbox_id);
    await sb.files.write(path, content);
    ctx.logger.info(`✅ File written: ${path}`);
    return `File written successfully: ${path}`;
  } catch (e) {
    ctx.logger.error(`Failed to write file ${path}: ${e}`);
    return `Error writing file ${path}: ${String(e)}`;
  }
}

export async function readFileImpl(
  ctx: Context,
  sandbox_id: string,
  path: string,
): Promise<string> {
  if (!sandbox_id) return 'Error: sandbox_id is required';
  try {
    ctx.logger.debug(`Reading file: ${path}`);
    const sb = await connect(sandbox_id);
    const content = await sb.files.read(path);
    ctx.logger.info(`✅ File read: ${path} (${content.length} chars)`);
    return `File content from ${path}:\n${content}`;
  } catch (e) {
    ctx.logger.error(`Failed to read file ${path}: ${e}`);
    return `Error reading file ${path}: ${String(e)}`;
  }
}

export async function listFilesImpl(
  ctx: Context,
  sandbox_id: string,
  path = '/',
): Promise<string> {
  if (!sandbox_id) return 'Error: sandbox_id is required';
  try {
    const sb = await connect(sandbox_id);
    const fileList = await sb.files.list(path);
    let result = `Files and directories in ${path}:\n`;
    for (const f of fileList) {
      const type = f.type === 'dir' ? 'DIR' : 'FILE';
      result += `  ${type}: ${f.name}\n`;
    }
    ctx.logger.info(`Listed ${fileList.length} items in ${path}`);
    return result;
  } catch (e) {
    ctx.logger.error(`Failed to list files in ${path}: ${e}`);
    return `Error listing files: ${String(e)}`;
  }
}

export async function deleteFileImpl(
  ctx: Context,
  sandbox_id: string,
  path: string,
): Promise<string> {
  if (!sandbox_id) return 'Error: sandbox_id is required';
  try {
    const sb = await connect(sandbox_id);
    await sb.files.remove(path);
    ctx.logger.info(`✅ Deleted: ${path}`);
    return `Successfully deleted: ${path}`;
  } catch (e) {
    ctx.logger.error(`Failed to delete ${path}: ${e}`);
    return `Error deleting ${path}: ${String(e)}`;
  }
}

export async function runCommandImpl(
  ctx: Context,
  sandbox_id: string,
  command: string,
  timeout_ms = 30000,
  capture_output = true,
  working_directory?: string,
): Promise<{
  exit_code: number | null;
  stdout: string;
  stderr: string;
  error?: string;
  success: boolean;
  execution_time_ms: number;
}> {
  if (!sandbox_id) {
    return { exit_code: null, stdout: '', stderr: 'Error: sandbox_id is required', error: 'No sandbox_id', success: false, execution_time_ms: 0 };
  }

  try {
    ctx.logger.info(`🚀 Running command: ${command}`);
    const sb = await connect(sandbox_id);
    const start = Date.now();

    const opts: any = { timeoutMs: timeout_ms };
    if (working_directory) opts.cwd = working_directory;

    let exit_code: number;
    let stdout: string;
    let stderr: string;
    let error: string | undefined;

    try {
      const result = await sb.commands.run(command, opts);
      exit_code = result.exitCode ?? 0;
      stdout = result.stdout ?? '';
      stderr = result.stderr ?? '';
    } catch (e: any) {
      exit_code = e.exitCode ?? e.exit_code ?? 1;
      stdout = e.stdout ?? '';
      stderr = e.stderr ?? '';
      error = String(e);
      ctx.logger.debug(`Command failed with exit code ${exit_code}`);
    }

    const execution_time_ms = Date.now() - start;

    if (exit_code === 0) {
      ctx.logger.info(`✅ Command succeeded (${execution_time_ms}ms)`);
    } else {
      ctx.logger.warn(`❌ Command failed with exit code ${exit_code} (${execution_time_ms}ms)`);
    }

    return {
      exit_code,
      stdout: capture_output ? stdout : '',
      stderr: capture_output ? stderr : '',
      error,
      success: exit_code === 0,
      execution_time_ms,
    };
  } catch (e) {
    ctx.logger.error(`Unexpected error running command: ${e}`);
    return { exit_code: null, stdout: '', stderr: String(e), error: String(e), success: false, execution_time_ms: 0 };
  }
}

export async function runCodeImpl(
  ctx: Context,
  sandbox_id: string,
  code: string,
  language = 'python',
  envs?: Record<string, string>,
  timeout_ms = 60000,
): Promise<string> {
  if (!sandbox_id) return '{"error": "sandbox_id is required"}';
  try {
    ctx.logger.info(`Running ${language} code (${code.length} chars)`);
    const sb = await connect(sandbox_id);
    const opts: any = { language, timeoutMs: timeout_ms };
    if (envs) opts.envs = envs;
    const execution = await sb.runCode(code, opts);
    ctx.logger.info('✅ Code execution completed');
    return JSON.stringify(execution);
  } catch (e) {
    ctx.logger.error(`Code execution failed: ${e}`);
    return `{"error": "${String(e).replace(/"/g, '\\"')}"}`;
  }
}

// ── AGNT5 tool() registrations — appear in Studio ──────────────────────

export const createSandboxTool = tool(
  'create_sandbox',
  {
    description: 'Create a new E2B sandbox for code execution, or reconnect to an existing one.',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'Existing sandbox ID to reconnect (optional)' },
        metadata: { type: 'object', description: 'Custom metadata tags for the sandbox (optional)' },
        envs: { type: 'object', description: 'Environment variables for the sandbox (optional)' },
      },
      required: [],
    },
  },
  async (ctx: Context, args: { sandbox_id?: string; metadata?: Record<string, string>; envs?: Record<string, string> }) =>
    createSandboxImpl(ctx, args.sandbox_id, args.metadata, args.envs),
);

export const writeFileTool = tool(
  'write_file',
  {
    description: 'Write a file to the E2B sandbox.',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'E2B sandbox identifier' },
        path: { type: 'string', description: 'File path to write (e.g. "main.py")' },
        content: { type: 'string', description: 'File content as string' },
      },
      required: ['sandbox_id', 'path', 'content'],
    },
  },
  async (ctx: Context, args: { sandbox_id: string; path: string; content: string }) =>
    writeFileImpl(ctx, args.sandbox_id, args.path, args.content),
);

export const readFileTool = tool(
  'read_file',
  {
    description: 'Read a file from the E2B sandbox.',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'E2B sandbox identifier' },
        path: { type: 'string', description: 'File path to read' },
      },
      required: ['sandbox_id', 'path'],
    },
  },
  async (ctx: Context, args: { sandbox_id: string; path: string }) =>
    readFileImpl(ctx, args.sandbox_id, args.path),
);

export const listFilesTool = tool(
  'list_files',
  {
    description: 'List files and directories in the sandbox.',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'E2B sandbox identifier' },
        path: { type: 'string', description: 'Directory path to list (default: "/")' },
      },
      required: ['sandbox_id'],
    },
  },
  async (ctx: Context, args: { sandbox_id: string; path?: string }) =>
    listFilesImpl(ctx, args.sandbox_id, args.path),
);

export const deleteFileTool = tool(
  'delete_file',
  {
    description: 'Delete a file or directory from the sandbox.',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'E2B sandbox identifier' },
        path: { type: 'string', description: 'Path to delete' },
      },
      required: ['sandbox_id', 'path'],
    },
  },
  async (ctx: Context, args: { sandbox_id: string; path: string }) =>
    deleteFileImpl(ctx, args.sandbox_id, args.path),
);

export const runCommandTool = tool(
  'run_command',
  {
    description: 'Run a shell command in the E2B sandbox.',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'E2B sandbox identifier' },
        command: { type: 'string', description: 'Shell command to execute (e.g. "pytest test.py")' },
        working_directory: { type: 'string', description: 'Working directory for command execution (optional)' },
        timeout_ms: { type: 'number', description: 'Command timeout in milliseconds (default: 30000)' },
        capture_output: { type: 'boolean', description: 'Whether to capture stdout/stderr (default: true)' },
      },
      required: ['sandbox_id', 'command'],
    },
  },
  async (ctx: Context, args: { sandbox_id: string; command: string; working_directory?: string; timeout_ms?: number; capture_output?: boolean }) =>
    runCommandImpl(ctx, args.sandbox_id, args.command, args.timeout_ms, args.capture_output, args.working_directory),
);

export const runCodeTool = tool(
  'run_code',
  {
    description: 'Run code directly in the E2B sandbox (alternative to run_command).',
    inputSchema: {
      type: 'object',
      properties: {
        sandbox_id: { type: 'string', description: 'E2B sandbox identifier' },
        code: { type: 'string', description: 'Code to execute' },
        language: { type: 'string', description: 'Programming language: python, javascript, typescript (default: python)' },
        envs: { type: 'object', description: 'Environment variables for execution (optional)' },
        timeout_ms: { type: 'number', description: 'Timeout in milliseconds (default: 60000)' },
      },
      required: ['sandbox_id', 'code'],
    },
  },
  async (ctx: Context, args: { sandbox_id: string; code: string; language?: string; envs?: Record<string, string>; timeout_ms?: number }) =>
    runCodeImpl(ctx, args.sandbox_id, args.code, args.language, args.envs, args.timeout_ms),
);
