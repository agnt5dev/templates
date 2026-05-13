"""
Support Triage Tools - Agent Tool Definitions

Tools that the Support Agent can call during ticket analysis.
These demonstrate AGNT5's automatic retry and recovery for flaky operations.
"""

import asyncio
import random
import os

from agnt5 import Context, tool

# Configurable failure rate for demo purposes
# Set AGNT5_TOOL_FAILURE_RATE=0.3 to fail 30% of the time
TOOL_FAILURE_RATE = float(os.getenv("AGNT5_TOOL_FAILURE_RATE", "0.3"))


# Sample knowledge base (embedded for simplicity)
KNOWLEDGE_BASE = [
    {
        "id": "doc_refund_policy",
        "title": "Refund Policy",
        "content": "We offer full refunds within 30 days of purchase. For subscription plans, you can get a prorated refund for unused time. To request a refund, contact support with your order number.",
        "keywords": ["refund", "money back", "return", "cancel"],
    },
    {
        "id": "doc_billing_faq",
        "title": "Billing FAQ",
        "content": "Billing cycles on the 1st of each month. You can update payment methods in Account Settings. Failed payments retry 3 times over 7 days before account suspension.",
        "keywords": ["billing", "payment", "charge", "invoice", "subscription"],
    },
    {
        "id": "doc_upgrade_guide",
        "title": "Plan Upgrade Guide",
        "content": "To upgrade your plan: Go to Settings > Subscription > Change Plan. The price difference is prorated. New features are available immediately after upgrade.",
        "keywords": ["upgrade", "plan", "tier", "features", "premium"],
    },
    {
        "id": "doc_password_reset",
        "title": "Password Reset",
        "content": "Click 'Forgot Password' on the login page. Enter your email to receive a reset link (valid 24 hours). If you don't receive it, check spam or contact support.",
        "keywords": ["password", "reset", "forgot", "login", "access"],
    },
    {
        "id": "doc_data_export",
        "title": "Data Export",
        "content": "You can export your data anytime from Settings > Privacy > Export Data. The export includes all your content and settings in JSON format. Processing takes up to 24 hours.",
        "keywords": ["export", "data", "download", "backup", "privacy"],
    },
]

# Sample customer database (embedded for simplicity)
CUSTOMER_DB = {
    "TCK-1001": {
        "customer_id": "cust_12345",
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "plan": "Pro",
        "member_since": "2023-06-15",
        "lifetime_value": 599.00,
        "support_tickets": 3,
    },
    "TCK-1002": {
        "customer_id": "cust_67890",
        "name": "Bob Smith",
        "email": "bob@example.com",
        "plan": "Enterprise",
        "member_since": "2022-01-10",
        "lifetime_value": 4799.00,
        "support_tickets": 12,
    },
    "default": {
        "customer_id": "cust_00000",
        "name": "Unknown Customer",
        "email": "unknown@example.com",
        "plan": "Free",
        "member_since": "2024-01-01",
        "lifetime_value": 0.00,
        "support_tickets": 1,
    },
}


@tool(auto_schema=True)
async def search_kb_tool(ctx: Context, query: str) -> str:
    """
    Search the knowledge base for relevant documentation.

    Use this tool to find documentation that helps answer the customer's question.

    Args:
        query: Search query based on the ticket content

    Returns:
        Relevant knowledge base articles as formatted text
    """
    ctx.logger.info(f"Searching knowledge base for: {query[:50]}...")

    # Simulate search latency
    await asyncio.sleep(0.5)

    # Simple keyword matching
    query_lower = query.lower()
    results = []

    for doc in KNOWLEDGE_BASE:
        score = sum(1 for kw in doc["keywords"] if kw in query_lower)
        if score > 0:
            results.append({
                "title": doc["title"],
                "content": doc["content"],
                "score": score,
            })

    # Sort by relevance
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:3]  # Top 3

    if not results:
        ctx.logger.info("No matching documents found")
        return "No relevant documentation found for this query."

    ctx.logger.info(f"Found {len(results)} relevant documents")

    # Format results
    formatted = "Relevant Knowledge Base Articles:\n\n"
    for i, doc in enumerate(results, 1):
        formatted += f"{i}. **{doc['title']}**\n{doc['content']}\n\n"

    return formatted


@tool(auto_schema=True)
async def fetch_customer_info_tool(ctx: Context, ticket_id: str) -> str:
    """
    Fetch customer information from the CRM system.

    This tool retrieves customer details to personalize the response.
    NOTE: This simulates a flaky external API that sometimes fails.
    AGNT5 will automatically retry on failure.

    Args:
        ticket_id: The ticket ID to look up customer info for

    Returns:
        Customer information as formatted text
    """
    ctx.logger.info(f"Fetching customer info for ticket: {ticket_id}")

    # Simulate API latency
    await asyncio.sleep(0.3)

    # Simulate flaky API - randomly fail based on configured rate
    if random.random() < TOOL_FAILURE_RATE:
        ctx.logger.warning(f"CRM API error - connection timeout (simulated failure)")
        raise ConnectionError(
            "CRM API timeout: Unable to reach customer database. "
            "This is a transient error - please retry."
        )

    # Look up customer (use default if not found)
    customer = CUSTOMER_DB.get(ticket_id, CUSTOMER_DB["default"])

    ctx.logger.info(f"Retrieved customer info: {customer['name']} ({customer['plan']} plan)")

    # Format customer info
    return f"""Customer Information:
- Name: {customer['name']}
- Email: {customer['email']}
- Plan: {customer['plan']}
- Member Since: {customer['member_since']}
- Lifetime Value: ${customer['lifetime_value']:.2f}
- Previous Support Tickets: {customer['support_tickets']}

Priority: {'High' if customer['plan'] == 'Enterprise' else 'Normal'}"""


@tool(auto_schema=True)
async def categorize_ticket_tool(ctx: Context, subject: str, body: str) -> str:
    """
    Categorize the support ticket based on its content.

    Use this to determine the ticket category and priority.

    Args:
        subject: The ticket subject line
        body: The ticket body text

    Returns:
        Ticket categorization with category and suggested priority
    """
    ctx.logger.info("Categorizing ticket...")

    # Simulate processing
    await asyncio.sleep(0.2)

    combined = f"{subject} {body}".lower()

    # Simple rule-based categorization
    if any(word in combined for word in ["refund", "money", "charge", "cancel"]):
        category = "Billing"
        priority = "High"
    elif any(word in combined for word in ["password", "login", "access", "locked"]):
        category = "Account Access"
        priority = "High"
    elif any(word in combined for word in ["upgrade", "plan", "features", "pricing"]):
        category = "Sales"
        priority = "Medium"
    elif any(word in combined for word in ["bug", "error", "broken", "not working"]):
        category = "Technical Issue"
        priority = "High"
    elif any(word in combined for word in ["export", "data", "download"]):
        category = "Data Request"
        priority = "Low"
    else:
        category = "General Inquiry"
        priority = "Medium"

    ctx.logger.info(f"Categorized as: {category} ({priority} priority)")

    return f"""Ticket Analysis:
- Category: {category}
- Suggested Priority: {priority}
- Sentiment: {'Urgent' if priority == 'High' else 'Normal'}"""


__all__ = [
    "search_kb_tool",
    "fetch_customer_info_tool",
    "categorize_ticket_tool",
    # Constants exported for mock mode
    "KNOWLEDGE_BASE",
    "CUSTOMER_DB",
    "TOOL_FAILURE_RATE",
]
