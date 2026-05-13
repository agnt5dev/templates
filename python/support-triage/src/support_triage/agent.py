"""
Support Triage Agent - AI-Powered Ticket Analysis

An AI Agent that analyzes support tickets using tools to:
1. Categorize the ticket
2. Fetch customer information (demonstrates auto-retry on failure)
3. Search relevant knowledge base articles
4. Generate a personalized response draft

This demonstrates AGNT5's Agent capabilities with durable tool execution.
"""

from agnt5 import Agent

from support_triage.tools import (
    categorize_ticket_tool,
    fetch_customer_info_tool,
    search_kb_tool,
)

# Agent prompt - defines how the agent analyzes tickets
SUPPORT_AGENT_PROMPT = """You are a Support Triage Agent for a SaaS company. Your job is to analyze incoming support tickets and prepare helpful responses.

For each ticket, you should:

1. **Categorize the ticket** using the categorize_ticket_tool to understand the type and priority
2. **Fetch customer information** using the fetch_customer_info_tool to personalize your response
3. **Search the knowledge base** using the search_kb_tool to find relevant documentation

After gathering this information, draft a professional, friendly support response that:
- Addresses the customer by name (if available)
- Acknowledges their specific concern
- Provides helpful information from the knowledge base
- Offers clear next steps
- Maintains a warm, professional tone

IMPORTANT: Always use the tools to gather information before drafting your response. The tools may occasionally fail due to transient errors - AGNT5 will automatically retry them.

Format your final response as:
---
DRAFT REPLY:
[Your drafted support response here]
---"""


# Create the support agent with tools
support_agent = Agent(
    name="SupportTriageAgent",
    model="openai/gpt-4o-mini",
    instructions=SUPPORT_AGENT_PROMPT,
    tools=[
        categorize_ticket_tool,
        fetch_customer_info_tool,
        search_kb_tool,
    ],
    max_tokens=2048,
)


__all__ = ["support_agent", "SUPPORT_AGENT_PROMPT"]
