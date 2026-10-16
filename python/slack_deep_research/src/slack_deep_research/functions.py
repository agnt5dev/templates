from datetime import datetime, timezone

from agnt5 import function, FunctionContext
from slack_deep_research.agents import scoping_agent, research_agent, writing_agent


@function(name="plan_research")
async def _plan_research(ctx: FunctionContext, topic: str) -> str:
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = f"""Today's date is {current_date}.

Research topic: {topic}

Create a structured research plan for this topic:
1. Break it into 3-6 manageable subtopics
2. Define the research strategy for each subtopic
3. Make reasonable assumptions if the topic is vague or ambiguous
4. Start your response with "PLAN:" followed by the structured plan"""

    result = await scoping_agent.run(prompt, context=ctx)
    plan = result.output
    if plan.strip().startswith("PLAN:"):
        plan = plan.replace("PLAN:", "", 1).strip()
    ctx.logger.info("Research plan created successfully")
    return plan


@function(name="conduct_research")
async def _conduct_research(ctx: FunctionContext, topic: str, research_plan: str) -> str:
    prompt = f"""Execute systematic research for the following topic:

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

    result = await research_agent.run(prompt, context=ctx)
    ctx.logger.info(f"Research completed - {len(result.output)} characters of findings")
    return result.output


@function(name="write_report")
async def _write_report(
    ctx: FunctionContext, topic: str, research_plan: str, research_findings: str
) -> str:
    prompt = f"""Create a concise Slack-friendly research summary.

Topic: {topic}

Research Plan:
{research_plan}

Research Findings:
{research_findings}

Instructions:
1. Synthesize the findings into a brief, clear summary for Slack
2. Use plain text with * for bold and - for bullet points (no markdown headers or HTML)
3. Structure: bold topic title, Executive Summary (2-3 sentences), Key Findings (up to 5 bullets), Sources (top 3-5)
4. Keep total length under 2000 characters
5. Focus on the most important, actionable insights"""

    result = await writing_agent.run(prompt, context=ctx)
    ctx.logger.info("Research report synthesized successfully")
    return result.output


__all__ = ["_plan_research", "_conduct_research", "_write_report"]
