/**
 * Deep Research Agent — AGNT5 Worker
 *
 * Connects to the AGNT5 platform coordinator and registers the
 * deep research workflow, functions, agents, and tools.
 *
 * Usage:
 *   npx tsx app.ts
 *
 * Requires:
 *   - Running AGNT5 platform (coordinator at localhost:34186)
 *   - OPENAI_API_KEY for the research agents
 */

import { Worker } from '@agnt5/sdk';

// Import to trigger registration via workflow() / fn()
import './src/workflows.js';
import './src/functions.js';

import { getScopingAgent, getResearchAgent, getWritingAgent } from './src/agents.js';

const SERVICE_NAME = 'deep-research';

async function main() {
  const coordinatorEndpoint =
    process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186';

  const worker = new Worker(SERVICE_NAME, {
    serviceVersion: '2.0.0',
    coordinatorEndpoint,
  });

  try {
    worker.registerAgents([
      getScopingAgent(),
      getResearchAgent(),
      getWritingAgent(),
    ]);
  } catch (error) {
    console.warn(
      'Could not create agents (OPENAI_API_KEY may not be set):',
      (error as Error).message,
    );
    console.warn('Workflow and functions are still registered.');
  }

  // worker.run() prints the startup banner (service, registered components,
  // dashboard URL, connection status) — no need to duplicate it here.
  await worker.run();
}

main().catch((error) => {
  console.error('Worker failed:', error);
  process.exit(1);
});
