/**
 * AGNT5 Tutor Agent Worker — Demonstrates agent handoffs
 *
 * Architecture:
 *   triage_tutor → history_tutor  (history questions)
 *               → math_tutor     (math questions)
 *
 * Usage:
 *   npx tsx app.ts
 *
 * Requires:
 *   - Running AGNT5 platform (coordinator at localhost:34186)
 *   - OPENAI_API_KEY
 */

import { Worker } from '@agnt5/sdk';

// Import to trigger workflow registration via workflow()
import './src/workflows.js';

import { getHistoryTutorAgent, getMathTutorAgent, getTutorAgent } from './src/agents.js';

const SERVICE_NAME = 'agnt5-tutor-agent';

async function main() {
  console.log(`Starting ${SERVICE_NAME} worker...`);

  const coordinatorEndpoint =
    process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186';

  const worker = new Worker(SERVICE_NAME, {
    serviceVersion: '1.0.0',
    coordinatorEndpoint,
  });

  try {
    // Initialize agents in dependency order: specialists first, triage last
    worker.registerAgents([
      getHistoryTutorAgent(),
      getMathTutorAgent(),
      getTutorAgent(),
    ]);
  } catch (error) {
    console.warn(
      'Could not create agents (OPENAI_API_KEY may not be set):',
      (error as Error).message,
    );
    console.warn('Workflow is still registered and will work once API key is provided.');
  }

  // worker.run() prints the startup banner — no need to duplicate it here.
  await worker.run();
}

main().catch((error) => {
  console.error('Worker failed:', error);
  process.exit(1);
});
