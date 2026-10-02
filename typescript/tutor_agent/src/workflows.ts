/**
 * Tutor Workflows for Educational Interactions
 *
 * Demonstrates the agent handoff pattern where a triage agent routes
 * the student's question to the appropriate specialist tutor.
 */

import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';
import { getTutorAgent } from './agents.js';

export const tutorChatWorkflow = workflow(
  'tutor_chat_workflow',
  async (ctx: Context, input: { message: string }) => {
    const { message } = input;
    ctx.logger.info(`Tutor chat workflow - message: ${message}`);

    // Errors are not caught here: when the model call fails (no OPENAI_API_KEY,
    // a provider outage), the run fails with that error rather than returning
    // a canned answer as a success.
    const result = await getTutorAgent().run(message, ctx);
    return {
      output: result.output,
    };
  },
);
