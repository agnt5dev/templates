/**
 * AGNT5 Hacker News digest — worker entry point.
 */

import { Worker } from '@agnt5/sdk';

// Importing the modules registers their functions/workflows via decorators.
import './src/functions.js';
import './src/workflows.js';

async function main() {
  console.log('Starting quickstart worker...');

  const coordinatorEndpoint =
    process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34180';

  const worker = new Worker('quickstart', {
    serviceVersion: '0.1.0',
    coordinatorEndpoint,
  });

  console.log('Worker created. Connecting to AGNT5 runtime...');
  await worker.run();
}

main().catch((error) => {
  console.error('Worker error:', error);
  process.exit(1);
});
