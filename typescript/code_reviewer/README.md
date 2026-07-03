# Code Reviewer Agent (TypeScript)

An AI-powered code review agent that analyzes GitHub pull requests and linked tickets to deliver comprehensive, context-aware reviews.

## What it does

- **Review pull requests** — Fetches PR diffs from GitHub and reviews every changed file for correctness, quality, and security issues.
- **Align with tickets** — Cross-references the PR against a linked Jira or Linear ticket to flag missing requirements.
- **Produce a merge recommendation** — Synthesizes all findings into a Markdown report with an APPROVE / REQUEST CHANGES / BLOCK verdict.

## Key concepts

- **Context builder + reviewer agents** — One agent gathers PR/ticket context using tools (`prFetcher`, `jiraTicketFetcher`, `linearTicketFetcher`); a second agent synthesizes the final report.
- **Parallel per-file review** — `reviewFileNode` runs once per changed file, all in parallel, alongside a cross-file `securityReviewNode`.

## Setup

1. Install Node.js 22+:
   ```bash
   node --version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template typescript/code_reviewer my-code-reviewer
   cd my-code-reviewer
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Set up environment variables (`GITHUB_TOKEN` is required; Jira/Linear credentials are optional):
   ```bash
   cp .env.example .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```
