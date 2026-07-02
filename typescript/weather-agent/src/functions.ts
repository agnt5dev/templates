import { fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

import { config } from './config.js';
import type { WeatherData } from './models.js';

/** Fetch weather data from Open-Meteo (no API key required). */
export async function _fetchWeatherData(location: string): Promise<WeatherData> {
  // Step 1: Geocode location → coordinates
  const geoUrl = new URL(config.GEOCODING_API_URL);
  geoUrl.searchParams.set('name', location);
  geoUrl.searchParams.set('count', '1');

  const geoRes = await fetch(geoUrl.toString());
  if (!geoRes.ok) throw new Error(`Geocoding failed: ${geoRes.status}`);
  const geoData = await geoRes.json() as any;

  if (!geoData.results?.length) {
    throw new Error(`Location not found: ${location}`);
  }

  const place = geoData.results[0];
  const { latitude, longitude } = place;

  // Step 2: Fetch weather using coordinates
  const weatherUrl = new URL(config.WEATHER_API_URL);
  weatherUrl.searchParams.set('latitude', String(latitude));
  weatherUrl.searchParams.set('longitude', String(longitude));
  weatherUrl.searchParams.set('current', 'temperature_2m,relative_humidity_2m,wind_speed_10m');

  const weatherRes = await fetch(weatherUrl.toString());
  if (!weatherRes.ok) throw new Error(`Weather API failed: ${weatherRes.status}`);
  const weatherData = await weatherRes.json() as any;

  const current = weatherData.current;
  const temp_c: number = current.temperature_2m;

  return {
    location: place.name,
    latitude,
    longitude,
    temperature_c: temp_c,
    temperature_f: temp_c * 9 / 5 + 32,
    humidity: current.relative_humidity_2m,
    wind_kph: current.wind_speed_10m,
    country: place.country ?? undefined,
    region: place.admin1 ?? undefined,
  };
}

/** Registered AGNT5 function node — called via ctx.step() from the workflow. */
export const getWeatherData = fn('get_weather_data').run(
  async (ctx: Context, input: { location: string }): Promise<WeatherData> => {
    return _fetchWeatherData(input.location);
  },
);
