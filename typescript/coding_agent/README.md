# Coding Agent (TypeScript)

An autonomous test-driven development agent that writes, tests, and iteratively fixes Python code until all tests pass, using an E2B sandbox for execution.

## What it does

- **Plan then build** — Generates a synchronized dev plan and test plan from a task description before writing any code.
- **Test-driven iteration** — Writes tests first, then code; on failure, analyzes the pytest output and fixes the code, up to `max_retries` times.
- **Sandboxed execution** — Runs and tests all generated code inside an isolated E2B sandbox, never on the worker host.

## Key concepts

- **Multi-node workflow** — `plannerNode` → (`testGeneratorNode` → `codeGeneratorNode`) or (`errorAnalyzerNode` → `codeGeneratorNode`) → `codeSyncNode` → `installDepsNode` → `codeExecutorNode` → `finalResponseNode`.
- **Structured error feedback loop** — Each failed `pytest` run is parsed into a structured `ErrorAnalysis` that drives the next fix iteration, rather than regenerating code from scratch.

## Setup

1. Install Node.js 22+:
   ```bash
   node --version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template typescript/coding_agent my-coding-agent
   cd my-coding-agent
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Set up environment variables (`GROQ_API_KEY` and `E2B_API_KEY` are required):
   ```bash
   cp .env.example .env
   ```

   Get keys at: https://console.groq.com/keys and https://e2b.dev/dashboard

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```
