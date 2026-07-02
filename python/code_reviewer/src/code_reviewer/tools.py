import os
import re

import httpx
from agnt5 import Context, FunctionContext, tool
from agnt5._ids import generate_cid

from code_reviewer.functions import (
    call_jira_api,
    call_linear_api,
    call_github_api,
)

from code_reviewer.utils import parse_adf


def _make_fun_ctx(ctx: Context) -> FunctionContext:
    """Create a FunctionContext from an agent/workflow Context for calling @function helpers."""
    return FunctionContext(
        run_id=ctx.run_id,
        correlation_id=generate_cid(),
        parent_correlation_id=getattr(ctx, "_correlation_id", ""),
        runtime_context=getattr(ctx, "_runtime_context", None),
        trace_metadata=getattr(ctx, "_trace_metadata", None),
    )


@tool
async def jira_ticket_fetcher(ctx: Context, ticket_url: str) -> dict:
    """
    Fetch Jira issue details via REST API (v3).

    Args:
        ctx: FunctionContext for logging
        ticket_url: Full Jira ticket URL
            (e.g., https://company.atlassian.net/browse/PROJ-123)

    Returns:
        dict: Normalized ticket data with keys: key, summary, status,
            assignee, priority, project, description, url

    Raises:
        EnvironmentError: If Jira credentials are missing
        ValueError: If ticket URL is invalid
    """
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_domain = os.getenv("JIRA_DOMAIN")

    if not all([jira_email, jira_token, jira_domain]):
        error_msg = ("❌ Missing Jira credentials "
                     "(JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN)")
        ctx.logger.error(error_msg)
        raise EnvironmentError("Missing Jira credentials in environment.")

    match = re.search(r"/browse/([A-Z0-9\-]+)", ticket_url)
    if not match:
        ctx.logger.error(f"❌ Invalid Jira ticket URL: {ticket_url}")
        raise ValueError(f"Invalid Jira ticket URL: {ticket_url}")

    ticket_key = match.group(1)
    api_url = f"{jira_domain}/rest/api/3/issue/{ticket_key}"

    ctx.logger.info(f"🚀 Fetching Jira issue {ticket_key} from {api_url}")
    fun_ctx = _make_fun_ctx(ctx)
    data = await call_jira_api(
        fun_ctx, url=api_url, auth=(jira_email, jira_token)
    )
    fields = data.get("fields", {})

    description_text = parse_adf(fields.get("description", {})).strip()

    result = {
        "key": data.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "assignee": (
            fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None
        ),
        "priority": fields.get("priority", {}).get("name"),
        "project": fields.get("project", {}).get("name"),
        "description": description_text or None,
        "url": ticket_url,
    }

    ctx.logger.info(f"✅ Jira issue {ticket_key} fetched successfully.")
    return result


@tool
async def linear_ticket_fetcher(ctx: Context, ticket_url: str) -> dict:
    """
    Fetch Linear issue details using GraphQL API.

    Args:
        ctx: FunctionContext for logging
        ticket_url: Full Linear ticket URL
            (e.g., https://linear.app/team/issue/PROJ-123)

    Returns:
        dict: Normalized ticket data with keys: key, summary, status,
            assignee, priority, project, description, url

    Raises:
        EnvironmentError: If LINEAR_API_TOKEN is missing
        ValueError: If ticket URL is invalid or issue not found
    """
    linear_token = os.getenv("LINEAR_API_TOKEN")

    if not linear_token:
        ctx.logger.error("❌ Missing LINEAR_API_TOKEN")
        raise EnvironmentError("Missing LINEAR_API_TOKEN in environment variables.")

    match = re.search(r"/issue/([A-Z0-9\-]+)", ticket_url)
    if not match:
        ctx.logger.error(f"❌ Invalid Linear ticket URL: {ticket_url}")
        raise ValueError(f"Invalid Linear ticket URL: {ticket_url}")

    ticket_key = match.group(1)
    ctx.logger.info(f"🚀 Fetching Linear issue {ticket_key}")

    fun_ctx = _make_fun_ctx(ctx)
    data = await call_linear_api(
        fun_ctx, ticket_id=ticket_key, linear_token=linear_token
    )
    issue = data.get("data", {}).get("issue")

    if not issue:
        ctx.logger.error(f"❌ No issue found for Linear key: {ticket_key}")
        raise ValueError(f"No issue found for Linear key: {ticket_key}")

    result = {
        "key": issue["identifier"],
        "summary": issue["title"],
        "status": issue.get("state", {}).get("name"),
        "assignee": issue.get("assignee", {}).get("name"),
        "priority": str(issue.get("priority")) if issue.get("priority") else None,
        "project": issue.get("team", {}).get("name"),
        "description": issue.get("description"),
        "url": issue["url"],
    }

    ctx.logger.info(f"✅ Linear issue {ticket_key} fetched successfully.")
    return result


