"""
Support Triage Workflows - AGNT5 Quickstart

Two workflows demonstrating different patterns:

1. support_triage (chat=False) - Structured Pipeline
   - Checkpointing: Each ctx.step() call is memoized; completed steps skip on restart
   - Human-in-the-Loop: Durable pauses for approval that survive restarts
   - Exactly-Once: No duplicate side effects after recovery
   - Best for: Formal ticket processing with approval gates

2. support_chat (chat=True) - Interactive Chat
   - Multi-turn conversation with the support agent
   - Agent uses tools to search KB and fetch customer info
   - Best for: Interactive support, exploring issues, quick answers
"""

import os

from agnt5 import WorkflowContext, workflow
from datetime import datetime
from support_triage.agent import support_agent
from support_triage.functions import fetch_customer_info, analyze_ticket, post_reply


@workflow
async def support_triage(ctx: WorkflowContext, ticket: dict) -> dict:
    """
    Triage a support ticket with AI agent analysis and human approval.

    Flow:
    1. Fetch customer info (demonstrates checkpointing)
    2. AI Agent analyzes the ticket with customer context
    3. Wait for human approval (durable pause - survives restarts)
    4. Post reply to ticket system (exactly-once guarantee)

    Args:
        ticket: Dict with ticket_id, subject, and body

    Returns:
        Dict with status and details

    Demo - Watch these AGNT5 superpowers in action:

    1. CHECKPOINTING (Durable Execution)
       - Each ctx.step() / ctx.task() call is checkpointed
       - If workflow restarts, completed steps are skipped (memoized)
       - Watch the timeline to see step execution order

    2. HUMAN-IN-THE-LOOP
       - Workflow pauses for approval in Dev Studio
       - This pause is durable - it survives server restarts
       - Hours later, approve and workflow resumes

    3. EXACTLY-ONCE
       - post_reply executes exactly once, even after failures
       - Check .agnt5_demo/replies.log to verify no duplicates

    4. ZERO-CONFIG OBSERVABILITY
       - Every step and decision visible in the timeline
       - Click any event to see inputs, outputs, and timing
    """
    ticket_id = ticket.get("ticket_id", "unknown")
    subject = ticket.get("subject", "")

    ctx.logger.info(f"=== Starting Support Triage for {ticket_id} ===")
    ctx.logger.info(f"Subject: {subject}")

    # Step 1: Fetch customer info (demonstrates checkpointing)
    # This step is checkpointed - if workflow restarts, cached result is used.
    # Watch the timeline to see how steps are recorded!
    ctx.logger.info("Step 1: Fetching customer info...")
    ctx.logger.info("  (This step is checkpointed - watch the timeline!)")

    customer = await ctx.task(fetch_customer_info, ticket_id=ticket_id)

    ctx.logger.info(f"Customer: {customer.get('name')} ({customer.get('plan')} plan)")

    # Step 2: AI Agent analyzes the ticket
    # Uses the customer info we just fetched to personalize the response
    ctx.logger.info("Step 2: AI Agent analyzing ticket...")

    analysis = await ctx.task(analyze_ticket, ticket=ticket, customer=customer)

    draft = analysis.get("draft_reply", "")
    ctx.logger.info(f"Agent analysis complete. Draft ready ({len(draft)} chars)")

    # Step 3: Human approval (durable pause - survives restarts)
    ctx.logger.info("Step 3: Waiting for human approval...")
    ctx.logger.info("  This pause is durable - it survives server restarts!")

    decision = await ctx.wait_for_user(
        question=f"Review this AI-generated reply for ticket #{ticket_id}:\n\n---\n{draft}\n---\n\nApprove sending this reply?",
        input_type="select",
        options=[
            {"id": "approve", "label": "Send Reply"},
            {"id": "edit", "label": "Edit & Send"},
            {"id": "reject", "label": "Reject"},
        ],
    )

    ctx.logger.info(f"Decision received: {decision}")

    if decision == "reject":
        ctx.logger.info("Reply rejected by reviewer")
        return {
            "status": "rejected",
            "ticket_id": ticket_id,
            "message": "Reply was rejected by human reviewer",
        }

    # Handle edit case - get the edited message
    final_message = draft
    if decision == "edit":
        ctx.logger.info("Requesting edited message...")
        final_message = await ctx.wait_for_user(
            question="Please provide your edited reply:",
            input_type="text",
        )
        ctx.logger.info("Received edited message")

    # Step 4: Post reply (exactly-once via idempotency)
    ctx.logger.info("Step 4: Posting reply (exactly-once guarantee)...")
    result = await ctx.task(post_reply, ticket_id=ticket_id, message=final_message)

    ctx.logger.info(f"=== Triage Complete for {ticket_id} ===")
    ctx.logger.info(f"Reply ID: {result.get('reply_id')}")

    return {
        "status": "sent",
        "ticket_id": ticket_id,
        "reply_id": result.get("reply_id"),
        "message": final_message,
        "agent_analysis": analysis.get("agent_output", "")[
            :500
        ],  # Truncate for response
    }


def _mock_chat_response(message: str, customer_id: str | None = None) -> str:
    """Generate a mock response when no API key is available."""
    msg_lower = message.lower()

    greeting = f"Hi{' ' + customer_id if customer_id else ''}!"

    if any(word in msg_lower for word in ["refund", "money", "charge"]):
        return f"""{greeting}

I understand you have a billing question. Our refund policy allows full refunds within 30 days of purchase. For subscription plans, you can receive a prorated refund for unused time.

To help you further, could you provide your order number or the email associated with your account?

(Note: Running in mock mode - set OPENAI_API_KEY for full AI responses)"""

    elif any(word in msg_lower for word in ["password", "login", "access", "account"]):
        return f"""{greeting}

I can help with account access issues. Here are the steps to reset your password:

1. Click "Forgot Password" on the login page
2. Enter your account email address
3. Check your inbox for the reset link (valid 24 hours)

If you don't receive the email, check your spam folder. Let me know if you need further assistance!

(Note: Running in mock mode - set OPENAI_API_KEY for full AI responses)"""

    elif any(word in msg_lower for word in ["upgrade", "plan", "feature", "pricing"]):
        return f"""{greeting}

I'd be happy to help with plan information! You can upgrade anytime from Settings > Subscription > Change Plan.

The price difference is prorated, and new features activate immediately after upgrading.

What specific features are you interested in?

(Note: Running in mock mode - set OPENAI_API_KEY for full AI responses)"""

    else:
        return f"""{greeting}

Thanks for reaching out! I'm here to help with any questions about our product or services.

Could you tell me more about what you're looking for? I can help with:
- Billing and refunds
- Account access issues
- Plan upgrades and features
- Technical questions

(Note: Running in mock mode - set OPENAI_API_KEY for full AI responses)"""


@workflow(cron="* * * * *")
async def my_scheduled_workflow(ctx: WorkflowContext):
    # This runs every minute
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx.logger.info(f"Executing scheduled workflow at {timestamp_str}")
    return {"status": "executed"}


__all__ = ["support_triage", "my_scheduled_workflow"]
