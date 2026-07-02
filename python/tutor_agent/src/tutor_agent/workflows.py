"""
Tutor Workflows for Educational Interactions

Workflows that orchestrate tutor agents with handoff-based routing for educational interactions.
This demonstrates the agent handoff pattern where a triage agent delegates to specialized tutors.
"""

from agnt5 import workflow, WorkflowContext
from tutor_agent.agents import tutor_agent


@workflow
async def tutor_chat_workflow(ctx: WorkflowContext, message: str) -> dict:
    """
    Simple chat-based tutor workflow.

    Demonstrates:
    - Agent handoff pattern (triage → history/math specialist)
    - Subject detection and routing

    Args:
        message: Student's message/question
    """
    ctx.logger.info(f"Tutor chat workflow - message: {message}")

    try:
        result = await tutor_agent.run(message, context=ctx)
        response = result.output
    except Exception as e:
        ctx.logger.error(f"Error running tutor agent: {e}")
        response = f"I apologize, but I'm having trouble processing your question right now. Could you please rephrase: {message}"

    return {
        "output": response,
    }


__all__ = ["tutor_chat_workflow"]
