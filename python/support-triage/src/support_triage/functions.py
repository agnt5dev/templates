"""
Support Triage Functions - Checkpointed Operations

Each function is decorated with @function, making it:
- Automatically checkpointed when called via ctx.step()
- Retryable via platform when invoked through Gateway API
- Logged with correlation IDs for observability

test.
"""

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime

from agnt5 import function, FunctionContext

from support_triage.agent import support_agent
from support_triage.tools import (
    KNOWLEDGE_BASE,
    CUSTOMER_DB,
)


# Check if mock mode is enabled (for demos without API key)
USE_MOCK_MODE = os.getenv("AGNT5_MOCK_MODE", "").lower() in ("1", "true", "yes")


# Simulated data paths (created at runtime)
DATA_DIR = Path(".agnt5_demo")
REPLIES_LOG = DATA_DIR / "replies.log"
IDEMPOTENCY_DB = DATA_DIR / "idempotency.json"


@function
async def hello_world(ctx: FunctionContext, name: str) -> str:
    # await asyncio.sleep(20)
    ctx.logger.info(f"Hello {name}")
    ctx.logger.debug(f"Hello, debug statement {name}")
    return f"Hello {name}"


@function
async def fetch_customer_info(ctx: FunctionContext, ticket_id: str) -> dict:
    """
    Fetch customer info from CRM system.

    This function demonstrates checkpointing - when called via ctx.step() / ctx.task(),
    the result is memoized. If the workflow restarts, this step won't re-execute;
    the cached result is returned instead.

    Args:
        ticket_id: The ticket ID to look up customer info for

    Returns:
        Dict with customer information (name, email, plan, etc.)
    """
    # Look up customer (use default if not found)
    customer = CUSTOMER_DB.get(ticket_id, CUSTOMER_DB["default"])
    ctx.logger.info(f"Retrieved customer: {customer['name']} ({customer['plan']} plan)")

    return customer


@function
async def analyze_ticket(
    ctx: FunctionContext, ticket: dict, customer: dict | None = None
) -> dict:
    """
    Analyze a support ticket using the AI Agent.

    The agent will:
    1. Categorize the ticket (type and priority)
    2. Use provided customer info for personalization
    3. Search the knowledge base for relevant docs
    4. Draft a personalized response

    This demonstrates:
    - Agent with tools
    - Checkpointed execution (won't repeat after crash)

    Set AGNT5_MOCK_MODE=1 to run without an API key (uses mock responses).

    Args:
        ticket: Dict with ticket_id, subject, and body
        customer: Dict with customer info (name, email, plan, etc.)

    Returns:
        Dict with analysis results and draft reply
    """
    ticket_id = ticket.get("ticket_id", "unknown")
    subject = ticket.get("subject", "")
    body = ticket.get("body", "")

    ctx.logger.info(f"Agent analyzing ticket {ticket_id}...")

    if USE_MOCK_MODE:
        ctx.logger.info("Running in MOCK MODE (no API key required)")
        return await _mock_analyze_ticket(ctx, ticket_id, subject, body, customer)

    # Build the prompt for the agent
    agent_prompt = f"""Please analyze this support ticket and draft a response.

TICKET ID: {ticket_id}

SUBJECT: {subject}

BODY:
{body}

Use the available tools to:
1. Categorize this ticket
2. Fetch customer information for personalization
3. Search the knowledge base for relevant documentation
4. Then draft a helpful response based on all this information"""

    # Run the agent - this executes tools and generates a response
    result = await support_agent.run(agent_prompt, context=ctx)

    ctx.logger.info("Agent analysis complete")

    # Extract the draft reply from the agent's output
    output = result.output
    draft = _extract_draft_reply(output)

    return {
        "ticket_id": ticket_id,
        "agent_output": output,
        "draft_reply": draft,
        "tool_calls": len(result.tool_calls) if hasattr(result, "tool_calls") else 0,
    }


async def _mock_analyze_ticket(
    ctx: FunctionContext,
    ticket_id: str,
    subject: str,
    body: str,
    customer: dict | None = None,
) -> dict:
    """
    Mock ticket analysis for demos without an API key.

    This simulates the agent's behavior including:
    - Tool calls with simulated latency
    - Template-based response generation

    Uses customer info passed from the workflow (already fetched with retry).
    """
    combined = f"{subject} {body}".lower()
    tool_calls = 0

    # Step 1: Categorize ticket (simulated)
    ctx.logger.info("  [Mock] Tool call: categorize_ticket")
    await asyncio.sleep(0.2)
    tool_calls += 1

    if any(word in combined for word in ["refund", "money", "charge", "cancel"]):
        category = "Billing"
        priority = "High"
    elif any(word in combined for word in ["password", "login", "access"]):
        category = "Account Access"
        priority = "High"
    elif any(word in combined for word in ["upgrade", "plan", "features"]):
        category = "Sales"
        priority = "Medium"
    else:
        category = "General Inquiry"
        priority = "Medium"

    ctx.logger.info(f"  [Mock] Categorized: {category} ({priority})")

    # Use customer info passed from workflow (already fetched with retry)
    if customer is None:
        customer = CUSTOMER_DB.get(ticket_id, CUSTOMER_DB["default"])
    customer_name = customer["name"]
    customer_plan = customer["plan"]

    # Step 2: Search KB (simulated)
    ctx.logger.info("  [Mock] Tool call: search_kb")
    await asyncio.sleep(0.5)
    tool_calls += 1

    # Find relevant docs
    relevant_docs = []
    for doc in KNOWLEDGE_BASE:
        if any(kw in combined for kw in doc["keywords"]):
            relevant_docs.append(doc)

    kb_info = (
        relevant_docs[0]["content"]
        if relevant_docs
        else "No specific documentation found."
    )
    ctx.logger.info(f"  [Mock] Found {len(relevant_docs)} relevant KB articles")

    # Step 3: Generate mock response
    ctx.logger.info("  [Mock] Generating response...")
    await asyncio.sleep(0.3)

    draft = _generate_mock_reply(customer_name, subject, body, kb_info, category)

    agent_output = f"""## Ticket Analysis

**Category:** {category}
**Priority:** {priority}

**Customer Information:**
- Name: {customer_name}
- Plan: {customer_plan}

**Relevant Documentation:**
{kb_info[:200]}...

---
DRAFT REPLY:
{draft}
---"""

    return {
        "ticket_id": ticket_id,
        "agent_output": agent_output,
        "draft_reply": draft,
        "tool_calls": tool_calls,
    }


