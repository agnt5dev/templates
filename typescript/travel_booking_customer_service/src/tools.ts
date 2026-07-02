/**
 * Travel Booking Tools for Flight and Hotel Search
 *
 * Provides tools for searching flights, hotels, and creating itineraries using SerpAPI.
 */

import { tool } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';

export const searchFlights = tool(
  'search_flights',
  {
    description: 'Search for flights using SerpAPI Google Flights',
    inputSchema: {
      type: 'object',
      properties: {
        departure_id: { type: 'string', description: 'Departure airport code (e.g., JFK, LAX)' },
        arrival_id: { type: 'string', description: 'Arrival airport code (e.g., LHR, CDG)' },
        outbound_date: { type: 'string', description: 'Departure date in YYYY-MM-DD format' },
        return_date: { type: 'string', description: 'Return date in YYYY-MM-DD format (optional for one-way)' },
        adults: { type: 'number', description: 'Number of adult passengers' },
      },
      required: ['departure_id', 'arrival_id', 'outbound_date'],
    },
  },
  async (
    ctx: Context,
    args: {
      departure_id: string;
      arrival_id: string;
      outbound_date: string;
      return_date?: string;
      adults?: number;
    },
  ) => {
    const { departure_id, arrival_id, outbound_date, return_date, adults = 1 } = args;
    ctx.logger.info(`Searching flights: ${departure_id} -> ${arrival_id} on ${outbound_date}`);

    const serpApiKey = process.env.SERPAPI_KEY;
    if (!serpApiKey) {
      ctx.logger.error('SERPAPI_KEY not set');
      return JSON.stringify({ error: 'SERPAPI_KEY not configured', status: 'failed' });
    }

    const params = new URLSearchParams({
      engine: 'google_flights',
      departure_id,
      arrival_id,
      outbound_date,
      currency: 'USD',
      hl: 'en',
      adults: String(adults),
      api_key: serpApiKey,
      type: return_date ? '1' : '2', // 1 = round trip, 2 = one way
    });

    if (return_date) {
      params.set('return_date', return_date);
    }

    try {
      const response = await fetch(`https://serpapi.com/search?${params}`);
      const data = (await response.json()) as Record<string, any>;

      const flights: Array<Record<string, any>> = [];
      if (Array.isArray(data.best_flights)) {
        for (const flight of data.best_flights.slice(0, 3)) {
          const leg = flight.flights?.[0] ?? {};
          flights.push({
            price: flight.price,
            airline: leg.airline,
            departure_time: leg.departure_airport?.time,
            arrival_time: leg.arrival_airport?.time,
            duration: leg.duration,
            flight_number: leg.flight_number,
          });
        }
      }

      ctx.logger.info(`Found ${flights.length} flight options`);
      return JSON.stringify({ flights, status: 'success' });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ctx.logger.error(`Flight search failed: ${message}`);
      return JSON.stringify({ error: message, status: 'failed' });
    }
  },
);

export const searchHotels = tool(
  'search_hotels',
  {
    description: 'Search for hotels using SerpAPI Google Hotels',
    inputSchema: {
      type: 'object',
      properties: {
        location: { type: 'string', description: "City or location name (e.g., 'Paris, France')" },
        check_in_date: { type: 'string', description: 'Check-in date in YYYY-MM-DD format' },
        check_out_date: { type: 'string', description: 'Check-out date in YYYY-MM-DD format' },
        adults: { type: 'number', description: 'Number of guests' },
      },
      required: ['location', 'check_in_date', 'check_out_date'],
    },
  },
  async (
    ctx: Context,
    args: {
      location: string;
      check_in_date: string;
      check_out_date: string;
      adults?: number;
    },
  ) => {
    const { location, check_in_date, check_out_date, adults = 1 } = args;
    ctx.logger.info(`Searching hotels in ${location}: ${check_in_date} to ${check_out_date}`);

    const serpApiKey = process.env.SERPAPI_KEY;
    if (!serpApiKey) {
      ctx.logger.error('SERPAPI_KEY not set');
      return JSON.stringify({ error: 'SERPAPI_KEY not configured', status: 'failed' });
    }

    const params = new URLSearchParams({
      engine: 'google_hotels',
      q: location,
      check_in_date,
      check_out_date,
      adults: String(adults),
      currency: 'USD',
      gl: 'us',
      hl: 'en',
      api_key: serpApiKey,
    });

    try {
      const response = await fetch(`https://serpapi.com/search?${params}`);
      const data = (await response.json()) as Record<string, any>;

      const hotels: Array<Record<string, any>> = [];
      if (Array.isArray(data.properties)) {
        for (const hotel of data.properties.slice(0, 3)) {
          hotels.push({
            name: hotel.name,
            price: hotel.rate_per_night?.lowest,
            rating: hotel.overall_rating,
            reviews: hotel.reviews,
            description: hotel.description,
            amenities: (hotel.amenities ?? []).slice(0, 5),
          });
        }
      }

      ctx.logger.info(`Found ${hotels.length} hotel options`);
      return JSON.stringify({ hotels, status: 'success' });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      ctx.logger.error(`Hotel search failed: ${message}`);
      return JSON.stringify({ error: message, status: 'failed' });
    }
  },
);

export const createItinerary = tool(
  'create_itinerary',
  {
    description: 'Create a travel itinerary framework for the given destination and dates',
    inputSchema: {
      type: 'object',
      properties: {
        destination: { type: 'string', description: 'Travel destination' },
        travel_dates: { type: 'string', description: 'Travel date range' },
        preferences: { type: 'string', description: 'Any special preferences or requirements' },
      },
      required: ['destination', 'travel_dates'],
    },
  },
  async (
    ctx: Context,
    args: {
      destination: string;
      travel_dates: string;
      preferences?: string;
    },
  ) => {
    const { destination, travel_dates, preferences = '' } = args;
    ctx.logger.info(`Creating itinerary for ${destination} (${travel_dates})`);

    const itinerary = {
      destination,
      dates: travel_dates,
      preferences,
      status: 'created',
      message: 'Itinerary framework created. Please search for flights and hotels to complete it.',
    };

    return JSON.stringify(itinerary);
  },
);
