"""
Autonomous Deep Research Workflows

A fully autonomous research pipeline using 3 specialized agents:
1. Scoping Agent - Analyzes topic and creates research plan
2. Research Agent - Conducts systematic research using tools
3. Writing Agent - Synthesizes findings into comprehensive reports

The workflow runs from start to finish without requiring user intervention.
"""

import uuid
from datetime import datetime, timezone
from agnt5 import workflow, WorkflowContext, function, FunctionContext
from deep_research.entities import ResearchSession
from deep_research.agents import scoping_agent, research_agent, writing_agent


@function
async def clarify_and_plan(ctx: FunctionContext, topic: str) -> str:
    """
    Stage 1: Create research plan for the topic.

    Uses the Scoping Agent to:
    - Analyze the research topic and make reasonable assumptions if vague
    - Create a structured research plan with 3-6 subtopics

    Returns:
        str: The research plan
    """
    ctx.logger.info(f"Stage 1: Creating research plan for: {topic[:50]}...")

    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    scoping_prompt = f"""Today's date is {current_date}.

Research topic: {topic}

Create a structured research plan for this topic:
1. Break it into 3-6 manageable subtopics
2. Define the research strategy for each subtopic
3. Make reasonable assumptions if the topic is vague or ambiguous
4. Start your response with "PLAN:" followed by the structured plan"""

    # Run agent synchronously (non-streaming)
    result = await scoping_agent.run_sync(scoping_prompt, context=ctx)

    # Extract the research plan
    research_plan = result.output
    if research_plan.strip().startswith("PLAN:"):
        research_plan = research_plan.replace("PLAN:", "").strip()

    ctx.logger.info("Research plan created successfully")
    return research_plan


@function
async def conduct_research(ctx: FunctionContext, topic: str, research_plan: str) -> str:
    """
    Stage 2: Conduct systematic research using Wikipedia and web sources.

    Uses the Research Agent with tools to:
    - Execute research according to the plan
    - Gather information from Wikipedia and other sources
    - Organize findings by subtopic

    Returns:
        Structured research findings
    """
    ctx.logger.info(f"Stage 2: Conducting research for: {topic[:50]}...")

    research_prompt = f"""Execute systematic research for the following topic:

Topic: {topic}

Research Plan:
{research_plan}

Instructions:
1. Research each subtopic thoroughly using Wikipedia as your primary source
2. Supplement with web searches for additional context when needed
3. Organize your findings by subtopic
4. Cite all sources clearly (include titles and URLs)
5. Focus on factual information and verifiable details

Use the wikipedia_search_tool and fetch_webpage_tool to gather comprehensive information."""

    # Run agent synchronously (non-streaming)
    result = await research_agent.run_sync(research_prompt, context=ctx)

    ctx.logger.info(f"Research completed - {len(result.output)} characters of findings")

    return result.output


@function
async def write_report(ctx: FunctionContext, topic: str, research_plan: str, research_findings: str) -> dict:
    """
    Stage 3: Synthesize findings into a comprehensive report and evaluate quality.

    Uses the Writing Agent to:
    - Transform research findings into a well-structured academic report
    - Ensure proper citations and coherent narrative
    - Evaluate the quality and completeness of the output

    Returns:
        dict with 'final_report' and 'quality_assessment'
    """
    ctx.logger.info(f"Stage 3: Writing report for: {topic[:50]}...")

    synthesis_prompt = f"""Create a comprehensive academic report based on the research findings.

Topic: {topic}

Research Plan:
{research_plan}

Research Findings:
{research_findings}

Instructions:
1. Synthesize the findings into a well-structured academic report
2. Follow the report structure: Executive Summary, Introduction, Main Sections, Conclusion, References
3. Use proper citations in [Source Name](URL) format
4. Create a coherent narrative that connects different aspects of the research
5. Ensure the report answers the original research question comprehensively"""

    # Run agent synchronously (non-streaming)
    synthesis_result = await writing_agent.run_sync(synthesis_prompt, context=ctx)
    final_report = synthesis_result.output

    ctx.logger.info("Report synthesized, now evaluating quality...")

    # Evaluate the quality of the report
    evaluation_prompt = f"""Evaluate the quality and completeness of this research report.

Original Topic: {topic}

Research Report:
{final_report}

Provide a quality assessment using the criteria:
- Completeness: Does it answer the original research question?
- Accuracy: Are claims properly supported by sources?
- Clarity: Is it well-organized and easy to understand?
- Depth: Does it provide sufficient detail and analysis?

Use the format:
QUALITY ASSESSMENT:
- Completeness: [score/10] - [justification]
- Accuracy: [score/10] - [justification]
- Clarity: [score/10] - [justification]
- Depth: [score/10] - [justification]
- Overall: [score/10]

Gaps identified: [list any gaps or areas for improvement]"""

    # Run agent synchronously (non-streaming)
    evaluation_result = await writing_agent.run_sync(evaluation_prompt, context=ctx)
    quality_assessment = evaluation_result.output

    ctx.logger.info("Quality assessment completed")

    return {
        "final_report": final_report,
        "quality_assessment": quality_assessment,
    }


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

    The workflow maintains state in a ResearchSession entity and supports:
    - Resumable sessions
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

    # Load or create session entity
    session = ResearchSession(key=f"research:{session_id}")

    # Determine current state
    topic = await session.get_topic()
    research_plan = await session.get_research_plan()
    research_findings = await session.get_research_findings()
    final_report = await session.get_final_report()

    # Stage 1: Planning
    if not research_plan:
        if not topic:
            # First message - this is the initial topic
            await session.set_topic(message)
            topic = message

        ctx.logger.info("Stage 1: Creating research plan")

        # Run planning
        research_plan = await ctx.task(clarify_and_plan, topic)
        await session.set_research_plan(research_plan)

        ctx.logger.info("Research plan created and saved")

    # Stage 2: Research
    if not research_findings:
        ctx.logger.info("Stage 2: Conducting research")

        research_findings = await ctx.task(conduct_research, topic, research_plan)
        await session.set_research_findings(research_findings)

        ctx.logger.info("Research findings saved")

    # Stage 3: Write Report & Evaluate
    if not final_report:
        ctx.logger.info("Stage 3: Writing report and evaluating quality")

        write_result = await ctx.task(write_report, topic, research_plan, research_findings)

        final_report = write_result.get("final_report")
        quality_assessment = write_result.get("quality_assessment")

        await session.set_final_report(final_report)
        await session.set_quality_assessment(quality_assessment)

        ctx.logger.info("Research completed successfully")

    # Return final results
    return {
        "status": "completed",
        "session_id": session_id,
        "topic": topic,
        "research_plan": research_plan,
        "report": final_report,
        "quality_assessment": await session.get_quality_assessment(),
        "stage": "completed",
    }


__all__ = ["deep_research_workflow", "clarify_and_plan", "conduct_research", "write_report"]
