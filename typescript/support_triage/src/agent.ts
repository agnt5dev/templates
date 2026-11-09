/**
 * The support agent and the one tool it can call.
 *
 * With `MOCK_MODE=1`, or no `OPENAI_API_KEY`, the agent runs on a
 * scripted stand-in model: it calls `get_policy` once, then writes a reply from
 * the tool result. The tool call, the tool result and both model turns still go
 * through the real agent loop, so Studio shows the same trace a real model makes.
 */

import { Agent, LM, tool } from '@agnt5/sdk';
import type { Context, GenerateRequest, GenerateResponse, LanguageModel } from '@agnt5/sdk';

import { POLICIES } from './data.js';

const SUPPORT_PROMPT = `You are a support agent. Call get_policy with the ticket's
category, then write a short, friendly reply (2-3 sentences) to the customer
that uses the policy text. Sign it "AGNT5 Support".`;

// TypeScript types are erased at runtime, so the tool's input schema is spelled out.
export const getPolicy = tool(
  'get_policy',
  {
    description: 'Look up the support policy for a ticket category.',
    inputSchema: {
      type: 'object',
      properties: {
        topic: { type: 'string', description: 'Ticket category: refund, bug or question' },
      },
      required: ['topic'],
    },
  },
  async (_ctx: Context, input: { topic: string }) => ({
    topic: input.topic,
    policy: POLICIES[input.topic] ?? POLICIES.question,
  }),
);

function field(prompt: string, name: string): string {
  const line = prompt.split('\n').find((l) => l.startsWith(`${name}:`));
  return line ? line.slice(name.length + 1).trim() : '';
}

/** Deterministic stand-in for an LLM: one get_policy call, then a reply. */
const scriptedSupportModel: LanguageModel = {
  async generate(request: GenerateRequest): Promise<GenerateResponse> {
    const prompt = request.messages[0].content;
    if (request.messages.length === 1) {
      return {
        text: '',
        toolCalls: [
          {
            id: 'call_policy',
            name: 'get_policy',
            arguments: JSON.stringify({ topic: field(prompt, 'Category') }),
          },
        ],
      };
    }
    const { policy } = JSON.parse(request.messages[request.messages.length - 1].content);
    return {
      text:
        `Hi ${field(prompt, 'Customer')}, thanks for reaching out about your ` +
        `${field(prompt, 'Category')} request. ${policy} — AGNT5 Support`,
    };
  },
};

/**
 * MOCK_MODE=1 forces the scripted model; unset, it's used only without an OpenAI key.
 * Not AGNT5_MOCK_MODE: `agnt5 dev` doesn't pass AGNT5_* variables from .env to the worker.
 */
export function mockMode(): boolean {
  const flag = process.env.MOCK_MODE;
  return flag !== undefined ? flag === '1' : !process.env.OPENAI_API_KEY;
}

/** Build the agent per call so a changed MOCK_MODE takes effect. */
export function buildSupportAgent(): Agent {
  const mock = mockMode();
  return new Agent({
    name: 'support_agent',
    model: mock ? scriptedSupportModel : LM.openai(),
    // The journal records this name, so the scripted model gets its own.
    modelName: mock ? 'mock-model' : 'openai/gpt-6-luna',
    temperature: 1, // gpt-6 accepts only its default temperature; the SDK would send 0.7
    instructions: SUPPORT_PROMPT,
    tools: [getPolicy],
    maxIterations: 4,
  });
}
