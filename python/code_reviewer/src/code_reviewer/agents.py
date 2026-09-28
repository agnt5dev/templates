from agnt5 import Agent

from code_reviewer.tools import (
    pr_fetcher,
    jira_ticket_fetcher,
    linear_ticket_fetcher,
    detect_ticket_source,
)
from code_reviewer.prompts import (
    CODE_REVIEWER_PROMPT,
    CONTEXT_BUILDER_PROMPT,
)


context_builder_agent = Agent(
    name="context_builder",
    model="openai/gpt-4.1-mini",
    instructions=CONTEXT_BUILDER_PROMPT,
    tools=[
        pr_fetcher,
        jira_ticket_fetcher,
        linear_ticket_fetcher,
        detect_ticket_source,
    ],
    temperature=0.0,
    max_iterations=3,  # Reduced from 5 to limit conversation history
    max_tokens=4096
)


reviewer_agent = Agent(
    name="code_reviewer",
    model="openai/gpt-4.1-mini",
    instructions=CODE_REVIEWER_PROMPT,
    tools=[pr_fetcher, jira_ticket_fetcher, linear_ticket_fetcher],
    temperature=0.0,
    max_iterations=3,  # Reduced from 5 to limit conversation history
    max_tokens=4096
)


__all__ = [
    "context_builder_agent",
    "reviewer_agent",
]