import re
from pathlib import Path
from typing import Any, Dict

from agnt5 import workflow, WorkflowContext

from code_reviewer.agents import context_builder_agent, reviewer_agent
from code_reviewer.functions import (
    fetch_pr_node,
    detect_tech_stack_node,
    review_file_node,
    security_review_node,
)
from code_reviewer.prompts import CONTEXT_BUILDER_USER_PROMPT

PR_SIZE_WARNING_THRESHOLD = 30


@workflow(name="code_reviewer_workflow")
async def code_reviewer_workflow(
    ctx: WorkflowContext,
    pr_url: str,
    ticket_url: str = "",
) -> Dict[str, Any]:
    ctx.logger.info("🚀 Starting code review workflow")
    ctx.state.set("pr_url", pr_url)
    ctx.state.set("ticket_url", ticket_url)
    ctx.state.set("status", "in_progress")

    # ── STEP 1: context_builder_agent + fetch_pr_node in parallel ─────────────
    # context_builder_agent autonomously calls its tools (pr_fetcher,
    # detect_ticket_source, jira/linear_ticket_fetcher) to build a rich
    # context summary of the PR and ticket requirements.
    # fetch_pr_node runs in parallel to get structured file data needed
    # to split work into per-file parallel review steps.
    ctx.logger.info("📡 Step 1/4: Context Builder Agent + structured PR fetch (parallel)")

    context_result, pr_data = await ctx.parallel(
        context_builder_agent.run(
            CONTEXT_BUILDER_USER_PROMPT.format(
                pr_url=pr_url,
                ticket_url=ticket_url or "No ticket URL provided",
            ),
            context=ctx,
        ),
        ctx.step(fetch_pr_node, pr_url=pr_url),
    )

    context_summary: str = context_result.output
    ctx.state.set("context_summary", context_summary)
    ctx.state.set("pr_data", pr_data)

    file_count = pr_data["changed_files"]
    ctx.logger.info(f"✅ Context built — PR #{pr_data['pr_number']} · {file_count} files")

    print("\n" + "=" * 60)
    print("🤖 CONTEXT BUILDER AGENT OUTPUT")
    print("=" * 60)
    print(context_summary)
    print("=" * 60 + "\n")

    if file_count > PR_SIZE_WARNING_THRESHOLD:
        ctx.logger.warning(
            f"⚠️ Large PR: {file_count} files. Per-file parallel reviews will cover all of them."
        )

    # ── STEP 2: Tech stack detection ──────────────────────────────────────────
    ctx.logger.info("🔍 Step 2/4: Detecting tech stack")
    tech_stack = await ctx.step(detect_tech_stack_node, files=pr_data["files"])
    ctx.state.set("tech_stack", tech_stack)
    ctx.logger.info(
        f"✅ Tech stack: {tech_stack.get('languages')} | Frameworks: {tech_stack.get('frameworks')}"
    )

    # ── STEP 3: Per-file reviews + security review — all in parallel ──────────
    # Each file review sees exactly one file's diff → no hallucination possible.
    # Security review sees all diffs together for cross-file vulnerability detection.
    reviewable_files = [f for f in pr_data["files"] if f.get("has_patch")]
    ctx.logger.info(
        f"🔎 Step 3/4: Reviewing {len(reviewable_files)}/{file_count} files in parallel "
        f"+ security review"
    )

    pr_context = {
        "title": pr_data["title"],
        "description": pr_data["description"],
        "repo": pr_data["repo"],
    }
    # Minimal ticket context for per-file prompts (full context goes to reviewer_agent)
    ticket_context: Dict[str, Any] = {"available": False}

    file_review_steps = [
        ctx.step(
            review_file_node,
            file_data=f,
            pr_context=pr_context,
            tech_stack=tech_stack,
            ticket_context=ticket_context,
        )
        for f in reviewable_files
    ]
    security_step = ctx.step(
        security_review_node,
        files=reviewable_files,
        pr_context=pr_context,
        tech_stack=tech_stack,
        ticket_context=ticket_context,
    )

    if file_review_steps:
        all_results = await ctx.parallel(*file_review_steps, security_step)
        file_reviews = list(all_results[:-1])
        security_review = all_results[-1]
    else:
        security_review = await security_step
        file_reviews = []

    ctx.state.set("file_reviews", file_reviews)
    ctx.state.set("security_review", security_review)

    total_findings = sum(len(fr.get("findings", [])) for fr in file_reviews)
    ctx.logger.info(
        f"✅ Reviews complete: {total_findings} findings across {len(file_reviews)} files · "
        f"security risk={security_review.get('overall_risk')}"
    )

    print("\n" + "=" * 60)
    print("📋 PER-FILE REVIEW RESULTS")
    print("=" * 60)
    for fr in file_reviews:
        findings = fr.get("findings", [])
        print(f"  {fr['filename']} — {len(findings)} finding(s): {fr.get('summary', '')}")
    print(f"\n🔒 Security Risk: {security_review.get('overall_risk', 'unknown').upper()}")
    print(f"   {security_review.get('summary', '')}")
    print(f"\nTotal findings: {total_findings}")
    print("=" * 60 + "\n")

    # ── STEP 4: reviewer_agent synthesizes everything into the final report ────
    # The agent gets the full context summary (ticket requirements, PR overview)
    # plus all structured per-file findings and security findings.
    # It does NOT need to re-read the code — findings are already extracted.
    ctx.logger.info("📝 Step 4/4: Reviewer Agent synthesizing final report")

    severity_counts: Dict[str, int] = {"critical": 0, "major": 0, "minor": 0, "nitpick": 0}
    for fr in file_reviews:
        for finding in fr.get("findings", []):
            sev = finding.get("severity", "minor")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
    for finding in security_review.get("findings", []):
        sev = finding.get("severity", "minor")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    file_findings_text = ""
    for fr in file_reviews:
        file_findings_text += (
            f"\n**{fr['filename']}** ({fr.get('language', 'unknown')}) — {fr.get('summary', '')}\n"
        )
        for finding in fr.get("findings", []):
            loc = f" ({finding['line_reference']})" if finding.get("line_reference") else ""
            file_findings_text += (
                f"  - [{finding['severity'].upper()}] {finding['category']}: "
                f"{finding['description']} → {finding['suggestion']}{loc}\n"
            )
        if not fr.get("findings"):
            file_findings_text += "  - No issues found\n"

    sec_text = (
        f"Overall Risk: {security_review.get('overall_risk', 'unknown').upper()}\n"
        f"{security_review.get('summary', '')}\n"
    )
    for finding in security_review.get("findings", []):
        loc = f" ({finding['line_reference']})" if finding.get("line_reference") else ""
        sec_text += f"  - [{finding['severity'].upper()}] {finding['description']} → {finding['suggestion']}{loc}\n"

    tech_text = (
        f"Languages: {', '.join(tech_stack.get('languages', []) or ['unknown'])}\n"
        f"Frameworks: {', '.join(tech_stack.get('frameworks', []) or ['none'])}\n"
        f"Tests in PR: {'Yes' if tech_stack.get('test_files_present') else 'No'}\n"
        f"Notes: {tech_stack.get('notes', '')}"
    )

    pr_meta_text = (
        f"Title: {pr_data.get('title', '')}\n"
        f"Author: {pr_data.get('author', '')}\n"
        f"Repo: {pr_data.get('repo', '')}\n"
        f"PR #: {pr_data.get('pr_number', '')}\n"
        f"State: {pr_data.get('state', '')}\n"
        f"Description: {(pr_data.get('description', '') or '')[:500]}\n"
        f"Files changed: {pr_data.get('changed_files', 0)} "
        f"(+{pr_data.get('additions', 0)} / -{pr_data.get('deletions', 0)})"
    )

    synthesis_message = f"""Synthesize the following code review findings into a final Markdown report.

## PR Metadata
{pr_meta_text}

## PR + Ticket Context (from Context Builder Agent)
{context_summary}

## Tech Stack
{tech_text}

## Per-File Review Findings ({len(file_reviews)} files reviewed)
Severity summary: {severity_counts}
{file_findings_text}

## Security Review
{sec_text}

Write a complete, professional Markdown report with executive summary, findings grouped by severity, \
security section, and a clear merge recommendation (APPROVE / REQUEST CHANGES / BLOCK)."""

    report_result = await reviewer_agent.run(synthesis_message, context=ctx)
    report: str = report_result.output

    print("\n" + "=" * 60)
    print("🤖 REVIEWER AGENT OUTPUT")
    print("=" * 60)
    print(report)
    print("=" * 60 + "\n")

    # Save report
    saved_report_path = None
    try:
        match = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if match:
            owner, repo_name, pr_number = match.groups()
            reports_dir = Path("reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_path = reports_dir / f"{owner}_{repo_name}_pr_{pr_number}_review.md"
            header = (
                f"# Code Review Report\n\n"
                f"**PR**: {pr_url}\n"
                f"**Ticket**: {ticket_url or 'N/A'}\n"
                f"**Files reviewed**: {len(file_reviews)}/{file_count}\n"
                f"**Security risk**: {security_review.get('overall_risk', 'unknown').upper()}\n"
                f"**Findings**: {severity_counts}\n\n"
                f"---\n\n"
            )
            with open(report_path, "w") as f:
                f.write(header + report)
            ctx.logger.info(f"📄 Report saved to: {report_path}")
            saved_report_path = str(report_path)
    except Exception as e:
        ctx.logger.warning(f"⚠️ Failed to save report: {e}")

    ctx.state.set("status", "completed")
    ctx.logger.info("🎉 Code review workflow complete")

    return {
        "status": "success",
        "pr_url": pr_url,
        "ticket_url": ticket_url,
        "pr_number": pr_data["pr_number"],
        "repo": pr_data["repo"],
        "files_reviewed": len(file_reviews),
        "total_files": file_count,
        "security_risk": security_review.get("overall_risk", "unknown"),
        "severity_counts": severity_counts,
        "tech_stack": tech_stack,
        "context_summary": context_summary,
        "report": report,
        "report_file": saved_report_path,
    }


__all__ = ["code_reviewer_workflow"]
