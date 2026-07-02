import os
import re
import httpx

from agnt5 import (
    BackoffPolicy,
    BackoffType,
    function,
    FunctionContext,
    lm,
    RetryPolicy,
)

from code_reviewer.models import FileReview, SecurityReview, TechStack
from code_reviewer.prompts import (
    SYNTHESIZER_USER_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    FILE_REVIEWER_SYSTEM_PROMPT,
    FILE_REVIEWER_USER_PROMPT,
    SECURITY_REVIEWER_SYSTEM_PROMPT,
    SECURITY_REVIEWER_USER_PROMPT,
    REPORT_SYNTHESIZER_SYSTEM_PROMPT,
    REPORT_SYNTHESIZER_USER_PROMPT,
)


@function(
    name="call_jira_api",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL, multiplier=2.0),
)
async def call_jira_api(ctx: FunctionContext, url: str, auth: tuple) -> dict:
    """
    Fetch Jira issue data using REST API v3.
    Automatically retries on transient errors.
    """
    ctx.logger.info(f"📡 Fetching Jira issue from {url}")
    async with httpx.AsyncClient(auth=auth, timeout=20.0) as client:
        try:
            response = await client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            ctx.logger.info(f"✅ Jira API response OK: {response.status_code}")
            return response.json()
        except httpx.HTTPError as e:
            ctx.logger.error(f"❌ Jira API request failed: {e}")
            raise


@function(
    name="call_linear_api",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL, multiplier=2.0),
)
async def call_linear_api(ctx: FunctionContext, ticket_id: str, linear_token: str) -> dict:
    """
    Fetch Linear issue data using GraphQL API.
    Retries automatically with exponential backoff.
    """
    ctx.logger.info(f"📡 Fetching Linear issue {ticket_id}")
    url = "https://api.linear.app/graphql"
    headers = {
        "Authorization": linear_token,
        "Content-Type": "application/json",
    }

    query = {
        "query": f"""
        {{
            issue(id: "{ticket_id}") {{
                id
                identifier
                title
                description
                url
                state {{ name }}
                assignee {{ name }}
                team {{ name key }}
                priority
                createdAt
                updatedAt
                dueDate
            }}
        }}
        """
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(url, headers=headers, json=query)
            response.raise_for_status()
            ctx.logger.info(f"✅ Linear API response OK: {response.status_code}")
            ctx.logger.info(f"📦 Linear API response data: {response.json()}")
            return response.json()
        except httpx.HTTPError as e:
            ctx.logger.error(f"❌ Linear API request failed: {e}")
            raise


@function(
    name="call_github_api",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL, multiplier=2.0),
)
async def call_github_api(ctx: FunctionContext, url: str, headers: dict) -> dict:
    """
    Fetch GitHub PR metadata including changed files using a single API call.
    """
    ctx.logger.info(f"📡 Fetching GitHub data from {url}")
    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            ctx.logger.info(f"✅ GitHub API response OK: {response.status_code}")
            return response.json()
        except httpx.HTTPError as e:
            ctx.logger.error(f"❌ GitHub API request failed: {e}")
            raise


@function(
    name="synthesize_review_report",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def synthesize_review_report(ctx: FunctionContext, code_review: str) -> str:
    """
    Synthesize a concise code review report from detailed findings.
    """
    ctx.logger.info("📝 Synthesizing code review report")

    try:
        response = await lm.generate(
            model="openai/gpt-4.1-mini",
            system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": SYNTHESIZER_USER_PROMPT.format(
                        code_review=code_review
                    ),
                },
            ],
            temperature=0,
        )

        report = response.text
        ctx.logger.info("✅ Synthesis complete")

        return report
    except Exception as e:
        ctx.logger.error(f"❌ Synthesis failed: {e}")
        raise


