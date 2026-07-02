"""
Travel Booking Workflows

Provides workflows for orchestrating travel booking operations.
"""

from agnt5 import WorkflowContext, workflow
from travel_booking.agents import travel_booking_agent


@workflow
async def travel_booking_workflow(
    ctx: WorkflowContext,
    message: str,
) -> dict:
    """
    Chat-based travel booking workflow using an AI agent.

    Args:
        message: User's travel booking request or query

    Returns:
        Dictionary with agent response
    """
    ctx.logger.info(f"Travel booking workflow - message: {message[:100]}...")

    result = await travel_booking_agent.run(message, context=ctx)

    ctx.logger.info("Travel booking agent completed")

    return {
        "status": "completed",
        "output": result.output,
    }


__all__ = ["travel_booking_workflow"]
