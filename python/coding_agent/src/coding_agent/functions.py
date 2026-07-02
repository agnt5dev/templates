"""Function nodes for the coding agent workflow."""

import ast
import re
import sys
from typing import Optional

from agnt5 import function, FunctionContext, lm
from agnt5.types import RetryPolicy, BackoffType, BackoffPolicy

from coding_agent.models import (
    Plan,
    GeneratedCode,
    ErrorAnalysis,
    SyncResult,
    ExecutionResult,
    FinalResponse,
)
from coding_agent.prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_PROMPT,
    CODER_SYSTEM_PROMPT,
    CODER_USER_PROMPT,
    TEST_SYSTEM_PROMPT,
    TEST_USER_PROMPT,
    MARKDOWN_SYSTEM_PROMPT,
    MARKDOWN_USER_PROMPT,
    ERROR_ANALYZER_SYSTEM_PROMPT,
    ERROR_ANALYZER_USER_PROMPT,
    CODEFIXER_SYSTEM_PROMPT,
    CODEFIXER_USER_PROMPT,
)
from coding_agent.tools import E2BSandboxTools


def _clean_code(code: str) -> str:
    """Strip markdown code fences the LLM sometimes wraps around the code value."""
    code = code.strip()
    # Remove ```python ... ``` or ``` ... ``` wrappers
    fenced = re.match(r"^```(?:python)?\s*\n(.*?)\n```$", code, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # Fallback: strip any leading/trailing fence lines individually
    lines = code.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _validate_python_syntax(code: str) -> tuple[bool, str]:
    """Return (is_valid, error_message). Uses ast.parse() — catches all syntax errors."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}\n  {e.text or ''}"


STDLIB_MODULES = frozenset(sys.stdlib_module_names)


def _extract_third_party_imports(code: str) -> list[str]:
    """Get non-stdlib top-level module names from Python source code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    skip = STDLIB_MODULES | {"pytest", "__future__", "typing_extensions", "typing"}
    return sorted(n for n in names if n and n not in skip and not n.startswith("_"))


@function(
    name="planner_node",
    retries=RetryPolicy(max_attempts=5),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def planner_node(ctx: FunctionContext, task_description: str) -> Plan:
    ctx.logger.info("🎯 Planning process started")
    ctx.logger.debug(f"Task description length: {len(task_description)} chars")

    try:
        response = await lm.generate(
            model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
            system_prompt=PLANNER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": PLANNER_USER_PROMPT.format(
                        task_description=task_description
                    ),
                },
            ],
            temperature=0,
            response_format=Plan,
        )

        plan = response.structured_output

        ctx.logger.info("✅ Plan generated successfully")
        ctx.logger.debug(f"Dev plan length: {len(plan['dev_plan'])} chars")
        ctx.logger.debug(f"Test plan length: {len(plan['test_plan'])} chars")

        return Plan(**plan)

    except Exception as e:
        ctx.logger.error(f"Error in planner_agent: {e}")
        raise


