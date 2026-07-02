# HITL Deep Research — AGNT5 Template

A research pipeline that combines three specialized AI agents with a **human-in-the-loop approval gate** before any research begins.

## What it does

1. **Plan** — A scoping agent analyzes your topic and produces a structured research plan.
2. **Approve** — The workflow pauses and presents the plan to you. You can approve it, edit it, or reject it. This pause is durable — it survives restarts and waits as long as needed.
3. **Research** — A research agent executes the approved plan using web and Wikipedia tools.
4. **Write** — A writing agent synthesizes the findings into a polished report.

## Key concepts

- **Human-in-the-loop (HITL)** — `ctx.wait_for_user()` suspends the workflow at a checkpoint and resumes only after a human responds. The state is fully durable.
- **Durable workflows** — Each stage is a recorded step. If the worker restarts mid-run, the workflow replays from the last completed step without repeating side effects.
- **Specialized agents** — Scoping, Research, and Writing agents each have a focused role, keeping concerns cleanly separated.

## Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template hitl-deep-research my-deep-research
   cd my-deep-research
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Set up environment variables:
   ```bash
   cat > .env << EOF
   OPENAI_API_KEY=your_openai_api_key_here
   EOF
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev
   ```

When the workflow reaches the approval step, open the Dev Dashboard to review and approve the research plan before research begins.
