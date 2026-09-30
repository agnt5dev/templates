/**
 * AGNT5 Hacker News digest — worker entry point.
 */

import { Worker } from '@agnt5/sdk';

// Importing the modules registers their functions/workflows via decorators.
import './src/functions.js';
import './src/workflows.js';

// A promise that rejects with nothing awaiting it would otherwise end the
// worker process in the middle of a run. Log it and keep serving.
process.on('unhandledRejection', (reason) => {
  console.error('unhandledRejection', reason);
});

async function main() {
  // `agnt5 dev` and deployed workers set AGNT5_COORDINATOR_ENDPOINT; the
  // fallback is the SDK's own default.
  const coordinatorEndpoint =
    process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186';

  const worker = new Worker('quickstart', {
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