@function(
    name="code_generator_node",
    retries=RetryPolicy(max_attempts=5),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def code_generator_node(
    ctx: FunctionContext,
    task_description: str,
    dev_plan: str,
    execution_status: str = "initial",
    generated_code: str = "",
    generated_tests: str = "",
    error_logs: str = "",
    error_analysis: Optional[ErrorAnalysis] = None,
) -> GeneratedCode:
    try:
        if execution_status != "tests_failed":
            ctx.logger.info("🔨 Generating initial code from plan")
            prompt = CODER_USER_PROMPT.format(
                task_description=task_description,
                development_plan=dev_plan,
                test_suite=generated_tests if generated_tests else "Tests will be validated after implementation.",
            )
            system_prompt = CODER_SYSTEM_PROMPT
        else:
            ctx.logger.info("🔧 Fixing code based on test failures")
            ctx.logger.debug(f"Error logs: {error_logs[:200]}...")

            # Format error analysis for the prompt
            analysis_text = ""
            if error_analysis:
                analysis_text = f"""
### 🔍 ERROR ANALYSIS

**Failed Tests:**
{chr(10).join(f'- {test}' for test in error_analysis.failed_tests)}

**Root Causes:**
{chr(10).join(f'- {cause}' for cause in error_analysis.root_causes)}

**Suggested Fixes:**
{chr(10).join(f'- {fix}' for fix in error_analysis.suggested_fixes)}

**Analysis Summary:**
{error_analysis.analysis_summary}

---
"""

            prompt = CODEFIXER_USER_PROMPT.format(
                dev_code=generated_code,
                test_code=generated_tests,
                error_logs=error_logs,
                task_description=task_description,
                development_plan=dev_plan,
                error_analysis=analysis_text,
            )
            system_prompt = CODEFIXER_SYSTEM_PROMPT

        response = await lm.generate(
            model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format=GeneratedCode,
        )

        raw = response.structured_output
        code_result = GeneratedCode(code=_clean_code(raw["code"]))

        ctx.logger.info(f"✅ Code processed: {len(code_result.code)} chars")
        return code_result

    except Exception as e:
        ctx.logger.error(f"Code generation/fixing failed: {e}")
        raise


@function(
    name="test_generator_node",
    retries=RetryPolicy(max_attempts=5),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def test_generator_node(
    ctx: FunctionContext,
    task_description: str,
    test_plan: str
) -> GeneratedCode:
    ctx.logger.info("🧪 Generating test suite")
    try:
        response = await lm.generate(
            model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
            system_prompt=TEST_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": TEST_USER_PROMPT.format(
                        task_description=task_description,
                        test_plan=test_plan,
                    ),
                },
            ],
            temperature=0,
            response_format=GeneratedCode,
        )

        raw = response.structured_output
        tests = GeneratedCode(code=_clean_code(raw["code"]))

        ctx.logger.info(f"✅ Tests generated: {len(tests.code)} chars")
        return tests

    except Exception as e:
        ctx.logger.error(f"Test generation failed: {e}")
        raise


@function(
    name="code_sync_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def code_sync_node(
    ctx: FunctionContext,
    main_code: str,
    test_code: str,
    sandbox_id: Optional[str] = None,
) -> SyncResult:
    ctx.logger.info("📤 Syncing code and tests to sandbox")
    if not main_code or not test_code:
        raise ValueError("Cannot sync: main_code or test_code is empty")

    # Validate syntax locally before burning a sandbox round-trip
    for filename, src in [("main.py", main_code), ("test.py", test_code)]:
        valid, err = _validate_python_syntax(src)
        if not valid:
            ctx.logger.error(f"❌ Syntax error in {filename}: {err}")
            return SyncResult(
                success=False,
                sandbox_id=sandbox_id,
                message=f"Syntax error in {filename}: {err}",
            )

    try:
        if sandbox_id:
            ctx.logger.info(f"Using existing sandbox: {sandbox_id}")
        else:
            ctx.logger.info("Creating new E2B sandbox")
            result = await E2BSandboxTools.create_sandbox(ctx, sandbox_id=sandbox_id)
            sandbox_id = result.get("sandbox_id")
            if not sandbox_id:
                raise ValueError("Failed to create sandbox - no ID returned")
            ctx.logger.info(f"✅ Created sandbox: {sandbox_id}")

        ctx.logger.debug("Writing main.py...")
        await E2BSandboxTools.write_file(ctx, sandbox_id=sandbox_id, path="main.py", content=main_code)
        ctx.logger.debug("Writing test.py...")
        await E2BSandboxTools.write_file(ctx, sandbox_id=sandbox_id, path="test.py", content=test_code)

        ctx.logger.info("✅ Code and tests synced successfully")
        return SyncResult(success=True, sandbox_id=sandbox_id, message="Code and tests synced successfully")

    except Exception as e:
        ctx.logger.error(f"Code sync failed: {e}")
        raise


