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

    try {
      const result = await getTutorAgent().run(message, ctx);
      return {
        output: result.output,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      ctx.logger.error(`Error running tutor agent: ${msg}`);
      return {
        output: `I apologize, but I'm having trouble processing your question right now. Could you please rephrase: ${message}`,
      };
    }
  },
);
