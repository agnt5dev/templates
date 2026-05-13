"""
Autonomous Deep Research Workflows

A fully autonomous research pipeline using 3 specialized agents:
1. Scoping Agent - Analyzes topic and creates research plan
2. Research Agent - Conducts systematic research using tools
3. Writing Agent - Synthesizes findings into comprehensive reports

The workflow runs from start to finish without requiring user intervention.
"""

import uuid
from agnt5 import workflow, WorkflowContext
from deep_research.functions import clarify_and_plan, conduct_research, write_report


@workflow
async def deep_research_workflow(
    ctx: WorkflowContext,
    message: str,
    session_id: str = None
) -> dict:
    """
    Comprehensive deep research workflow with 3-stage pipeline.

    Stages:
    1. Plan - Scoping Agent creates research plan
    2. Research - Research Agent gathers information using tools
    3. Write - Writing Agent synthesizes report and evaluates quality

    The workflow maintains state via ctx.state and supports:
    - Resumable sessions via durable state checkpointing
    - Comprehensive academic reports with quality assessment
    - Autonomous execution from start to finish

    Args:
        message: Research topic or question
        session_id: Session identifier (auto-generated if not provided)

    Returns:
        dict with status, session_id, and results
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    ctx.logger.info(f"Deep research workflow - session: {session_id}, message: {message[:100]}...")

    # Determine current state from workflow's durable state
    topic = ctx.state.get("topic", "")
    research_plan = ctx.state.get("research_plan")
    research_findings = ctx.state.get("research_findings", "")
    final_report = ctx.state.get("final_report")

    # Stage 1: Planning
    if not research_plan:
        if not topic:
            # First message - this is the initial topic
            ctx.state.set("topic", message)
            topic = message

        ctx.logger.info("Stage 1: Creating research plan")

        # Run planning
        research_plan = await ctx.task(clarify_and_plan, topic)
        ctx.state.set("research_plan", research_plan)

        ctx.logger.info("Research plan created and saved")

    # Stage 2: Research
    if not research_findings:
        ctx.logger.info("Stage 2: Conducting research")

        research_findings = await ctx.task(conduct_research, topic, research_plan)
        ctx.state.set("research_findings", research_findings)

        ctx.logger.info("Research findings saved")

    # Stage 3: Write Report & Evaluate
    if not final_report:
        ctx.logger.info("Stage 3: Writing report and evaluating quality")

        write_result = await ctx.task(write_report, topic, research_plan, research_findings)

        final_report = write_result.get("final_report")
        quality_assessment = write_result.get("quality_assessment")

        ctx.state.set("final_report", final_report)
        ctx.state.set("quality_assessment", quality_assessment)

        ctx.logger.info("Research completed successfully")

    # Return final results
    return {
        "status": "completed",
        "session_id": session_id,
        "topic": topic,
        "research_plan": research_plan,
        "report": final_report,
        "quality_assessment": ctx.state.get("quality_assessment"),
        "stage": "completed",
    }


__all__ = ["deep_research_workflow"]
