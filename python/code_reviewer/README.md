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

### Direct Invocation (development / testing)

```python
import asyncio
from code_reviewer.workflow import code_reviewer_workflow

async def main():
    result = await code_reviewer_workflow(
        pr_url="https://github.com/owner/repo/pull/123",
        ticket_url="https://yourcompany.atlassian.net/browse/PROJ-456",  # optional
    )

    print(f"PR #{result['pr_number']} — {result['repo']}")
    print(f"Files reviewed: {result['files_reviewed']}/{result['total_files']}")
    print(f"Security risk: {result['security_risk']}")
    if result.get("report_file"):
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
    pr_url: str,           # GitHub PR URL (required)
    ticket_url: str = ""   # Jira or Linear ticket URL (optional)
)
```

### Return Value

```python
{
    "status": "success",
    "pr_url": "https://github.com/...",
    "pr_number": 123,
    "repo": "owner/repo",
    "files_reviewed": 12,
    "total_files": 15,
    "security_risk": "medium",   # low | medium | high | critical
    "severity_counts": {"critical": 0, "major": 2, "minor": 5, "nitpick": 3},
    "tech_stack": {"languages": ["Python"], "frameworks": ["FastAPI"], ...},
    "context_summary": "...",
    "report": "# Code Review Report\n...",
    "report_file": "reports/owner_repo_pr_123_review.md"  # None if save failed
}
```

<details>
<summary>Architecture</summary>

### 4-Step Parallel Workflow

The workflow combines function nodes and LLM agents across four steps:

#### Agents
- **Context Builder** (`openai/gpt-4.1-mini`): Autonomously fetches PR metadata and ticket details using `pr_fetcher`, `jira_ticket_fetcher`, `linear_ticket_fetcher`, and `detect_ticket_source` tools. Produces a natural-language context summary.
- **Reviewer** (`openai/gpt-4.1-mini`): Synthesizes all structured findings (per-file reviews + security analysis) into a professional Markdown report with an APPROVE / REQUEST CHANGES / BLOCK recommendation.

#### Function Nodes
- **`fetch_pr_node`**: Fetches structured PR data (files, diffs, metadata) from the GitHub API.
- **`detect_tech_stack_node`**: Inspects changed file paths to identify languages, frameworks, and whether tests are included.
- **`review_file_node`**: Reviews a single file's diff for bugs, quality, and ticket alignment. One instance per reviewable file, all run in parallel.
- **`security_review_node`**: Cross-file vulnerability scan (SQL injection, XSS, secrets, etc.) running in parallel with per-file reviews.

### Workflow Steps

```
Step 1: Context + PR fetch (parallel)
   ├─> Context Builder Agent (PR summary + ticket requirements)
   └─> fetch_pr_node (structured file list + diffs)

Step 2: Tech stack detection
   └─> detect_tech_stack_node (languages, frameworks, test presence)

Step 3: Per-file reviews + security (all in parallel)
   ├─> review_file_node × N files (one per reviewable file)
   └─> security_review_node (cross-file vulnerability scan)

Step 4: Synthesis
   └─> Reviewer Agent (final Markdown report + merge recommendation)
   └─> Save to reports/<owner>_<repo>_pr_<number>_review.md
```

### Parallelism

Steps 1 and 3 use `ctx.parallel()` — the context agent and structured PR fetch run concurrently, and all per-file reviews plus the security scan run concurrently. Wall-clock time scales with the slowest individual file review, not the total number of files.

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

### Large PR warning
For PRs with more than 30 changed files, the workflow logs a warning and still reviews all reviewable files in parallel. If you need to limit scope, filter `pr_data["files"]` in `workflow.py` before the parallel review step.

## Customization

### Extend Review Criteria

Modify the per-file review prompt in `src/code_reviewer/prompts/__init__.py` to add custom analysis dimensions. The per-file reviewer checks one file at a time; the security reviewer covers all files together. To add a custom cross-file check, add a new `ctx.step(custom_review_node, ...)` call alongside the existing parallel steps in `workflow.py`.

### Change the LLM Model

Both agents are defined in `src/code_reviewer/agents.py`. Update the `model` parameter:

```python
context_builder_agent = Agent(
    name="context_builder",
    model="openai/gpt-4.1",  # upgrade to a larger model
    ...
)
```

### Add New Ticket Sources

Implement a new fetcher tool in `src/code_reviewer/tools.py`:

```python
@tool(auto_schema=True)
async def custom_ticket_fetcher(ctx: Context, ticket_url: str) -> dict:
    # Your implementation
    pass
```

Register it in the `context_builder_agent` tool list in `src/code_reviewer/agents.py` and update `detect_ticket_source` to recognize the new platform URL pattern.

### Related Templates

- **weather-agent**: Example of tool-based agentic workflows
- **text-to-sql**: Multi-step reasoning workflows with validation
- **pdf-questions**: Document analysis with context extraction

## License

MIT License - see [LICENSE](LICENSE) for details
