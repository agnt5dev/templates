"""Function nodes for the coding agent workflow."""

from typing import Optional

from agnt5 import function, FunctionContext, lm
from agnt5.types import RetryPolicy, BackoffType, BackoffPolicy

from coding_agent_agnt5.models import (
    Plan,
    GeneratedCode,
    ErrorAnalysis,
    SyncResult,
    ExecutionResult,
    FinalResponse,
)
from coding_agent_agnt5.prompts import (
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
from coding_agent_agnt5.tools import E2BSandboxTools


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
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": PLANNER_USER_PROMPT.format(
                        task_description=task_description
                    )
                },
            ],
            temperature=0,
            response_format=Plan,
        )

        # Use the structured_output property to get the parsed object
        plan = response.structured_output

        ctx.logger.info("✅ Plan generated successfully")
        ctx.logger.debug(f"Dev plan length: {len(plan['dev_plan'])} chars")
        ctx.logger.debug(f"Test plan length: {len(plan['test_plan'])} chars")

        # Convert dict to Plan object
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
                development_plan=dev_plan
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
            model="groq/meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format=GeneratedCode,
        )

        # Use the structured_output property to get the parsed object
        code_result_dict = response.structured_output
        code_result = GeneratedCode(**code_result_dict)

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
            model="groq/meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {"role": "system", "content": TEST_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": TEST_USER_PROMPT.format(
                        task_description=task_description,
                        test_plan=test_plan
                    )
                },
            ],
            temperature=0,
            response_format=GeneratedCode,
        )

        # Use the structured_output property to get the parsed object
        tests_dict = response.structured_output
        tests = GeneratedCode(**tests_dict)

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

    try:
        if sandbox_id:
            ctx.logger.info(f"Using existing sandbox: {sandbox_id}")
        else:
            ctx.logger.info("Creating new E2B sandbox")
            result = await E2BSandboxTools.create_sandbox(
                ctx,
                sandbox_id=sandbox_id
            )
            sandbox_id = result.get("sandbox_id")
            if not sandbox_id:
                raise ValueError("Failed to create sandbox - no ID returned")
            ctx.logger.info(f"✅ Created sandbox: {sandbox_id}")

        ctx.logger.debug("Writing main.py...")
        await E2BSandboxTools.write_file(
            ctx,
            sandbox_id=sandbox_id,
            path="main.py",
            content=main_code
        )
        ctx.logger.debug("Writing test.py...")
        await E2BSandboxTools.write_file(
            ctx,
            sandbox_id=sandbox_id,
            path="test.py",
            content=test_code
        )

        ctx.logger.info("✅ Code and tests synced successfully")
        return SyncResult(
            success=True,
            sandbox_id=sandbox_id,
            message="Code and tests synced successfully"
        )

    except Exception as e:
        ctx.logger.error(f"Code sync failed: {e}")
        raise


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
            command="pytest test.py --maxfail=1 --disable-warnings -q",
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
        elif exit_code == 1:
            ctx.logger.warning("❌ Tests failed - retry needed")
            return ExecutionResult(
                status="tests_failed",
                next_action="retry_code",
                test_results=exec_result,
                error_logs=stdout,
            )
        else:
            ctx.logger.error(
                f"⚠️ Unexpected exit code {exit_code}\n"
                f"stdout: {stdout[:200]}\n"
                f"stderr: {stderr[:200]}"
            )
            return ExecutionResult(
                status="error",
                next_action="abort",
                test_results=exec_result,
                error_logs=f"Unexpected exit code {exit_code}. stdout: {stdout}, stderr: {stderr}",
            )

    except Exception as e:
        ctx.logger.error(f"Test execution failed: {e}")
        return ExecutionResult(
            status="error",
            next_action="abort",
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
            messages=[
                {"role": "system", "content": ERROR_ANALYZER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": ERROR_ANALYZER_USER_PROMPT.format(
                        task_description=task_description,
                        development_plan=dev_plan,
                        generated_code=generated_code,
                        generated_tests=generated_tests,
                        error_logs=error_logs,
                    )
                },
            ],
            temperature=0,
            response_format=ErrorAnalysis,
        )

        # Use the structured_output property to get the parsed object
        analysis_dict = response.structured_output
        analysis = ErrorAnalysis(**analysis_dict)

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
            messages=[
                {"role": "system", "content": MARKDOWN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": MARKDOWN_USER_PROMPT.format(
                        task_description=task_description,
                        generated_code=generated_code
                    )
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
