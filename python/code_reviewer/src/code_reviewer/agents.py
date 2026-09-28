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
    model="openai/gpt-6-luna",
    temperature=None,  # gpt-6 rejects any temperature; None stops the SDK sending its 0.7 default
    instructions=CONTEXT_BUILDER_PROMPT,
    tools=[
        pr_fetcher,
        jira_ticket_fetcher,
        linear_ticket_fetcher,
        detect_ticket_source,
    ],
    max_iterations=3,  # Reduced from 5 to limit conversation history
    max_tokens=4096
)


reviewer_agent = Agent(
    name="code_reviewer",
    model="openai/gpt-6-luna",
    temperature=None,  # gpt-6 rejects any temperature; None stops the SDK sending its 0.7 default
    instructions=CODE_REVIEWER_PROMPT,
    tools=[pr_fetcher, jira_ticket_fetcher, linear_ticket_fetcher],
    max_iterations=3,  # Reduced from 5 to limit conversation history
    max_tokens=4096
)


__all__ = [
    "context_builder_agent",
    "reviewer_agent",
]