def _generate_mock_reply(
    customer_name: str, subject: str, body: str, kb_info: str, category: str
) -> str:
    """Generate a mock support reply based on ticket content."""
    combined = f"{subject} {body}".lower()

    if "refund" in combined or "money" in combined:
        return f"""Hi {customer_name},

Thank you for reaching out about your refund request.

I understand you're looking to get a refund. Based on our policy, we offer full refunds within 30 days of purchase. For subscription plans, you can receive a prorated refund for any unused time.

To process your refund, I'll need:
1. Your order number or account email
2. The reason for the refund (optional, but helps us improve)

Once I have these details, I can process your refund within 2-3 business days.

Is there anything else I can help you with?

Best regards,
Support Team"""

    elif "upgrade" in combined or "plan" in combined:
        return f"""Hi {customer_name},

Thank you for your interest in upgrading your plan!

To upgrade, you can:
1. Go to Settings > Subscription > Change Plan
2. Select your new plan tier
3. Confirm the upgrade

The price difference will be prorated based on your current billing cycle, and all new features will be available immediately after the upgrade.

Would you like me to walk you through the process, or do you have any questions about the available plans?

Best regards,
Support Team"""

    elif "password" in combined or "login" in combined:
        return f"""Hi {customer_name},

I'm sorry to hear you're having trouble accessing your account.

To reset your password:
1. Click "Forgot Password" on the login page
2. Enter the email address associated with your account
3. Check your inbox for a reset link (valid for 24 hours)

If you don't receive the email within a few minutes, please check your spam folder. If it's still not there, let me know and I can help you further.

Best regards,
Support Team"""

    else:
        return f"""Hi {customer_name},

Thank you for contacting support about "{subject}".

I've reviewed your request and I'm happy to help. Based on our knowledge base:

{kb_info[:200]}

Please let me know if you need any clarification or have additional questions. I'm here to help!

Best regards,
Support Team"""


def _extract_draft_reply(agent_output: str) -> str:
    """Extract the draft reply from the agent's output."""
    # Try to find content between DRAFT REPLY markers
    match = re.search(
        r"DRAFT REPLY:\s*\n(.*?)(?:\n---|\Z)", agent_output, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()

    # If no markers found, look for a greeting-style response
    lines = agent_output.split("\n")
    reply_lines = []
    in_reply = False

    for line in lines:
        # Start capturing at common greeting patterns
        if any(
            line.strip().lower().startswith(g)
            for g in ["hi ", "hello ", "dear ", "thank you"]
        ):
            in_reply = True
        if in_reply:
            reply_lines.append(line)

    if reply_lines:
        return "\n".join(reply_lines).strip()

    # Fallback: return the full output
    return agent_output.strip()


@function
async def post_reply(ctx: FunctionContext, ticket_id: str, message: str) -> dict:
    """
    Post reply to the ticket system.

    This is a SIDE EFFECT that must be EXACTLY-ONCE.
    The checkpoint + idempotency key ensures no duplicate posts.

    In production, this would call the Zendesk/Intercom/etc API.
    The idempotency key prevents duplicate posts even if the API
    is called multiple times (e.g., due to retry or replay).

    Args:
        ticket_id: Ticket identifier
        message: Reply message to post

    Returns:
        Dict with reply_id and status
    """
    ctx.logger.info(f"Posting reply to ticket {ticket_id}...")

    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)

    # Create idempotency key from run_id + ticket_id
    idempotency_key = f"{ctx.run_id}:{ticket_id}"

    # Check if already posted (idempotency check)
    seen_keys = []
    if IDEMPOTENCY_DB.exists():
        try:
            seen_keys = json.loads(IDEMPOTENCY_DB.read_text())
        except json.JSONDecodeError:
            seen_keys = []

    if idempotency_key in seen_keys:
        ctx.logger.warning(f"Duplicate suppressed: {idempotency_key}")
        return {
            "reply_id": f"r_{ticket_id}",
            "posted": False,
            "reason": "duplicate_suppressed",
        }

    # Simulate posting to ticket system
    await asyncio.sleep(0.2)

    # Log the reply (simulated side effect)
    reply_record = {
        "timestamp": datetime.now().isoformat(),
        "ticket_id": ticket_id,
        "message": message,
        "run_id": ctx.run_id,
    }
    with REPLIES_LOG.open("a") as f:
        f.write(json.dumps(reply_record) + "\n")

    # Record idempotency key
    seen_keys.append(idempotency_key)
    IDEMPOTENCY_DB.write_text(json.dumps(seen_keys, indent=2))

    ctx.logger.info(f"Reply posted successfully to ticket {ticket_id}")

    return {
        "reply_id": f"r_{ticket_id}",
        "posted": True,
        "timestamp": reply_record["timestamp"],
    }


__all__ = ["fetch_customer_info", "analyze_ticket", "post_reply"]
