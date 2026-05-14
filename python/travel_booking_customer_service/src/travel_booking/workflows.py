"""
Travel Booking Workflows

Provides workflows for orchestrating travel booking operations.
"""

import os
from typing import Dict

from agnt5 import WorkflowContext, workflow
from travel_booking.agents import travel_booking_agent
from travel_booking.entities import TravelBookingSession


@workflow
async def travel_booking_workflow(
    ctx: WorkflowContext,
    message: str,
    session_id: str = None,
) -> Dict:
    """
    Chat-based travel booking workflow using an AI agent.

    This workflow demonstrates:
    - Agent integration with travel booking tools
    - Multi-turn conversation support with persistent state
    - Single entity tracking all conversation, cart, bookings, and preferences
    - Every user/assistant message is appended to entity state
    - Flight and hotel search capabilities
    - Itinerary creation

    Args:
        message: User's travel booking request or query
        session_id: Session identifier for conversation tracking

    Returns:
        Dictionary with agent response and booking details
    """
    ctx.logger.info(f"Travel booking workflow - session: {session_id}, message: {message}")

    # Create or retrieve session entity for this user
    # For chat workflows, use a consistent key based on session_id
    # If no session_id provided, use "default" for testing
    # In production, you'd use user_id or a persistent session identifier
    if session_id:
        session_key = f"travel_booking:{session_id}"
    else:
        # Use a default key for testing - all conversations go to same session
        session_key = "travel_booking:default"

    ctx.logger.info(f"Using entity key: {session_key}")
    session = TravelBookingSession(key=session_key)

    # Add user message to conversation history
    await session.add_message("user", message)

    # Get conversation context
    messages = await session.get_messages()
    preferences = await session.get_preferences()
    search_count = await session.get_search_count()

    ctx.logger.info(f"Session state - messages: {len(messages)}, searches: {search_count}")
    ctx.logger.info(f"Current preferences: {preferences}")

    # Check if API keys are available
    if not os.getenv("OPENAI_API_KEY"):
        ctx.logger.warning("OPENAI_API_KEY not set, cannot run agent")
        error_response = "OPENAI_API_KEY not configured"
        await session.add_message("assistant", error_response)
        return {
            "status": "error",
            "message": error_response,
            "session_id": session_id,
        }

    if not os.getenv("SERPAPI_KEY"):
        ctx.logger.warning("SERPAPI_KEY not set, cannot search flights/hotels")
        error_response = "SERPAPI_KEY not configured"
        await session.add_message("assistant", error_response)
        return {
            "status": "error",
            "message": error_response,
            "session_id": session_id,
        }

    # Prepare context-aware input for the agent
    # Include recent conversation history to help agent understand context
    if len(messages) > 1:
        # Build conversation context from entity history
        context_str = "Previous conversation:\n"
        for msg in messages[-5:]:  # Last 5 messages for context
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context_str += f"{role.capitalize()}: {content}\n"

        agent_input = f"{context_str}\nCurrent message: {message}"
        ctx.logger.info(f"Providing agent with {len(messages)} messages of context")
    else:
        agent_input = message
        ctx.logger.info("First message - no prior context")

    # Run the travel booking agent with conversation context
    ctx.logger.info("Starting travel booking agent")
    result = await travel_booking_agent.run(agent_input, context=ctx)

    ctx.logger.info(f"Agent completed with output: {result.output[:100]}...")

    # Add agent response to conversation history
    await session.add_message("assistant", result.output)

    # If tools were used, record the search
    if result.tool_calls:
        # Extract search parameters from tool calls if available
        search_params = {
            "tools_used": [tc["name"] for tc in result.tool_calls],
            "timestamp": messages[-1]["timestamp"] if messages else None
        }
        await session.record_search(search_params)

    # Get updated session summary
    updated_messages = await session.get_messages()
    updated_search_count = await session.get_search_count()

    return {
        "status": "completed",
        "session_id": session_id,
        "output": result.output,
        "tool_calls_made": len(result.tool_calls),
        "tools_used": [tc["name"] for tc in result.tool_calls],
        "conversation_length": len(updated_messages),
        "total_searches": updated_search_count,
    }





__all__ = [
    "travel_booking_workflow"
]
