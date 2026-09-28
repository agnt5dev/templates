import { Agent, LM } from '@agnt5/sdk';

import { getWeatherDataTool } from './tools.js';

export function createWeatherAgent(): Agent {
  return new Agent({
    name: 'weather-agent',
    model: LM.openai(),
    modelName: 'openai/gpt-6-luna',
    temperature: 1, // gpt-6 accepts only its default temperature; the SDK would send 0.7
    instructions: 'Get weather data for a location, if a generic question is posed, just answer the question with your knowledge',
    tools: [getWeatherDataTool],
  });
}
