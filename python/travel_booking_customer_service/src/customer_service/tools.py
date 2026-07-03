"""
Travel Booking Tools for Flight and Hotel Search

Provides tools for searching flights, hotels, and creating itineraries using SerpAPI.
"""

import os
import requests
from typing import Optional

from agnt5 import Context, tool


@tool(auto_schema=True)
async def search_flights(
    ctx: Context,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
) -> dict:
    """Search for flights using SerpAPI Google Flights.

    Args:
        departure_id: Departure airport code (e.g., JFK, LAX)
        arrival_id: Arrival airport code (e.g., LHR, CDG)
        outbound_date: Departure date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format (optional for one-way)
        adults: Number of adult passengers

    Returns:
        Dictionary with flight search results
    """
    ctx.logger.info(
        f"Searching flights: {departure_id} -> {arrival_id} on {outbound_date}"
    )

    serpapi_key = os.getenv("SERPAPI_KEY")
    if not serpapi_key:
        ctx.logger.error("SERPAPI_KEY not set")
        return {"error": "SERPAPI_KEY not configured", "status": "failed"}

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "currency": "USD",
        "hl": "en",
        "adults": adults,
        "api_key": serpapi_key,
    }

    if return_date:
        params["return_date"] = return_date
        params["type"] = "1"  # Round trip
    else:
        params["type"] = "2"  # One way

    try:
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()

        # Extract relevant flight information
        flights = []
        if "best_flights" in data:
            for flight in data["best_flights"][:3]:  # Top 3 flights
                flights.append(
                    {
                        "price": flight.get("price"),
                        "airline": flight["flights"][0].get("airline"),
                        "departure_time": flight["flights"][0]
                        .get("departure_airport", {})
                        .get("time"),
                        "arrival_time": flight["flights"][0]
                        .get("arrival_airport", {})
                        .get("time"),
                        "duration": flight["flights"][0].get("duration"),
                        "flight_number": flight["flights"][0].get("flight_number"),
                    }
                )

        ctx.logger.info(f"Found {len(flights)} flight options")
        return {"flights": flights, "status": "success"}

    except Exception as e:
        ctx.logger.error(f"Flight search failed: {str(e)}")
        return {"error": str(e), "status": "failed"}


@tool(auto_schema=True)
async def search_hotels(
    ctx: Context,
    location: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 1,
) -> dict:
    """Search for hotels using SerpAPI Google Hotels.

    Args:
        location: City or location name (e.g., 'Paris, France', 'New York')
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        adults: Number of guests

    Returns:
        Dictionary with hotel search results
    """
    ctx.logger.info(f"Searching hotels in {location}: {check_in_date} to {check_out_date}")

    serpapi_key = os.getenv("SERPAPI_KEY")
    if not serpapi_key:
        ctx.logger.error("SERPAPI_KEY not set")
        return {"error": "SERPAPI_KEY not configured", "status": "failed"}

    params = {
        "engine": "google_hotels",
        "q": location,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": adults,
        "currency": "USD",
        "gl": "us",
        "hl": "en",
        "api_key": serpapi_key,
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()

        # Extract relevant hotel information
        hotels = []
        if "properties" in data:
            for hotel in data["properties"][:3]:  # Top 3 hotels
                hotels.append(
                    {
                        "name": hotel.get("name"),
                        "price": hotel.get("rate_per_night", {}).get("lowest"),
                        "rating": hotel.get("overall_rating"),
                        "reviews": hotel.get("reviews"),
                        "description": hotel.get("description"),
                        "amenities": hotel.get("amenities", [])[:5],  # First 5 amenities
                    }
                )

        ctx.logger.info(f"Found {len(hotels)} hotel options")
        return {"hotels": hotels, "status": "success"}

    except Exception as e:
        ctx.logger.error(f"Hotel search failed: {str(e)}")
        return {"error": str(e), "status": "failed"}


@tool(auto_schema=True)
async def create_itinerary(
    ctx: Context,
    destination: str,
    travel_dates: str,
    preferences: str = "",
) -> dict:
    """Create a travel itinerary framework.

    Args:
        destination: Travel destination
        travel_dates: Travel date range
        preferences: Any special preferences or requirements

    Returns:
        Dictionary with itinerary information
    """
    ctx.logger.info(f"Creating itinerary for {destination} ({travel_dates})")

    itinerary = {
        "destination": destination,
        "dates": travel_dates,
        "preferences": preferences,
        "status": "created",
        "message": "Itinerary framework created. Please search for flights and hotels to complete it.",
    }

    return itinerary


__all__ = [
    "search_flights",
    "search_hotels",
    "create_itinerary",
]
