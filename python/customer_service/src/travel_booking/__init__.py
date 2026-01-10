"""
AGNT5 Travel Booking Service

This package provides comprehensive travel booking components using AGNT5 platform:
- Tools: Flight search, hotel search, itinerary creation
- Agents: AI-powered travel booking assistant
- Workflows: Chat-based and direct search workflows
- Entities: Travel session, booking cart, trip itinerary
"""

# Import tools
from travel_booking.tools import (
    search_flights,
    search_hotels,
    create_itinerary,
)

# Import agents
from travel_booking.agents import (
    travel_booking_agent,
)

# Import workflows
from travel_booking.workflows import (
    travel_booking_workflow,
)

# Import entities
from travel_booking.entities import (
    TravelBookingSession,
)

__all__ = [
    # Tools
    "search_flights",
    "search_hotels",
    "create_itinerary",
    # Agents
    "travel_booking_agent",
    # Workflows
    "travel_booking_workflow",
    # Entities
    "TravelBookingSession",
]

__version__ = "1.0.0"
