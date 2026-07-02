import 'dotenv/config';
import { Worker } from '@agnt5/sdk';

import './src/functions.js';
import './src/tools.js';
import './src/workflow.js';
import { createWeatherAgent } from './src/agents.js';
import { config } from './src/config.js';

async function main() {
  const worker = new Worker(config.SERVICE_NAME, {
    serviceVersion: config.SERVICE_VERSION,
    coordinatorEndpoint: process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186',
  });

  worker.registerAgents([createWeatherAgent()]);

  // worker.run() prints the startup banner — no need to duplicate it here.
  await worker.run();
}

main().catch((error) => {
  console.error('❌ Worker error:', error);
  process.exit(1);
});
