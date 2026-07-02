import { tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { _fetchWeatherData } from './functions.js';
import type { WeatherData } from './models.js';

/** Registered AGNT5 tool — exposed to agents and visible in Studio. */
export const getWeatherDataTool = tool(
  'get_weather_data_tool',
  {
    description: 'Fetch current weather data for a location (city name, coordinates, or postal code).',
    inputSchema: {
      type: 'object',
      properties: {
        location: { type: 'string', description: 'City name, coordinates, or postal code' },
      },
      required: ['location'],
    },
  },
  async (ctx: Context, args: { location: string }): Promise<WeatherData> => {
    ctx.logger.info(`Fetching weather data for ${args.location}`);
    const weather = await _fetchWeatherData(args.location);
    ctx.logger.info(`Received temperature ${weather.temperature_c}°C for ${args.location}`);
    return weather;
  },
);
