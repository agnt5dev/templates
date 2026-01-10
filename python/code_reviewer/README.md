# Code Reviewer Agent

> AI-powered code review agent that analyzes pull requests and tickets to deliver comprehensive, context-aware code reviews.

## Quick Start

```bash
agnt5 create --template python/code_reviewer
export GITHUB_TOKEN=ghp_...
export JIRA_EMAIL=your@email.com JIRA_API_TOKEN=... JIRA_DOMAIN=https://yourcompany.atlassian.net
agnt5 dev up
```

## What You Can Build

- **Automated PR Reviews**: Analyze pull requests for security vulnerabilities, performance issues, and code quality
- **Ticket-Aligned Reviews**: Verify code changes match Jira/Linear ticket requirements and acceptance criteria
- **Security & Performance Audits**: Detect SQL injection, XSS, N+1 queries, and memory leaks automatically

## Installation

### Prerequisites

- Python 3.12+
- AGNT5 SDK
- GitHub access token
- Jira or Linear credentials (optional)

### Setup

```bash
# Clone or create from template
agnt5 create --template python/code_reviewer
cd code_reviewer

# Install dependencies
uv sync

# Configure environment variables
export GITHUB_TOKEN=ghp_your_github_token

# For Jira integration
export JIRA_EMAIL=your@email.com
export JIRA_API_TOKEN=your_jira_token
export JIRA_DOMAIN=https://yourcompany.atlassian.net

# For Linear integration
export LINEAR_API_TOKEN=your_linear_token

# Start the worker
agnt5 dev up
```

## Usage

### Via Workflow Client

Call the workflow programmatically:

```python
import asyncio
from code_reviewer.workflow import code_reviewer_workflow
from agnt5 import with_entity_context

@with_entity_context
async def main():
    result = await code_reviewer_workflow(
        pr_url="https://github.com/owner/repo/pull/123",
        ticket_url="https://yourcompany.atlassian.net/browse/PROJ-456"
    )

    print(f"Review Status: {result['status']}")
    print(f"Report saved to: {result['report_file']}")
    print(result['report'])

asyncio.run(main())
```

### Example Output

The workflow generates a structured markdown report saved to `/app/reports/`:

```
/app/reports/repo_pr_123_review.md
```

Report includes:
- Security vulnerability analysis
- Performance issue detection
- Code quality assessment
- Ticket requirement alignment
- Actionable feedback with file/line references

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub personal access token | Yes |
| `JIRA_EMAIL` | Jira account email | For Jira tickets |
| `JIRA_API_TOKEN` | Jira API token | For Jira tickets |
| `JIRA_DOMAIN` | Jira instance URL | For Jira tickets |
| `LINEAR_API_TOKEN` | Linear API token | For Linear tickets |

### Workflow Parameters

```python
code_reviewer_workflow(
    pr_url: str,        # GitHub PR URL
    ticket_url: str     # Jira or Linear ticket URL
)
```

<details>
<summary>Architecture</summary>

### Multi-Agent System

The workflow orchestrates three specialized agents:

#### 1. Context Builder Agent
- **Tools**: `pr_fetcher`, `jira_ticket_fetcher`, `linear_ticket_fetcher`, `detect_ticket_source`
- **Role**: Gathers PR metadata, file diffs, and ticket details
- **Output**: Enriched context combining code changes and requirements

#### 2. Reviewer Agent
- **Tools**: None (analyzes context from previous step)
- **Role**: Performs deep code analysis for security, performance, quality, and standards
- **Output**: Structured findings with file/line references

#### 3. Synthesizer Function
- **Type**: Stateless function
- **Role**: Compiles review findings into a final markdown report
- **Output**: Formatted review report

### Workflow Steps

```
1. Context Building
   └─> Fetch PR details (title, author, changed files, diffs)
   └─> Detect ticket source (Jira/Linear)
   └─> Fetch ticket details (requirements, acceptance criteria)
   └─> Combine into enriched context

2. Code Review
   └─> Analyze security vulnerabilities
   └─> Check performance patterns
   └─> Evaluate code quality
   └─> Verify ticket alignment

3. Report Synthesis
   └─> Generate markdown report
   └─> Save to /app/reports/
   └─> Return structured result
```

### Entity State Management

The `CodeReviewSession` entity tracks workflow state:
- `initial` → `context_building` → `code_review` → `synthesizing` → `completed`
- Stores context, review results, and generated report
- Enables resumable workflows and state inspection

</details>

## Troubleshooting

### Missing credentials error
```
EnvironmentError: Missing GITHUB_TOKEN in environment variables
```
**Solution**: Export required environment variables before starting the worker.

### Invalid PR/ticket URL
```
ValueError: Invalid PR URL: https://...
```
**Solution**: Ensure URLs match expected patterns:
- GitHub: `https://github.com/owner/repo/pull/123`
- Jira: `https://company.atlassian.net/browse/PROJ-123`
- Linear: `https://linear.app/team/issue/PROJ-123`

### Worker connection failed
```
🔗 Connecting to AGNT5 Coordinator... [FAILED]
```
**Solution**: Ensure coordinator is running and project ID in `agnt5.yaml` is correct.

### Large PR truncation
Large file diffs are automatically truncated to 100 lines per file to prevent token overflow. Adjust `max_patch_lines` parameter in `pr_fetcher` tool if needed.

## Customization

### Extend Review Criteria

Modify the review prompt in `src/code_reviewer/workflow.py:135-151` to add custom analysis:

```python
review_user_prompt = f"""Using the gathered context below, perform a thorough code review:

Focus on:
- Security vulnerabilities (SQL injection, XSS, auth flaws, secrets)
- Performance issues (N+1 queries, inefficient algorithms, memory leaks)
- Code quality (smells, duplications, complexity, maintainability)
- Standards (naming, formatting, documentation)
- Alignment with ticket requirements
- [YOUR CUSTOM CRITERIA HERE]
"""
```

### Add New Ticket Sources

Implement a new fetcher tool in `src/code_reviewer/tools.py`:

```python
@tool(auto_schema=True)
async def custom_ticket_fetcher(ctx: Context, ticket_url: str) -> dict:
    # Your implementation
    pass
```

Update `detect_ticket_source` to recognize the new platform.

### Related Templates

- **weather-agent**: Example of tool-based agentic workflows
- **text-to-sql**: Multi-step reasoning workflows with validation
- **pdf-questions**: Document analysis with context extraction

## License

MIT License - see [LICENSE](LICENSE) for details