@tool
async def pr_fetcher(ctx: Context, pr_url: str) -> dict:
    """
    Fetch Pull Request metadata and ALL file diffs from GitHub REST API.

    Paginates through all changed files so no file is missed.

    Args:
        ctx: FunctionContext for logging
        pr_url: Full GitHub PR URL
            (e.g., https://github.com/owner/repo/pull/123)

    Returns:
        dict: PR data with keys: repo, pr_number, title, author, state,
            created_at, merged_at, description, changed_files, additions,
            deletions, files (full patches, all pages)

    Raises:
        EnvironmentError: If GITHUB_TOKEN is missing
        ValueError: If PR URL is invalid
    """
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        ctx.logger.error("❌ Missing GITHUB_TOKEN")
        raise EnvironmentError("Missing GITHUB_TOKEN in environment variables.")

    match = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        ctx.logger.error(f"❌ Invalid PR URL: {pr_url}")
        raise ValueError(f"Invalid PR URL: {pr_url}")

    owner, repo, pr_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    ctx.logger.info(f"🚀 Fetching PR #{pr_number} from {owner}/{repo}")

    fun_ctx = _make_fun_ctx(ctx)
    pr_meta = await call_github_api(fun_ctx, url=api_url, headers=headers)

    # Paginate through ALL changed files (GitHub returns 30/page by default)
    files: list = []
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        page_url = f"{files_url}?per_page=100&page=1"
        while page_url:
            ctx.logger.info(f"📄 Fetching files page: {page_url}")
            resp = await client.get(page_url)
            resp.raise_for_status()
            files.extend(resp.json())
            link_header = resp.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                part = part.strip()
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
            page_url = next_url

    result = {
        "repo": f"{owner}/{repo}",
        "pr_number": int(pr_number),
        "title": pr_meta.get("title"),
        "author": pr_meta.get("user", {}).get("login"),
        "state": pr_meta.get("state"),
        "created_at": pr_meta.get("created_at"),
        "merged_at": pr_meta.get("merged_at"),
        "description": pr_meta.get("body"),
        "changed_files": pr_meta.get("changed_files"),
        "additions": pr_meta.get("additions"),
        "deletions": pr_meta.get("deletions"),
        "files": [
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "changes": f.get("changes"),
                "patch": f.get("patch", "") or "",
                "has_patch": bool(f.get("patch")),
            }
            for f in files
        ],
    }

    ctx.logger.info(
        f"✅ PR #{pr_number} fetched: {len(files)} files across all pages, "
        f"+{pr_meta.get('additions', 0)} -{pr_meta.get('deletions', 0)}"
    )
    return result


@tool
async def detect_ticket_source(ctx: Context, ticket_url: str) -> str:
    """
    Determine ticketing platform (Jira or Linear) based on URL pattern.

    Args:
        ctx: FunctionContext for logging
        ticket_url: Ticket URL to analyze

    Returns:
        str: Tool name - "jira" or "linear"

    Raises:
        ValueError: If URL doesn't match known patterns
    """
    if "atlassian.net" in ticket_url:
        ctx.logger.info("🟦 Detected Jira ticket URL")
        return "jira"
    elif "linear.app" in ticket_url:
        ctx.logger.info("🟪 Detected Linear ticket URL")
        return "linear"
    else:
        ctx.logger.error(f"❌ Unsupported ticket URL: {ticket_url}")
        raise ValueError(f"Unsupported ticketing platform URL: {ticket_url}")


__all__ = [
    "jira_ticket_fetcher",
    "linear_ticket_fetcher",
    "pr_fetcher",
    "detect_ticket_source",
]