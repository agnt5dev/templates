"""
HITL Deep Research - AGNT5 Template

A Human-in-the-Loop deep research workflow that:
1. Scopes and plans research based on user topic
2. Pauses for human approval of the plan
3. Researches each subtopic in parallel using web/Wikipedia tools
4. Synthesizes findings into comprehensive reports
"""

from .agents import research_agent, scoping_agent, writing_agent
from .functions import _plan_research, _conduct_research, _write_report
from .tools import (
    fetch_webpage_tool,
    wikipedia_search_tool,
)
from .workflows import deep_research_workflow

__all__ = [
    # Workflow
    "deep_research_workflow",
    # Functions
    "_plan_research",
    "_conduct_research",
    "_write_report",
    # Agents
    "scoping_agent",
    "research_agent",
    "writing_agent",
    # Tools
    "fetch_webpage_tool",
    "wikipedia_search_tool",
]
