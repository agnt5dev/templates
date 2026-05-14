from pathlib import Path
from typing import Any, Dict

from agnt5 import workflow, WorkflowContext

from code_reviewer.agents import context_builder_agent, reviewer_agent
from code_reviewer.entities import CodeReviewSession
from code_reviewer.functions import synthesize_review_report
from code_reviewer.prompts import CONTEXT_BUILDER_USER_PROMPT


@workflow(name="code_reviewer_workflow")
async def code_reviewer_workflow(
    ctx: WorkflowContext,
    pr_url: str,
    ticket_url: str
) -> Dict[str, Any]:
    ctx.logger.info("🚀 Starting code review workflow")

    # Create/get entity instance for this review session
    # Using pr_url as entity_id to track per-PR state
    entity_id = f"review_{pr_url.split('/')[-1]}"
    session = CodeReviewSession(key=entity_id)

    # Set initial state in entity
    await session.set_initial_state(pr_url, ticket_url)

    ctx.logger.info("🔍 Step 1/3: Building context")
    await session.set_context_building()

    context_result = await ctx.step(
        "context_building",
        async_build_context(ctx, pr_url, ticket_url)
    )

    await session.set_context_result(context_result["output"], context_result["tool_calls"])
    ctx.logger.info("✅ Context successfully built")

    ctx.logger.info("🧩 Step 2/3: Performing code review")
    await session.set_code_review()

    review_result = await ctx.step(
        "code_review",
        async_review_code(ctx, context_result["output"], pr_url, ticket_url)
    )

    await session.set_review_result(review_result["output"], review_result["tool_calls"])
    ctx.logger.info("✅ Code review completed successfully")

    ctx.logger.info("🧠 Step 3/3: Synthesizing final report")
    await session.set_synthesizing()

    synthesized_report = await ctx.task(
        synthesize_review_report,
        code_review=review_result["output"]
    )

    await session.set_synthesized_report(synthesized_report)
    await session.set_completed()
    ctx.logger.info("✅ Workflow completed successfully")

    # Save report to markdown file
    try:
        # Extract PR number from URL for filename
        pr_number = pr_url.split('/')[-1]
        repo_name = pr_url.split('/')[-3]

        # Create reports directory if it doesn't exist
        reports_dir = Path("/app/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Save with meaningful filename
        report_filename = f"{repo_name}_pr_{pr_number}_review.md"
        report_path = reports_dir / report_filename

        with open(report_path, "w") as f:
            f.write(f"# Code Review Report\n\n")
            f.write(f"**PR**: {pr_url}\n")
            f.write(f"**Ticket**: {ticket_url}\n\n")
            f.write(f"---\n\n")
            f.write(synthesized_report)

        ctx.logger.info(f"📄 Report saved to: {report_path}")
        saved_report_path = str(report_path)
    except Exception as e:
        ctx.logger.warning(f"⚠️ Failed to save report to file: {e}")
        saved_report_path = None

    # Get final entity state
    entity_state = await session.get_state()

    return {
        "status": "success",
        "pr_url": pr_url,
        "ticket_url": ticket_url,
        "context": {
            "output": context_result["output"],
            "tool_calls": context_result["tool_calls"],
        },
        "review": {
            "output": review_result["output"],
            "tool_calls": review_result["tool_calls"],
        },
        "report": synthesized_report,
        "report_file": saved_report_path,
        "entity_state": entity_state,
    }


async def async_build_context(
    ctx: WorkflowContext, pr_url: str, ticket_url: str
) -> Dict[str, Any]:
    context_prompt = CONTEXT_BUILDER_USER_PROMPT.format(
        pr_url=pr_url,
        ticket_url=ticket_url
    )

    result = await context_builder_agent.run(
        user_message=context_prompt,
        context=ctx
    )

    return {
        "output": result.output,
        "tool_calls": len(result.tool_calls),
    }


async def async_review_code(
    ctx: WorkflowContext,
    context_output: str,
    pr_url: str,
    ticket_url: str
) -> Dict[str, Any]:
    review_user_prompt = f"""Using the gathered context below, perform a thorough code review:

Context:
{context_output}

PR URL: {pr_url}
Ticket URL: {ticket_url}

Focus on:
- Security vulnerabilities (SQL injection, XSS, auth flaws, secrets)
- Performance issues (N+1 queries, inefficient algorithms, memory leaks)
- Code quality (smells, duplications, complexity, maintainability)
- Standards (naming, formatting, documentation)
- Alignment with ticket requirements

Provide structured, actionable feedback with file/line references.
"""

    result = await reviewer_agent.run(
        user_message=review_user_prompt,
        context=ctx
    )

    return {
        "output": result.output,
        "tool_calls": len(result.tool_calls),
    }


__all__ = [
    "code_reviewer_workflow",
]