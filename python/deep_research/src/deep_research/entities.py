"""
Deep Research Entities for State Management

Simplified entity that stores only essential research artifacts.
All helper methods removed - use direct state access instead.
"""

from agnt5 import Entity


class ResearchSession(Entity):
    """
    Entity for storing research artifacts.

    Stores only the essential data produced during research:
    - Original topic
    - Research plan (subtopics and strategy)
    - Research findings (accumulated data)
    - Final report (synthesized output)
    - Quality assessment (evaluation results)

    Use entity methods to access state:
        topic = await session.get_topic()
        await session.set_topic("new topic")
    """

    _state_schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic or question",
                "default": ""
            },
            "research_plan": {
                "type": ["string", "null"],
                "description": "Research plan with subtopics and strategy",
                "default": None
            },
            "research_findings": {
                "type": "string",
                "description": "Accumulated research findings",
                "default": ""
            },
            "final_report": {
                "type": ["string", "null"],
                "description": "Final synthesized research report",
                "default": None
            },
            "quality_assessment": {
                "type": ["string", "null"],
                "description": "Quality evaluation results",
                "default": None
            }
        },
        "description": "Research session artifacts"
    }

    async def get_topic(self) -> str:
        """Get the current research topic."""
        return self.state.get("topic", "")

    async def set_topic(self, topic: str) -> None:
        """Set the research topic."""
        self.state.set("topic", topic)

    async def get_research_plan(self) -> str | None:
        """Get the research plan."""
        return self.state.get("research_plan")

    async def set_research_plan(self, plan: str) -> None:
        """Set the research plan."""
        self.state.set("research_plan", plan)

    async def get_research_findings(self) -> str:
        """Get the research findings."""
        return self.state.get("research_findings", "")

    async def set_research_findings(self, findings: str) -> None:
        """Set the research findings."""
        self.state.set("research_findings", findings)

    async def get_final_report(self) -> str | None:
        """Get the final report."""
        return self.state.get("final_report")

    async def set_final_report(self, report: str) -> None:
        """Set the final report."""
        self.state.set("final_report", report)

    async def get_quality_assessment(self) -> str | None:
        """Get the quality assessment."""
        return self.state.get("quality_assessment")

    async def set_quality_assessment(self, assessment: str) -> None:
        """Set the quality assessment."""
        self.state.set("quality_assessment", assessment)


__all__ = ["ResearchSession"]