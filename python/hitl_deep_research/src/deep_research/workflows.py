"""
Deep Research Workflows with Human-in-the-Loop Approval

A research pipeline using 3 specialized agents with HITL approval:
1. Scoping Agent - Analyzes topic and creates research plan
2. [HITL] User approval of research plan (approve/edit/reject)
3. Research Agent - Conducts systematic research using tools
4. Writing Agent - Synthesizes findings into comprehensive reports

The workflow pauses for user approval after the research plan is generated,
allowing users to review, edit, or reject the plan before research begins.
"""

from agnt5 import workflow, WorkflowContext
from deep_research.functions import _plan_research, _conduct_research, _write_report


@workflow
async def deep_research_workflow(
    ctx: WorkflowContext,
    message: str,
) -> dict:
    """
    Comprehensive deep research workflow with HITL approval.

    Stages:
    1. Plan - Scoping Agent creates research plan
    2. Approve - HITL: User reviews and approves/edits/rejects the plan (durable pause)
    3. Research - Research Agent gathers information using tools
    4. Write - Writing Agent synthesizes report

    The HITL pause at Stage 2 is durable - it survives server restarts and can
    wait indefinitely for user input.

    Args:
        message: Research topic or question

    Returns:
        dict with status and results
        - status: "completed" if finished, "rejected" if user rejected plan
    """
    ctx.logger.info(f"Deep research workflow started, message: {message[:100]}...")

    topic = message

    # Stage 1: Planning
    ctx.logger.info("Stage 1: Creating research plan")
    research_plan = await ctx.step(_plan_research, topic)
    ctx.logger.info("Research plan created")

    # HITL: Wait for user approval of the research plan.
    # The workflow body re-runs top-to-bottom on resume, so guard log/side effects
    # with `not ctx._is_replay` to fire them only on the first pass. The
    # wait_for_user() call below MUST stay unconditional — on replay it returns the
    # recorded answer so execution can continue past the pause.
    if not ctx._is_replay:
        ctx.logger.info("Stage 2: Waiting for human approval of research plan...")
        ctx.logger.info("  This pause is durable - it survives server restarts!")

    approval_question = f"""Please review the research plan below:

---
{research_plan}
---

Do you approve this research plan to proceed with research?"""

    decision = await ctx.wait_for_user(
        question=approval_question,
        input_type="select",
        options=[
            {"id": "approve", "label": "Approve Plan"},
            {"id": "edit", "label": "Edit Plan"},
            {"id": "reject", "label": "Reject"},
        ],
    )

    ctx.logger.info(f"Decision received: {decision}")

    if decision == "reject":
        ctx.logger.info("Research plan rejected by user")
        return {
            "status": "rejected",
            "topic": topic,
            "research_plan": research_plan,
            "message": "Research plan was rejected. Please start a new session with updated requirements.",
        }

    if decision == "edit":
        ctx.logger.info("User chose to edit the research plan")
        research_plan = await ctx.wait_for_user(
            question=f"""Please provide your edited research plan.

Here is the original plan for reference:
---
{research_plan}
---

Paste your revised plan below:""",
            input_type="text",
        )
        ctx.logger.info("Received edited research plan from user")

    ctx.logger.info("Research plan approved, proceeding to research phase")

    # Stage 3: Research
    ctx.logger.info("Stage 3: Conducting research")
    research_findings = await ctx.step(_conduct_research, topic, research_plan)
    ctx.logger.info("Research findings gathered")

    # Stage 4: Write Report
    ctx.logger.info("Stage 4: Writing report")
    final_report = await ctx.step(_write_report, topic, research_plan, research_findings)

    ctx.logger.info("Research completed successfully")

    return {
        "status": "completed",
        "topic": topic,
        "report": final_report,
    }


__all__ = ["deep_research_workflow"]
