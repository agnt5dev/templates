/**
 * Travel Booking Workflows
 *
 * Provides workflows for orchestrating travel booking operations.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';
import { createTravelBookingAgent } from './agents.js';

export const travelBookingWorkflow = workflow(
  'travel_booking_workflow',
  async (ctx: Context, input: { message: string }) => {
    const { message } = input;
    ctx.logger.info(`Travel booking workflow - message: ${message.slice(0, 100)}...`);

    const agent = createTravelBookingAgent();
    const result = await agent.run(message, ctx);

    ctx.logger.info('Travel booking agent completed');

    return {
      status: 'completed',
      output: result.output,
    };
  },
);
