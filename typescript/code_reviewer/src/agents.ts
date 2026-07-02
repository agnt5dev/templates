import { Agent, LM } from '@agnt5/sdk';

import { jiraTicketFetcher, linearTicketFetcher, prFetcher, detectTicketSource } from './tools.js';
import { CONTEXT_BUILDER_PROMPT, CODE_REVIEWER_PROMPT } from './prompts/index.js';

export const contextBuilderAgent = new Agent({
  name: 'context_builder',
  model: LM.openai(),
  modelName: 'openai/gpt-4.1-mini',
  instructions: CONTEXT_BUILDER_PROMPT,
  tools: [prFetcher, jiraTicketFetcher, linearTicketFetcher, detectTicketSource],
  temperature: 0.0,
  maxIterations: 3,
});

export const reviewerAgent = new Agent({
  name: 'code_reviewer',
  model: LM.openai(),
  modelName: 'openai/gpt-4.1-mini',
  instructions: CODE_REVIEWER_PROMPT,
  tools: [prFetcher, jiraTicketFetcher, linearTicketFetcher],
  temperature: 0.0,
  maxIterations: 3,
});
