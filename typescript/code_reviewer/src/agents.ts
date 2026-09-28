import { Agent, LM } from '@agnt5/sdk';
import type { AgentCallbacks } from '@agnt5/sdk';

import { jiraTicketFetcher, linearTicketFetcher, prFetcher, detectTicketSource } from './tools.js';
import { CONTEXT_BUILDER_PROMPT, CODE_REVIEWER_PROMPT } from './prompts/index.js';

// gpt-6 rejects any temperature, and @agnt5/sdk sends a default of 0.7, so drop it before each model call.
const dropTemperature: NonNullable<AgentCallbacks['beforeModel']> = (_ctx, request) => {
  delete request.config?.temperature;
};

export const contextBuilderAgent = new Agent({
  name: 'context_builder',
  model: LM.openai(),
  modelName: 'openai/gpt-6-luna',
  callbacks: { beforeModel: dropTemperature },
  instructions: CONTEXT_BUILDER_PROMPT,
  tools: [prFetcher, jiraTicketFetcher, linearTicketFetcher, detectTicketSource],
  maxIterations: 3,
});

export const reviewerAgent = new Agent({
  name: 'code_reviewer',
  model: LM.openai(),
  modelName: 'openai/gpt-6-luna',
  callbacks: { beforeModel: dropTemperature },
  instructions: CODE_REVIEWER_PROMPT,
  tools: [prFetcher, jiraTicketFetcher, linearTicketFetcher],
  maxIterations: 3,
});
