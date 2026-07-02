import 'dotenv/config';
import { Worker } from '@agnt5/sdk';

// Import modules to register their tools, functions, and workflow with the runtime
import './src/tools.js';
import './src/functions.js';
import './src/workflow.js';

import { contextBuilderAgent, reviewerAgent } from './src/agents.js';

async function main() {
  const worker = new Worker('code-reviewer', {
    serviceVersion: '2.0.0',
    coordinatorEndpoint: process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186',
  });

  worker.registerAgents([contextBuilderAgent, reviewerAgent]);
  await worker.run();
}

main().catch(console.error);
