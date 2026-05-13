"""
HITL Deep Research - AGNT5 Template

A Human-in-the-Loop deep research workflow that:
1. Scopes and plans research based on user topic
2. Pauses for human approval of the plan
3. Conducts systematic research using web/Wikipedia tools
4. Synthesizes findings into comprehensive reports
"""

from .agents import research_agent, scoping_agent, writing_agent
from .tools import (
    analyze_research_findings_tool,
    fetch_webpage_tool,
    wikipedia_search_tool,
)
from .workflows import (
    clarify_and_plan,
    conduct_research,
    deep_research_workflow,
    write_report,
)

__all__ = [
    # Workflow
    "deep_research_workflow",
    # Functions
    "clarify_and_plan",
    "conduct_research",
    "write_report",
    # Agents
    "scoping_agent",
    "research_agent",
    "writing_agent",
    # Tools
    "fetch_webpage_tool",
    "wikipedia_search_tool",
    "analyze_research_findings_tool",
]
