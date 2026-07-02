/** Weather information for a location. */
export interface WeatherData {
  location: string;
  latitude: number;
  longitude: number;
  temperature_c: number;
  temperature_f: number;
  humidity: number;
  wind_kph: number;
  country?: string;
  region?: string;
}
