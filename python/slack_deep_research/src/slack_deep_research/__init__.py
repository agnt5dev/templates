"""
Slack Deep Research - AGNT5 Template

A Slack bot that:
1. Claims each Slack mention so a repeated delivery doesn't start a second run
2. Plans the research and posts the plan with Approve / Reject buttons
3. Pauses until someone clicks, then researches the approved plan
4. Posts a sourced report to the thread, once
"""

from .agents import research_agent, scoping_agent, writing_agent
from .approval import _claim_event, _post_report, _request_plan_approval
from .functions import _conduct_research, _plan_research, _write_report
from .tools import fetch_webpage_tool, wikipedia_search_tool
from .workflows import slack_deep_research

__all__ = [
    # Workflow
    "slack_deep_research",
    # Functions (steps)
    "_claim_event",
    "_plan_research",
    "_request_plan_approval",
    "_conduct_research",
    "_write_report",
    "_post_report",
    # Agents
    "scoping_agent",
    "research_agent",
    "writing_agent",
    # Tools
    "fetch_webpage_tool",
    "wikipedia_search_tool",
]
