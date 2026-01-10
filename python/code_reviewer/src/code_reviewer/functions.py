import httpx

from agnt5 import (
    BackoffPolicy,
    BackoffType,
    function,
    FunctionContext,
    lm,
    RetryPolicy,
)

from code_reviewer.prompts import SYNTHESIZER_USER_PROMPT, SYNTHESIZER_SYSTEM_PROMPT


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
            data = response.json()

            if "files" not in data:
                files_url = f"{url}/files"
                ctx.logger.info(f"📄 Fetching changed files from {files_url}")
                files_resp = await client.get(files_url)
                files_resp.raise_for_status()
                data["files"] = files_resp.json()

            ctx.logger.info(f"✅ GitHub API response OK: {response.status_code}")
            return data
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
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
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


__all__ = [
    "call_jira_api",
    "call_linear_api",
    "call_github_api",
    "synthesize_review_report",
]