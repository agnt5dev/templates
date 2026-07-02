/**
 * Travel Booking (Customer Service) — AGNT5 Worker
 *
 * Connects to the AGNT5 platform coordinator and registers the
 * travel booking workflow and agent.
 *
 * Usage:
 *   npx tsx app.ts
 *
 * Requires:
 *   - Running AGNT5 platform (coordinator at localhost:34186)
 *   - OPENAI_API_KEY for the travel booking agent
 *   - SERPAPI_KEY for real-time flight and hotel search
 */

import { Worker } from '@agnt5/sdk';

// Import workflow to trigger registration via workflow()
import './src/workflows.js';

import { createTravelBookingAgent } from './src/agents.js';

const SERVICE_NAME = 'customer-service';

async function main() {
  const coordinatorEndpoint =
    process.env.AGNT5_COORDINATOR_ENDPOINT || 'http://localhost:34186';

  const worker = new Worker(SERVICE_NAME, {
    serviceVersion: '1.0.0',
    coordinatorEndpoint,
  });

  try {
    const travelBookingAgent = createTravelBookingAgent();
    worker.registerAgents([travelBookingAgent]);
  } catch (error) {
    console.warn(
      'Could not create travel booking agent (OPENAI_API_KEY may not be set):',
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
