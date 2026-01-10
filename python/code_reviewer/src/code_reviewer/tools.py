import os
import re

from agnt5 import Context, FunctionContext, tool

from code_reviewer.functions import (
    call_jira_api,
    call_linear_api,
    call_github_api,
)

from code_reviewer.utils import parse_adf


@tool(auto_schema=True)
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
    fun_ctx = FunctionContext(run_id=ctx.run_id)
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


@tool(auto_schema=True)
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

    fun_ctx = FunctionContext(run_id=ctx.run_id)
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


@tool(auto_schema=True)
async def pr_fetcher(ctx: Context, pr_url: str, max_patch_lines: int = 100) -> dict:
    """
    Fetch Pull Request metadata and file diffs from GitHub REST API.

    Large patches are truncated to prevent token overflow. Each file patch
    is limited to max_patch_lines (default: 100 lines).

    Args:
        ctx: FunctionContext for logging
        pr_url: Full GitHub PR URL
            (e.g., https://github.com/owner/repo/pull/123)
        max_patch_lines: Maximum lines per file patch (default: 100)

    Returns:
        dict: PR data with keys: repo, pr_number, title, author, state,
            created_at, merged_at, description, changed_files, additions,
            deletions, files (with truncated patches)

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

    log_msg = f"🚀 Fetching PR #{pr_number} and changed files from {owner}/{repo}"
    ctx.logger.info(log_msg)

    fun_ctx = FunctionContext(run_id=ctx.run_id)
    pr_data_with_files = await call_github_api(
        fun_ctx, url=api_url, headers=headers
    )

    # Extract files from the response
    files = pr_data_with_files.get("files", [])

    def truncate_patch(patch: str, max_lines: int) -> str:
        """Truncate patch to max_lines, adding truncation notice if needed."""
        if not patch:
            return ""

        lines = patch.split("\n")
        if len(lines) <= max_lines:
            return patch

        truncated = "\n".join(lines[:max_lines])
        remaining = len(lines) - max_lines
        return f"{truncated}\n... [truncated {remaining} more lines]"

    result = {
        "repo": f"{owner}/{repo}",
        "pr_number": int(pr_number),
        "title": pr_data_with_files.get("title"),
        "author": pr_data_with_files.get("user", {}).get("login"),
        "state": pr_data_with_files.get("state"),
        "created_at": pr_data_with_files.get("created_at"),
        "merged_at": pr_data_with_files.get("merged_at"),
        "description": pr_data_with_files.get("body"),
        "changed_files": pr_data_with_files.get("changed_files"),
        "additions": pr_data_with_files.get("additions"),
        "deletions": pr_data_with_files.get("deletions"),
        "files": [
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "changes": f.get("changes"),
                "patch": truncate_patch(f.get("patch", ""), max_patch_lines),
                "truncated": len((f.get("patch", "")).split("\n")) > max_patch_lines,
            }
            for f in files
        ],
    }

    success_msg = (f"✅ Successfully fetched PR #{pr_number} "
                   f"with {len(result['files'])} files (patches truncated to {max_patch_lines} lines)")
    ctx.logger.info(success_msg)
    return result


@tool(auto_schema=True)
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