"""
AGNT5 Tutor Agent

Multi-subject educational assistant with agent handoffs for history and math tutoring.
Conversation history is maintained across turns using session state.
"""

from tutor_agent.agents import tutor_agent, history_tutor_agent, math_tutor_agent
from tutor_agent.workflows import tutor_chat_workflow

__version__ = "1.0.0"

__all__ = [
    "tutor_agent",
    "history_tutor_agent",
    "math_tutor_agent",
    "tutor_chat_workflow",
]
