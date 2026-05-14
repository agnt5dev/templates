"""
Deep Research Functions

Individual research functions used in the workflow pipeline:
1. clarify_and_plan - Creates research plan using Scoping Agent
2. conduct_research - Gathers information using Research Agent
3. write_report - Synthesizes findings using Writing Agent
"""

from datetime import datetime, timezone
from textwrap import dedent
from agnt5 import function, FunctionContext
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
    result = await scoping_agent.run(scoping_prompt, context=ctx)

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
    result = await research_agent.run(research_prompt, context=ctx)

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
5. Ensure the report answers the original research question comprehensively
6. Do NOT include a quality assessment - end your report with the References section"""

    # Run agent synchronously (non-streaming)
    synthesis_result = await writing_agent.run(synthesis_prompt, context=ctx)
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
    evaluation_result = await writing_agent.run(evaluation_prompt, context=ctx)
    quality_assessment = evaluation_result.output

    ctx.logger.info("Quality assessment completed")

    return {
        "final_report": final_report,
        "quality_assessment": quality_assessment,
    }


__all__ = ["clarify_and_plan", "conduct_research", "write_report"]
