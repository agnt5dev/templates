"""
Travel Booking Entities

Entity for managing persistent state in travel booking workflows.
"""

from typing import Dict, List, Optional
from agnt5 import Entity


class TravelBookingSession(Entity):
    """
    Manages complete travel booking session state.

    Single entity that tracks all aspects of a travel booking session:
    - Conversation history (every user/assistant message appended)
    - User preferences
    - Shopping cart (items being considered)
    - Confirmed bookings
    - Search history

    State:
        messages (list): Conversation history with user and assistant
        preferences (dict): User's travel preferences (dates, locations, budget)
        cart_items (dict): Items in shopping cart (flights/hotels being considered)
        bookings (list): Confirmed bookings with details
        search_history (list): History of searches performed
        trip_details (dict): Trip name, dates, status
    """

    _state_schema = {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"]},
                        "content": {"type": "string"},
                        "timestamp": {"type": "string"}
                    }
                },
                "default": [],
                "description": "Complete conversation history"
            },
            "preferences": {
                "type": "object",
                "default": {},
                "description": "User's travel preferences"
            },
            "cart_items": {
                "type": "object",
                "default": {},
                "description": "Items in shopping cart keyed by item_id"
            },
            "bookings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "booking_id": {"type": "string"},
                        "type": {"type": "string"},
                        "details": {"type": "object"},
                        "cost": {"type": "number"},
                        "confirmation_number": {"type": "string"},
                        "booked_at": {"type": "string"}
                    }
                },
                "default": [],
                "description": "Confirmed bookings"
            },
            "search_history": {
                "type": "array",
                "items": {"type": "object"},
                "default": [],
                "description": "History of searches performed"
            },
            "trip_details": {
                "type": "object",
                "properties": {
                    "trip_name": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "status": {"type": "string", "enum": ["planning", "booked", "completed", "cancelled"]},
                    "total_cost": {"type": "number"}
                },
                "default": {
                    "trip_name": "",
                    "start_date": "",
                    "end_date": "",
                    "status": "planning",
                    "total_cost": 0.0
                },
                "description": "Overall trip information"
            }
        },
        "description": "Complete travel booking session state"
    }

    # ==================== Conversation Methods ====================

    async def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.
        Every user/assistant interaction is appended here.

        Args:
            role: Either 'user' or 'assistant'
            content: Message content
        """
        import datetime

        messages = self.state.get("messages", [])
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        self.state.set("messages", messages)

    async def get_messages(self) -> List[Dict]:
        """Get all conversation messages."""
        return self.state.get("messages", [])

    async def get_message_count(self) -> int:
        """Get total number of messages in conversation."""
        messages = self.state.get("messages", [])
        return len(messages)

    # ==================== Preferences Methods ====================

    async def update_preferences(self, preferences: Dict) -> None:
        """
        Update user's travel preferences.

        Args:
            preferences: Dictionary of preference updates (merges with existing)
        """
        current_prefs = self.state.get("preferences", {})
        current_prefs.update(preferences)
        self.state.set("preferences", current_prefs)

    async def get_preferences(self) -> Dict:
        """Get current travel preferences."""
        return self.state.get("preferences", {})

    # ==================== Cart Methods ====================

    async def add_to_cart(
        self,
        item_id: str,
        item_type: str,
        details: Dict,
        cost: float
    ) -> Dict:
        """
        Add an item to the shopping cart.

        Args:
            item_id: Unique identifier for the item
            item_type: Type of item ('flight', 'hotel', 'activity')
            details: Item details
            cost: Cost of the item

        Returns:
            Current cart summary
        """
        cart_items = self.state.get("cart_items", {})
        cart_items[item_id] = {
            "type": item_type,
            "details": details,
            "cost": cost
        }
        self.state.set("cart_items", cart_items)
        return await self.get_cart_summary()

    async def remove_from_cart(self, item_id: str) -> Dict:
        """
        Remove an item from the cart.

        Args:
            item_id: ID of item to remove

        Returns:
            Updated cart summary
        """
        cart_items = self.state.get("cart_items", {})
        if item_id in cart_items:
            del cart_items[item_id]
            self.state.set("cart_items", cart_items)
        return await self.get_cart_summary()

    async def get_cart_summary(self) -> Dict:
        """
        Get shopping cart summary.

        Returns:
            Dictionary with items, total_cost, and item_count
        """
        cart_items = self.state.get("cart_items", {})
        total_cost = sum(item["cost"] for item in cart_items.values())
        return {
            "items": cart_items,
            "total_cost": total_cost,
            "item_count": len(cart_items)
        }

    async def clear_cart(self) -> None:
        """Clear all items from the cart."""
        self.state.set("cart_items", {})

    # ==================== Booking Methods ====================

    async def add_booking(
        self,
        booking_id: str,
        booking_type: str,
        details: Dict,
        cost: float,
        confirmation_number: str
    ) -> None:
        """
        Add a confirmed booking.

        Args:
            booking_id: Unique booking identifier
            booking_type: Type of booking (flight, hotel, activity)
            details: Booking details
            cost: Booking cost
            confirmation_number: Confirmation number from provider
        """
        import datetime

        bookings = self.state.get("bookings", [])
        bookings.append({
            "booking_id": booking_id,
            "type": booking_type,
            "details": details,
            "cost": cost,
            "confirmation_number": confirmation_number,
            "booked_at": datetime.datetime.utcnow().isoformat()
        })
        self.state.set("bookings", bookings)

        # Update trip total cost
        trip_details = self.state.get("trip_details", {
            "trip_name": "",
            "start_date": "",
            "end_date": "",
            "status": "planning",
            "total_cost": 0.0
        })
        trip_details["total_cost"] = trip_details.get("total_cost", 0.0) + cost
        self.state.set("trip_details", trip_details)

    async def get_bookings(self) -> List[Dict]:
        """Get all confirmed bookings."""
        return self.state.get("bookings", [])

    # ==================== Search History Methods ====================

    async def record_search(self, search_params: Dict) -> int:
        """
        Record a search in history.

        Args:
            search_params: Search parameters used

        Returns:
            Total number of searches performed
        """
        import datetime

        search_history = self.state.get("search_history", [])
        search_history.append({
            **search_params,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        self.state.set("search_history", search_history)
        return len(search_history)

    async def get_search_history(self) -> List[Dict]:
        """Get all search history."""
        return self.state.get("search_history", [])

    async def get_search_count(self) -> int:
        """Get total number of searches performed."""
        search_history = self.state.get("search_history", [])
        return len(search_history)

    # ==================== Trip Details Methods ====================

    async def set_trip_details(
        self,
        trip_name: str = None,
        start_date: str = None,
        end_date: str = None,
        status: str = None
    ) -> None:
        """
        Set or update trip details.

        Args:
            trip_name: Name/description of trip
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            status: Trip status (planning, booked, completed, cancelled)
        """
        trip_details = self.state.get("trip_details", {
            "trip_name": "",
            "start_date": "",
            "end_date": "",
            "status": "planning",
            "total_cost": 0.0
        })

        if trip_name is not None:
            trip_details["trip_name"] = trip_name
        if start_date is not None:
            trip_details["start_date"] = start_date
        if end_date is not None:
            trip_details["end_date"] = end_date
        if status is not None:
            trip_details["status"] = status

        self.state.set("trip_details", trip_details)

    async def get_trip_details(self) -> Dict:
        """Get current trip details."""
        return self.state.get("trip_details", {
            "trip_name": "",
            "start_date": "",
            "end_date": "",
            "status": "planning",
            "total_cost": 0.0
        })

    # ==================== Summary Methods ====================

    async def get_session_summary(self) -> Dict:
        """
        Get complete session summary.

        Returns:
            Dictionary with all session information
        """
        messages = self.state.get("messages", [])
        cart_items = self.state.get("cart_items", {})
        bookings = self.state.get("bookings", [])
        search_history = self.state.get("search_history", [])
        trip_details = self.state.get("trip_details", {})

        return {
            "conversation": {
                "message_count": len(messages),
                "latest_messages": messages[-5:] if len(messages) > 5 else messages
            },
            "cart": {
                "item_count": len(cart_items),
                "total_cost": sum(item["cost"] for item in cart_items.values())
            },
            "bookings": {
                "booking_count": len(bookings),
                "bookings": bookings
            },
            "searches": {
                "search_count": len(search_history)
            },
            "trip": trip_details
        }

    async def clear_session(self) -> None:
        """Clear all session data."""
        self.state.clear()


__all__ = [
    "TravelBookingSession",
]
