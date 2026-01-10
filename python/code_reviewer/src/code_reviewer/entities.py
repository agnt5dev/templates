from typing import Any, Dict

from agnt5 import Entity


class CodeReviewSession(Entity):
    """
    Persistent entity for managing code review session state.

    This entity persists state across workflow executions, including:
    - PR and ticket URLs
    - Current workflow status and step
    - Context and review outputs
    - Tool call counts
    - Final synthesized report
    """

    async def set_initial_state(self, pr_url: str, ticket_url: str) -> None:
        """Set initial state for a new code review session."""
        self.state.set("pr_url", pr_url)
        self.state.set("ticket_url", ticket_url)
        self.state.set("status", "in_progress")
        self.state.set("current_step", "initialized")

    async def set_context_building(self) -> None:
        """Mark that context building step has started."""
        self.state.set("current_step", "context_building")

    async def set_context_result(self, output: str, tool_calls: int) -> None:
        """Store context building results."""
        self.state.set("context_output", output)
        self.state.set("context_tool_calls", tool_calls)

    async def set_code_review(self) -> None:
        """Mark that code review step has started."""
        self.state.set("current_step", "code_review")

    async def set_review_result(self, output: str, tool_calls: int) -> None:
        """Store code review results."""
        self.state.set("review_output", output)
        self.state.set("review_tool_calls", tool_calls)

    async def set_synthesizing(self) -> None:
        """Mark that synthesis step has started."""
        self.state.set("current_step", "synthesizing")

    async def set_synthesized_report(self, report: str) -> None:
        """Store synthesized report."""
        self.state.set("synthesized_report", report)

    async def set_completed(self) -> None:
        """Mark the workflow as completed."""
        self.state.set("status", "completed")
        self.state.set("current_step", "done")

    async def get_state(self) -> Dict[str, Any]:
        """Get the complete current state."""
        return {
            "pr_url": self.state.get("pr_url"),
            "ticket_url": self.state.get("ticket_url"),
            "status": self.state.get("status"),
            "current_step": self.state.get("current_step"),
            "context_output": self.state.get("context_output"),
            "context_tool_calls": self.state.get("context_tool_calls"),
            "review_output": self.state.get("review_output"),
            "review_tool_calls": self.state.get("review_tool_calls"),
            "synthesized_report": self.state.get("synthesized_report"),
        }


__all__ = [
    "CodeReviewSession",
]