@function(
    name="install_deps_node",
    retries=RetryPolicy(max_attempts=2),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def install_deps_node(
    ctx: FunctionContext,
    main_code: str,
    sandbox_id: str,
) -> bool:
    """Install any third-party packages imported by main.py into the sandbox."""
    pkgs = _extract_third_party_imports(main_code)
    if not pkgs:
        ctx.logger.info("No third-party dependencies detected")
        return True

    ctx.logger.info(f"📦 Installing dependencies: {pkgs}")
    result = await E2BSandboxTools.run_command(
        ctx,
        sandbox_id=sandbox_id,
        command=f"pip install -q {' '.join(pkgs)} 2>&1 | tail -5",
        timeout_ms=120000,
    )
    if result.get("success"):
        ctx.logger.info(f"✅ Dependencies installed: {pkgs}")
    else:
        ctx.logger.warning(f"⚠️ pip install completed with warnings: {result.get('stdout', '')[:200]}")
    return True


@function(
    name="code_executor_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def code_executor_node(ctx: FunctionContext, sandbox_id: str) -> ExecutionResult:
    ctx.logger.info("🧪 Executing tests in sandbox")
    if not sandbox_id:
        raise ValueError("No sandbox_id provided")

    try:
        exec_result = await E2BSandboxTools.run_command(
            ctx,
            sandbox_id=sandbox_id,
            command="pytest test.py --tb=short -q 2>&1",
        )

        exit_code = exec_result.get("exit_code")
        stdout = exec_result.get("stdout", "")
        stderr = exec_result.get("stderr", "")

        ctx.logger.debug(f"Exit code: {exit_code}")
        ctx.logger.debug(f"Stdout: {stdout[:200]}...")

        if exit_code == 0:
            ctx.logger.info("✅ All tests passed!")
            return ExecutionResult(
                status="tests_passed",
                next_action="success",
                test_results=exec_result,
                error_logs=None,
            )
        else:
            # exit_code 1 = test failures
            # exit_code 2 = collection error (syntax/import error in generated code)
            # all are recoverable — let the error analyzer + code fixer handle them
            error_output = stdout or stderr
            ctx.logger.warning(
                f"❌ Tests failed (exit code {exit_code}) - retry needed\n"
                f"stdout: {stdout[:200]}"
            )
            return ExecutionResult(
                status="tests_failed",
                next_action="retry_code",
                test_results=exec_result,
                error_logs=error_output,
            )

    except Exception as e:
        ctx.logger.error(f"Test execution failed: {e}")
        return ExecutionResult(
            status="tests_failed",
            next_action="retry_code",
            test_results=None,
            error_logs=str(e),
        )


@function(
    name="error_analyzer_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def error_analyzer_node(
    ctx: FunctionContext,
    task_description: str,
    dev_plan: str,
    generated_code: str,
    generated_tests: str,
    error_logs: str,
) -> ErrorAnalysis:
    ctx.logger.info("🔍 Analyzing test failures")
    ctx.logger.debug(f"Error logs length: {len(error_logs)} chars")

    try:
        response = await lm.generate(
            model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
            system_prompt=ERROR_ANALYZER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": ERROR_ANALYZER_USER_PROMPT.format(
                        task_description=task_description,
                        development_plan=dev_plan,
                        generated_code=generated_code,
                        generated_tests=generated_tests,
                        error_logs=error_logs,
                    ),
                },
            ],
            temperature=0,
            response_format=ErrorAnalysis,
        )

        analysis = ErrorAnalysis(**response.structured_output)

        ctx.logger.info("✅ Error analysis complete")
        ctx.logger.debug(f"Failed tests: {len(analysis.failed_tests)}")
        ctx.logger.debug(f"Root causes: {len(analysis.root_causes)}")
        return analysis

    except Exception as e:
        ctx.logger.error(f"Error in error_analyzer_node: {e}")
        raise


@function(
    name="final_response_node",
    retries=RetryPolicy(max_attempts=3),
    backoff=BackoffPolicy(type=BackoffType.EXPONENTIAL),
)
async def final_response_node(
    ctx: FunctionContext,
    task_description: str,
    generated_code: str
) -> FinalResponse:
    ctx.logger.info("📝 Generating documentation")
    try:
        response = await lm.generate(
            model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
            system_prompt=MARKDOWN_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": MARKDOWN_USER_PROMPT.format(
                        task_description=task_description,
                        generated_code=generated_code,
                    ),
                },
            ],
            temperature=0,
        )

        markdown_response = response.text
        with open("final_response.md", "w") as f:
            f.write(markdown_response)

        ctx.logger.info("✅ Documentation saved to final_response.md")
        return FinalResponse(markdown_content=markdown_response)

    except Exception as e:
        ctx.logger.error(f"Documentation generation failed: {e}")
        raise
