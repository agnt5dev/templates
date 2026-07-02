# Coding Agent

> Autonomous test-driven development agent that writes, tests, and iteratively fixes Python code until all tests pass.

## Quick Start

```bash
agnt5 create --template python/coding_agent
export GROQ_API_KEY=gsk_... E2B_API_KEY=...
agnt5 dev up
```

## What You Can Build

- **Algorithm Implementations**: Solve LeetCode problems, implement data structures, or build utility functions
- **API Clients**: Generate complete Python modules with tests for third-party API integrations
- **Data Processing Scripts**: Create ETL pipelines, parsers, or validators with full test coverage

## Installation

### Prerequisites

- Python 3.12+
- AGNT5 SDK
- Groq API key (for LLM)
- E2B API key (for code execution sandbox)

### Setup

```bash
# Clone or create from template
agnt5 create --template python/coding_agent
cd coding_agent

# Install dependencies
uv sync

# Configure environment variables
export GROQ_API_KEY=gsk_your_groq_api_key
export E2B_API_KEY=your_e2b_api_key

# Start the worker
agnt5 dev up
```

Get API keys:
- Groq: https://console.groq.com/keys
- E2B: https://e2b.dev/dashboard

## Usage

### Direct Invocation (development / testing)

```python
import asyncio
from coding_agent.workflows import coding_agent_workflow

async def main():
    task = """
    Create a function that validates whether a string is a valid number.
    Support integers, decimals, and scientific notation.
    """

    result = await coding_agent_workflow(task, max_retries=15)

    if result.success:
        print(f"Code:\n{result.code}")
        print(f"Tests:\n{result.tests}")
        print(f"Iterations: {result.iterations}")
        print(f"Documentation:\n{result.documentation}")
    else:
        print(f"Failed: {result.error}")

asyncio.run(main())
```

### Example Output

```python
{
    "success": True,
    "task": "Create a function that validates...",
    "iterations": 3,
    "code": "def is_valid_number(s: str) -> bool:\n    ...",
    "tests": "import pytest\n\ndef test_valid_numbers():\n    ...",
    "sandbox_id": "e2b-sandbox-xyz123",
    "documentation": "# Valid Number Validator\n\n## Overview...",
    "error": None
}
```

The workflow automatically:
- Generates Python code from task description
- Creates comprehensive pytest test suite
- Runs tests in isolated E2B sandbox
- Analyzes failures and fixes code iteratively
- Produces final documentation in markdown

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for LLM access | Yes |
| `E2B_API_KEY` | E2B API key for code sandbox | Yes |

### Workflow Parameters

```python
coding_agent_workflow(
    task_description: str,  # Coding task description
    max_retries: int = 15   # Max iterations for fixing code
)
```

### Models Used

- **Planner/Analyzer**: `llama-4-scout-17b-16e-instruct` (planning and error analysis)
- **Code Generator**: `llama-4-maverick-17b-128e-instruct` (code generation and fixes)

<details>
<summary>Architecture</summary>

### Multi-Function Workflow

The workflow orchestrates eight specialized function nodes:

#### 1. Planner Node
- **Input**: Task description
- **Output**: Development plan + test plan
- **Model**: llama-4-scout-17b-16e-instruct
- **Role**: Creates structured plans for implementation and testing

#### 2. Test Generator Node
- **Input**: Task, test plan
- **Output**: Pytest test suite
- **Model**: llama-4-maverick-17b-128e-instruct
- **Role**: Generates tests first — code is written to satisfy them (TDD)

#### 3. Code Generator Node
- **Input**: Task, dev plan, generated tests, (optional) error analysis
- **Output**: Python code
- **Model**: llama-4-maverick-17b-128e-instruct
- **Role**: Generates or fixes code guided by the existing test suite

#### 4. Code Sync Node
- **Input**: Main code, test code, sandbox ID
- **Output**: Sync status, sandbox ID
- **Role**: Uploads code files to E2B sandbox

#### 5. Install Deps Node
- **Input**: Main code, sandbox ID
- **Output**: Installation status
- **Role**: Detects and installs required packages in the sandbox before test execution

#### 6. Code Executor Node
- **Input**: Sandbox ID
- **Output**: Test results, error logs, next action
- **Tools**: E2B sandbox (`run_command`, `read_file`)
- **Role**: Runs pytest and analyzes results

#### 7. Error Analyzer Node
- **Input**: Task, code, tests, error logs
- **Output**: Error analysis with root causes and suggestions
- **Model**: llama-4-scout-17b-16e-instruct
- **Role**: Deep analysis of test failures to guide fixes

