/**
 * Coding Agent — AGNT5 Worker entry point.
 *
 * Connects to the AGNT5 platform coordinator and registers all
 * functions, tools, and workflows.
 *
 * Usage:
 *   npx tsx app.ts
 *
 * Requires:
 *   - Running AGNT5 platform (coordinator at localhost:34186 by default)
 *   - GROQ_API_KEY for LLM calls
 *   - E2B_API_KEY for sandbox execution
 */

import 'dotenv/config';
import { Worker } from '@agnt5/sdk';

// Import modules to register their tools, functions, and workflow with the runtime
import './src/tools.js';
import './src/functions.js';
import './src/workflow.js';

async function main() {
  const coordinatorEndpoint =
    process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186';

  // Validate required environment variables
  const missing: string[] = [];
  if (!process.env.GROQ_API_KEY) missing.push('GROQ_API_KEY');
  if (!process.env.E2B_API_KEY) missing.push('E2B_API_KEY');

  if (missing.length > 0) {
    console.error(
      `Missing required environment variables: ${missing.join(', ')}\n` +
        'Please create a .env file based on .env.example',
    );
    process.exit(1);
  }

  const worker = new Worker('coding-agent', {
    serviceVersion: '1.0.0',
    coordinatorEndpoint,
  });

  // worker.run() prints the startup banner — no need to duplicate it here.
  await worker.run();
}

main().catch((error) => {
  console.error('Worker error:', error);
  process.exit(1);
});