LANGUAGE_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript/JSX", ".tsx": "TypeScript/TSX", ".java": "Java",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
    ".kt": "Kotlin", ".scala": "Scala", ".sh": "Shell",
    ".html": "HTML", ".css": "CSS", ".sql": "SQL", ".r": "R",
}

FRAMEWORK_INDICATORS = {
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "express": "Express.js", "react": "React", "vue": "Vue.js",
    "angular": "Angular", "spring": "Spring Boot", "rails": "Ruby on Rails",
    "laravel": "Laravel", "next": "Next.js", "nuxt": "Nuxt.js",
    "pytest": "pytest", "jest": "Jest", "sqlalchemy": "SQLAlchemy",
    "prisma": "Prisma", "mongoose": "Mongoose", "celery": "Celery",
    "graphql": "GraphQL", "grpc": "gRPC",
}


@function(
    name="detect_tech_stack_node",
    retries=RetryPolicy(max_attempts=2),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def detect_tech_stack_node(ctx: FunctionContext, files: list) -> dict:
    """Detect languages, frameworks, and tech stack from PR file list."""
    languages: set[str] = set()
    frameworks: set[str] = set()
    config_files: list[str] = []
    has_tests = False

    for f in files:
        filename: str = f.get("filename", "")
        patch: str = f.get("patch", "") or ""

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in LANGUAGE_MAP:
            languages.add(LANGUAGE_MAP[ext])

        name_lower = filename.lower()
        if any(x in name_lower for x in ["test", "spec", "_test.", ".test."]):
            has_tests = True

        if any(name_lower.endswith(c) for c in [
            "requirements.txt", "package.json", "go.mod", "cargo.toml",
            "gemfile", "composer.json", "pom.xml", "build.gradle",
            ".env.example", "dockerfile", "docker-compose.yml",
        ]):
            config_files.append(filename)

        content = (filename + " " + patch).lower()
        for indicator, framework in FRAMEWORK_INDICATORS.items():
            if indicator in content:
                frameworks.add(framework)

    notes = []
    if not has_tests:
        notes.append("No test files detected in this PR")
    if len(files) > 20:
        notes.append(f"Large PR: {len(files)} files changed")

    stack = TechStack(
        languages=sorted(languages),
        frameworks=sorted(frameworks),
        test_files_present=has_tests,
        config_files=config_files,
        notes="; ".join(notes) if notes else "Standard PR size",
    )

    ctx.logger.info(f"🔍 Tech stack: {stack.languages} | Frameworks: {stack.frameworks}")
    return stack.model_dump()


@function(
    name="fetch_pr_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL, multiplier=2.0),
)
async def fetch_pr_node(ctx: FunctionContext, pr_url: str) -> dict:
    """Fetch PR metadata and ALL changed files (paginated) from GitHub API."""
    import re as _re
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("Missing GITHUB_TOKEN in environment variables.")

    match = _re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        raise ValueError(f"Invalid PR URL: {pr_url}")

    owner, repo, pr_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    ctx.logger.info(f"📡 Fetching PR #{pr_number} from {owner}/{repo}")
    data = await call_github_api(ctx, url=api_url, headers=headers)

    # Paginate through ALL changed files (GitHub caps at 30/page by default)
    files: list = []
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        page_url = f"{files_url}?per_page=100&page=1"
        while page_url:
            ctx.logger.info(f"📄 Fetching files page: {page_url}")
            resp = await client.get(page_url)
            resp.raise_for_status()
            files.extend(resp.json())
            # Follow GitHub Link header for next page
            link_header = resp.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                part = part.strip()
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
            page_url = next_url

    ctx.logger.info(f"✅ Fetched {len(files)} files across all pages")

    result = {
        "repo": f"{owner}/{repo}",
        "pr_number": int(pr_number),
        "title": data.get("title", ""),
        "author": data.get("user", {}).get("login", ""),
        "state": data.get("state", ""),
        "description": data.get("body", "") or "",
        "changed_files": data.get("changed_files", 0),
        "additions": data.get("additions", 0),
        "deletions": data.get("deletions", 0),
        "files": [
            {
                "filename": f.get("filename", ""),
                "status": f.get("status", ""),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "patch": f.get("patch", "") or "",
                "has_patch": bool(f.get("patch")),
            }
            for f in files
        ],
    }

    ctx.logger.info(f"✅ PR #{pr_number} fetched: {len(files)} files, +{result['additions']} -{result['deletions']}")
    return result


@function(
    name="fetch_ticket_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL, multiplier=2.0),
)
async def fetch_ticket_node(ctx: FunctionContext, ticket_url: str) -> dict:
    """Fetch ticket data from Jira or Linear, auto-detected from URL."""
    import re as _re

    if not ticket_url or not ticket_url.strip():
        ctx.logger.info("No ticket URL provided, skipping ticket fetch")
        return {"available": False, "reason": "No ticket URL provided"}

    if "atlassian.net" in ticket_url:
        jira_email = os.getenv("JIRA_EMAIL")
        jira_token = os.getenv("JIRA_API_TOKEN")
        jira_domain = os.getenv("JIRA_DOMAIN")

        if not all([jira_email, jira_token, jira_domain]):
            ctx.logger.warning("Missing Jira credentials")
            return {"available": False, "reason": "Missing Jira credentials"}

        match = _re.search(r"/browse/([A-Z0-9\-]+)", ticket_url)
        if not match:
            return {"available": False, "reason": f"Invalid Jira URL: {ticket_url}"}

        ticket_key = match.group(1)
        api_url = f"{jira_domain}/rest/api/3/issue/{ticket_key}"
        data = await call_jira_api(ctx, url=api_url, auth=(jira_email, jira_token))
        fields = data.get("fields", {})

        from code_reviewer.utils import parse_adf
        description = parse_adf(fields.get("description", {})).strip()

        ctx.logger.info(f"✅ Jira ticket {ticket_key} fetched")
        return {
            "available": True,
            "source": "jira",
            "key": data.get("key"),
            "summary": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "description": description or "No description",
            "url": ticket_url,
        }

    elif "linear.app" in ticket_url:
        linear_token = os.getenv("LINEAR_API_TOKEN")
        if not linear_token:
            ctx.logger.warning("Missing LINEAR_API_TOKEN")
            return {"available": False, "reason": "Missing LINEAR_API_TOKEN"}

        match = _re.search(r"/issue/([A-Z0-9\-]+)", ticket_url)
        if not match:
            return {"available": False, "reason": f"Invalid Linear URL: {ticket_url}"}

        ticket_key = match.group(1)
        data = await call_linear_api(ctx, ticket_id=ticket_key, linear_token=linear_token)
        issue = data.get("data", {}).get("issue")

        if not issue:
            return {"available": False, "reason": f"Linear issue {ticket_key} not found"}

        ctx.logger.info(f"✅ Linear ticket {ticket_key} fetched")
        return {
            "available": True,
            "source": "linear",
            "key": issue["identifier"],
            "summary": issue["title"],
            "status": issue.get("state", {}).get("name", ""),
            "priority": str(issue.get("priority", "")) or "Not set",
            "description": issue.get("description", "No description") or "No description",
            "url": issue["url"],
        }

    else:
        return {"available": False, "reason": f"Unrecognized ticket platform: {ticket_url}"}


@function(
    name="review_file_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def review_file_node(
    ctx: FunctionContext,
    file_data: dict,
    pr_context: dict,
    tech_stack: dict,
    ticket_context: dict,
) -> dict:
    """Review a single file's diff and return structured findings."""
    filename = file_data.get("filename", "unknown")
    patch = file_data.get("patch", "")

    if not patch:
        ctx.logger.info(f"⏭️ Skipping {filename} — no diff available")
        return FileReview(
            filename=filename,
            language="unknown",
            findings=[],
            summary="No diff available for this file — binary or renamed file.",
        ).model_dump()

    ctx.logger.info(f"🔍 Reviewing {filename}")

    ticket_summary = "No ticket provided"
    if ticket_context.get("available"):
        ticket_summary = f"{ticket_context.get('key', '')}: {ticket_context.get('summary', '')} — {ticket_context.get('description', '')[:300]}"

    tech_str = f"Languages: {', '.join(tech_stack.get('languages', []))} | Frameworks: {', '.join(tech_stack.get('frameworks', []))}"

    response = await lm.generate(
        model="openai/gpt-4.1-mini",
        system_prompt=FILE_REVIEWER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": FILE_REVIEWER_USER_PROMPT.format(
                pr_title=pr_context.get("title", ""),
                pr_description=(pr_context.get("description", "") or "")[:500],
                tech_stack=tech_str,
                ticket_context=ticket_summary,
                filename=filename,
                status=file_data.get("status", "modified"),
                additions=file_data.get("additions", 0),
                deletions=file_data.get("deletions", 0),
                patch=patch,
            ),
        }],
        temperature=0,
        response_format=FileReview,
    )

    result = response.structured_output
    if result is None and response.text:
        try:
            import json as _json
            result = _json.loads(response.text)
        except Exception:
            pass

    if result is None:
        ctx.logger.warning(f"⚠️ No structured output for {filename}, using empty review")
        return FileReview(
            filename=filename,
            language="unknown",
            findings=[],
            summary="Structured output unavailable for this file.",
        ).model_dump()

    review = FileReview(**result) if isinstance(result, dict) else result
    ctx.logger.info(f"✅ {filename}: {len(review.findings)} findings")
    return review.model_dump()


