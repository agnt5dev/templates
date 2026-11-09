/**
 * AGNT5 expense processor — worker entry point.
 */

import { Worker } from '@agnt5/sdk';

// Importing the module registers its functions and workflow.
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

  const worker = new Worker('expense-processor', {
    serviceVersion: '0.1.0',
    coordinatorEndpoint,
  });

  await worker.run();
}

main().catch((error) => {
  console.error('Worker error:', error);
  process.exit(1);
});