#### 8. Final Response Node
- **Input**: Task, generated code
- **Output**: Markdown documentation
- **Role**: Generates comprehensive documentation

### Workflow Steps

```
1. Planning
   └─> Analyze task description
   └─> Create development plan + test plan

2. Iteration 1 (TDD bootstrap)
   └─> Generate pytest test suite (from test plan)
   └─> Generate implementation (guided by tests)
   └─> Sync both files to E2B sandbox
   └─> Install detected dependencies
   └─> Execute tests

3. Fix Loop (Iterations 2–N)
   └─> Analyze test failures (root causes + suggestions)
   └─> Fix code based on analysis
   └─> Sync updated code to sandbox
   └─> Install any new dependencies
   └─> Execute tests
   └─> Repeat until success or max_retries

4. Documentation
   └─> Generate markdown docs
   └─> Return results
```

### Iterative Refinement

- Tests are generated first on iteration 1; all subsequent iterations keep the same test suite
- Error analyzer runs before each code fix to identify root causes
- Each iteration includes: error analysis → code fix → sync → dep install → test execution
- Loop terminates on success or after `max_retries` iterations

### E2B Sandbox Isolation

All code execution happens in E2B sandboxes:
- Isolated Python 3.12 environment
- Pre-installed pytest
- File system access for code/test uploads
- Command execution for running tests
- Prevents host system contamination

### State Management

Workflow state tracks:
- `task_description`: Original task
- `dev_plan`, `test_plan`: Planning outputs
- `generated_code`, `generated_tests`: Latest code versions
- `execution_status`: Test execution state
- `error_logs`: Failure details
- `error_analysis`: Analysis results
- `sandbox_id`: E2B sandbox identifier
- `retries`: Current iteration count

</details>

## Troubleshooting

### Missing API keys
```
ValueError: Missing required environment variables: GROQ_API_KEY, E2B_API_KEY
```
**Solution**: Export both `GROQ_API_KEY` and `E2B_API_KEY` before running.

### E2B sandbox creation failed
```
Error: Failed to create E2B sandbox
```
**Solution**: Verify E2B API key is valid and your account has available quota at https://e2b.dev/dashboard.

### Max retries reached
```
Workflow failed: Maximum retries (15) exhausted
```
**Solution**: The agent couldn't fix all test failures within 15 iterations. Simplify the task, increase `max_retries`, or inspect logs to see what's failing.

### Groq rate limits
```
Error: Rate limit exceeded
```
**Solution**: Wait and retry, or upgrade your Groq plan for higher rate limits.

### Import errors in generated code
Check that the E2B sandbox has required dependencies. Modify `code_sync_node` in `src/coding_agent/functions.py` to install packages via pip before running tests.

## Customization

### Change LLM Models

Modify model selection in `src/coding_agent/functions.py`:

```python
# For planning and error analysis (planner_node, error_analyzer_node)
model="groq/meta-llama/llama-4-scout-17b-16e-instruct"

# For code generation (code_generator_node, test_generator_node)
model="groq/meta-llama/llama-4-maverick-17b-128e-instruct"
```

You can switch to other Groq models by updating the model parameter in each function node.

### Adjust Retry Logic

Change max iterations in workflow call:

```python
result = await coding_agent_workflow(
    task_description=task,
    max_retries=25  # Increase from default 15
)
```

### Add Custom Tools

Extend E2B tools in `src/coding_agent/tools.py`:

```python
@tool(auto_schema=True)
async def install_package(ctx: Context, sandbox_id: str, package: str) -> dict:
    """Install a Python package in the sandbox."""
    # Implementation
    pass
```

Register in `app.py`:

```python
worker = Worker(
    tools=[
        E2BSandboxTools.create_sandbox,
        E2BSandboxTools.write_file,
        E2BSandboxTools.run_command,
        E2BSandboxTools.read_file,
        install_package,  # Add custom tool
    ],
    ...
)
```

### Customize Test Framework

Modify test generation prompts in `src/coding_agent/prompts/coding_agent_prompts.py` to use unittest, doctest, or other frameworks instead of pytest.

### Related Templates

- **code_reviewer**: AI-powered code review with security and quality analysis
- **text-to-sql**: Multi-step reasoning workflows with validation
- **weather-agent**: Tool-based agentic workflows

## License

MIT License - see [LICENSE](LICENSE) for details