@function(
    name="security_review_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def security_review_node(
    ctx: FunctionContext,
    files: list,
    pr_context: dict,
    tech_stack: dict,
    ticket_context: dict,
) -> dict:
    """Dedicated security review pass across all changed files."""
    ctx.logger.info("🔒 Running security review pass")

    reviewable = [f for f in files if f.get("patch")]
    if not reviewable:
        ctx.logger.info("No diffs available for security review")
        return SecurityReview(
            findings=[],
            overall_risk="low",
            summary="No diffs available to review.",
        ).model_dump()

    all_diffs = "\n\n".join(
        f"### {f['filename']} (+{f.get('additions',0)} -{f.get('deletions',0)})\n```\n{f['patch']}\n```"
        for f in reviewable[:15]  # cap at 15 files to avoid token limits
    )

    tech_str = f"Languages: {', '.join(tech_stack.get('languages', []))} | Frameworks: {', '.join(tech_stack.get('frameworks', []))}"
    ticket_summary = "No ticket provided"
    if ticket_context.get("available"):
        ticket_summary = f"{ticket_context.get('key', '')}: {ticket_context.get('summary', '')}"

    response = await lm.generate(
        model="openai/gpt-4.1-mini",
        system_prompt=SECURITY_REVIEWER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": SECURITY_REVIEWER_USER_PROMPT.format(
                pr_title=pr_context.get("title", ""),
                repo=pr_context.get("repo", ""),
                tech_stack=tech_str,
                all_diffs=all_diffs,
                ticket_context=ticket_summary,
            ),
        }],
        temperature=0,
        response_format=SecurityReview,
    )

    result = response.structured_output
    if result is None and response.text:
        try:
            import json as _json
            result = _json.loads(response.text)
        except Exception:
            pass

    if result is None:
        ctx.logger.warning("⚠️ No structured output for security review, using empty result")
        return SecurityReview(
            findings=[],
            overall_risk="low",
            summary="Structured output unavailable for security review.",
        ).model_dump()

    review = SecurityReview(**result) if isinstance(result, dict) else result
    ctx.logger.info(f"🔒 Security review done: {len(review.findings)} findings, risk={review.overall_risk}")
    return review.model_dump()


