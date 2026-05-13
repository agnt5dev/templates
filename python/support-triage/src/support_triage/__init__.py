"""
Support Triage - AGNT5 Quickstart

Two workflows demonstrating different patterns:

1. support_triage (chat=False) - Structured Pipeline
   - Checkpointing (durable execution)
   - Human-in-the-loop (durable pauses)
   - Exactly-once semantics

2. support_chat (chat=True) - Interactive Chat
   - Multi-turn conversation with AI agent
   - Agent uses tools to search KB and fetch customer info
"""

from .agent import support_agent
from .functions import analyze_ticket, post_reply
from .tools import (
    CUSTOMER_DB,
    KNOWLEDGE_BASE,
    TOOL_FAILURE_RATE,
    categorize_ticket_tool,
    fetch_customer_info_tool,
    search_kb_tool,
)
from .workflows import my_scheduled_workflow, support_triage

__all__ = [
    # Workflows
    "support_triage",
    "my_scheduled_workflow",
    # Functions
    "analyze_ticket",
    "post_reply",
    # Agent
    "support_agent",
    # Tools
    "search_kb_tool",
    "fetch_customer_info_tool",
    "categorize_ticket_tool",
    # Constants (for mock mode)
    "KNOWLEDGE_BASE",
    "CUSTOMER_DB",
    "TOOL_FAILURE_RATE",
]
