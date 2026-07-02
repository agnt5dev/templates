import { workflow } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { getWeatherData } from './functions.js';
import { createWeatherAgent } from './agents.js';
import type { WeatherData } from './models.js';

/** Fetch weather data for a location. */
export const getWeather = workflow(
  'get_weather',
  async (ctx: Context, input: { location: string }): Promise<WeatherData> => {
    const weather = await ctx.step('get_weather_data', () =>
      getWeatherData(ctx, { location: input.location }),
    );

    ctx.logger.info(
      `Weather retrieved: ${weather.location} - ${weather.temperature_c}°C`,
    );

    return weather;
  },
);

/** Interactive chat workflow for weather queries (multi-turn). */
export const getWeatherInteractive = workflow(
  'get_weather_interactive',
  async (ctx: Context, input: { message: string }): Promise<string> => {
    const agent = createWeatherAgent();
    const result = await agent.run(input.message, ctx);

    ctx.logger.info(`Weather agent response: ${result.output.slice(0, 100)}...`);

    return result.output;
  },
);
