/**
 * AGNT5 MCP server starter: worker entry point.
 *
 * Importing ./src/server.js is what publishes the MCP server: a worker runs
 * only the module graph of agnt5.yaml's worker.command, and publishes the
 * servers defined in it.
 */

import 'dotenv/config';
import { Worker } from '@agnt5/sdk';

import './src/functions.js';
import './src/workflows.js';
import './src/server.js';

// A promise that rejects with nothing awaiting it would otherwise end the
// worker process in the middle of a run. Log it and keep serving.
process.on('unhandledRejection', (reason) => {
  console.error('unhandledRejection', reason);
});

async function main() {
  // `agnt5 dev` and deployed workers set AGNT5_COORDINATOR_ENDPOINT; the
  // fallback is the SDK's own default.
  const coordinatorEndpoint = process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186';

  const worker = new Worker('mcp-server', {
    serviceVersion: '0.1.0',
    coordinatorEndpoint,
  });

  // worker.run() prints the startup banner — no need to duplicate it here.
  await worker.run();
}

main().catch((error) => {
  console.error('Worker error:', error);
  process.exit(1);
});