@function(
    name="build_report_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def build_report_node(
    ctx: FunctionContext,
    file_reviews: list,
    security_review: dict,
    pr_data: dict,
    ticket_data: dict,
    tech_stack: dict,
) -> str:
    """Synthesize all file reviews and security review into a final Markdown report."""
    ctx.logger.info("📝 Building final report")

    # Count severity across all findings
    severity_counts: dict[str, int] = {"critical": 0, "major": 0, "minor": 0, "nitpick": 0}
    for fr in file_reviews:
        for finding in fr.get("findings", []):
            sev = finding.get("severity", "minor")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
    for finding in security_review.get("findings", []):
        sev = finding.get("severity", "minor")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Format file reviews for prompt
    file_reviews_text = ""
    for fr in file_reviews:
        findings = fr.get("findings", [])
        file_reviews_text += f"\n**{fr['filename']}** ({fr.get('language', 'unknown')}) — {fr.get('summary', '')}\n"
        for f in findings:
            file_reviews_text += f"  - [{f['severity'].upper()}] {f['category']}: {f['description']} → {f['suggestion']}"
            if f.get("line_reference"):
                file_reviews_text += f" ({f['line_reference']})"
            file_reviews_text += "\n"
        if not findings:
            file_reviews_text += "  - No issues found\n"

    # Format security review
    sec_findings = security_review.get("findings", [])
    security_text = f"Overall Risk: {security_review.get('overall_risk', 'unknown').upper()}\n{security_review.get('summary', '')}\n"
    for f in sec_findings:
        security_text += f"  - [{f['severity'].upper()}] {f['description']} → {f['suggestion']}\n"
        if f.get("line_reference"):
            security_text += f"    Location: {f['line_reference']}\n"

    pr_metadata = (
        f"Title: {pr_data.get('title', '')}\n"
        f"Author: {pr_data.get('author', '')}\n"
        f"Repo: {pr_data.get('repo', '')}\n"
        f"PR #{pr_data.get('pr_number', '')}\n"
        f"Files: {pr_data.get('changed_files', 0)} changed (+{pr_data.get('additions', 0)} -{pr_data.get('deletions', 0)})\n"
        f"Description: {(pr_data.get('description', '') or '')[:400]}\n"
        f"Severity counts: {severity_counts}"
    )

    ticket_text = "No ticket provided"
    if ticket_data.get("available"):
        ticket_text = (
            f"[{ticket_data.get('source', '').upper()}] {ticket_data.get('key', '')}: {ticket_data.get('summary', '')}\n"
            f"Status: {ticket_data.get('status', '')} | Priority: {ticket_data.get('priority', '')}\n"
            f"Description: {(ticket_data.get('description', '') or '')[:500]}"
        )

    tech_text = (
        f"Languages: {', '.join(tech_stack.get('languages', []) or ['unknown'])}\n"
        f"Frameworks: {', '.join(tech_stack.get('frameworks', []) or ['none detected'])}\n"
        f"Tests in PR: {'Yes' if tech_stack.get('test_files_present') else 'No'}\n"
        f"Notes: {tech_stack.get('notes', '')}"
    )

    response = await lm.generate(
        model="openai/gpt-4.1-mini",
        system_prompt=REPORT_SYNTHESIZER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": REPORT_SYNTHESIZER_USER_PROMPT.format(
                pr_metadata=pr_metadata,
                ticket_context=ticket_text,
                tech_stack=tech_text,
                file_reviews=file_reviews_text,
                security_review=security_text,
            ),
        }],
        temperature=0,
    )

    ctx.logger.info("✅ Final report built")
    return response.text


__all__ = [
    "call_jira_api",
    "call_linear_api",
    "call_github_api",
    "synthesize_review_report",
    "detect_tech_stack_node",
    "fetch_pr_node",
    "fetch_ticket_node",
    "review_file_node",
    "security_review_node",
    "build_report_node",
]