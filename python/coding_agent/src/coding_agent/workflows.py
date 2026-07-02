"""Coding agent workflow implementation."""

from agnt5 import workflow, WorkflowContext

from coding_agent.models import WorkflowResult
from coding_agent.functions import (
    planner_node,
    code_generator_node,
    test_generator_node,
    code_sync_node,
    install_deps_node,
    code_executor_node,
    error_analyzer_node,
    final_response_node,
)


@workflow(name="coding_agent_workflow")
async def coding_agent_workflow(
    ctx: WorkflowContext, task_description: str, max_retries: int = 15
) -> WorkflowResult:
    """Execute the complete coding agent workflow.

    Args:
        ctx: Workflow context for state management and logging
        task_description: Description of the coding task
        max_retries: Maximum number of retry attempts (default: 15)

    Returns:
        Dict containing workflow results including success status and code
    """
    ctx.logger.info("=" * 60)
    ctx.logger.info("🚀 INITIATING CODING AGENT WORKFLOW")
    ctx.logger.info("=" * 60)

    ctx.state.set("task_description", task_description)
    ctx.state.set("retries", 0)
    ctx.state.set("execution_status", "initial")

    ctx.logger.info(f"📋 Task: {task_description[:100]}...")
    ctx.logger.info(f"🔁 Max retries: {max_retries}")

    try:
        ctx.logger.info("\n" + "=" * 60)
        ctx.logger.info("📍 STEP 1: PLANNING")
        ctx.logger.info("=" * 60)

        plan = await ctx.step(planner_node, task_description)

        ctx.state.set("dev_plan", plan.dev_plan)
        ctx.state.set("test_plan", plan.test_plan)

        ctx.logger.info("✅ Planning complete")

        for iteration in range(max_retries):
            ctx.logger.info("\n" + "=" * 60)
            ctx.logger.info(f"🔄 ITERATION {iteration + 1}/{max_retries}")
            ctx.logger.info("=" * 60)

            execution_status = ctx.state.get("execution_status", "initial")

            ctx.logger.info("\n📍 STEP 2: CODE GENERATION")

            if iteration == 0:
                ctx.logger.info("🧪 Generating test suite first")
                test_result = await ctx.step(
                    test_generator_node,
                    task_description=task_description,
                    test_plan=ctx.state.get("test_plan"),
                )
                generated_tests = test_result.code

                ctx.logger.info("📝 Generating implementation (guided by tests)")
                code_result = await ctx.step(
                    code_generator_node,
                    task_description=task_description,
                    dev_plan=ctx.state.get("dev_plan"),
                    execution_status="initial",
                    generated_tests=generated_tests,
                )
                generated_code = code_result.code

            else:
                ctx.logger.info("🔧 Fixing code based on test failures")

                ctx.logger.info("\n🔍 Analyzing errors...")
                error_analysis = await ctx.step(
                    error_analyzer_node,
                    task_description=task_description,
                    dev_plan=ctx.state.get("dev_plan"),
                    generated_code=ctx.state.get("generated_code"),
                    generated_tests=ctx.state.get("generated_tests"),
                    error_logs=ctx.state.get("error_logs", ""),
                )

                ctx.state.set("error_analysis", error_analysis)
                ctx.logger.info(f"✅ Analysis complete: {error_analysis.analysis_summary[:100]}...")

                code_result = await ctx.step(
                    code_generator_node,
                    task_description=task_description,
                    dev_plan=ctx.state.get("dev_plan"),
                    execution_status=execution_status,
                    generated_code=ctx.state.get("generated_code"),
                    generated_tests=ctx.state.get("generated_tests"),
                    error_logs=ctx.state.get("error_logs", ""),
                    error_analysis=error_analysis,
                )

                generated_code = code_result.code
                generated_tests = ctx.state.get("generated_tests")

            ctx.state.set("generated_code", generated_code)
            ctx.state.set("generated_tests", generated_tests)

            ctx.logger.info("\n📍 STEP 3: CODE SYNC")

            sync_result = await ctx.step(
                code_sync_node,
                main_code=generated_code,
                test_code=generated_tests,
                sandbox_id=ctx.state.get("sandbox_id"),
            )

            if not sync_result.success:
                ctx.logger.error(f"❌ Code sync failed: {sync_result.message}")
                ctx.state.set("execution_status", "tests_failed")
                ctx.state.set("error_logs", sync_result.message or "Code sync failed")
                error_logs = sync_result.message or "Code sync failed"
                # Fall through to the shared retry block below
                next_action = "retry_code"
                status = "tests_failed"
            else:
                sandbox_id = sync_result.sandbox_id
                ctx.state.set("sandbox_id", sandbox_id)
                ctx.logger.info(f"✅ Synced to sandbox: {sandbox_id}")

                ctx.logger.info("\n📍 STEP 4: DEPENDENCY INSTALLATION")
                await ctx.step(
                    install_deps_node,
                    main_code=generated_code,
                    sandbox_id=sandbox_id,
                )

                ctx.logger.info("\n📍 STEP 5: TEST EXECUTION")

                exec_result = await ctx.step(
                    code_executor_node,
                    sandbox_id=sandbox_id,
                )

                next_action = exec_result.next_action
                status = exec_result.status
                error_logs = exec_result.error_logs

                ctx.state.set("execution_status", status)
                ctx.state.set("error_logs", error_logs)

            ctx.logger.info("\n📍 STEP 6: DECISION")

            if next_action == "success":
                ctx.logger.info("✅ SUCCESS! All tests passed")
                ctx.logger.info("\n📍 STEP 7: DOCUMENTATION")

                final_result = await ctx.step(
                    final_response_node,
                    task_description=task_description,
                    generated_code=generated_code,
                )

                ctx.logger.info("=" * 60)
                ctx.logger.info("🎉 WORKFLOW COMPLETE - SUCCESS")
                ctx.logger.info("=" * 60)

                return WorkflowResult(
                    success=True,
                    task=task_description,
                    iterations=iteration + 1,
                    code=generated_code,
                    tests=generated_tests,
                    sandbox_id=sandbox_id,
                    documentation=final_result.markdown_content,
                    error=None,
                )

            else:
                # All non-success outcomes (test failure, syntax error, sync failure) → retry
                retries = ctx.state.get("retries", 0) + 1
                ctx.state.set("retries", retries)

                if retries >= max_retries:
                    ctx.logger.warning(f"❌ Maximum retries ({max_retries}) reached")
                    ctx.logger.info("=" * 60)
                    ctx.logger.info("💔 WORKFLOW COMPLETE - MAX RETRIES")
                    ctx.logger.info("=" * 60)
                    return WorkflowResult(
                        success=False,
                        task=task_description,
                        iterations=iteration + 1,
                        error=f"Maximum retries ({max_retries}) exhausted",
                        error_logs=error_logs,
                        code=generated_code,
                        tests=generated_tests,
                        sandbox_id=sandbox_id,
                    )

                ctx.logger.warning(f"⚠️ Retrying ({retries}/{max_retries}) — {status}")
                continue

    except Exception as e:
        ctx.logger.error(f"💥 Workflow exception: {e}")
        ctx.logger.info("=" * 60)
        ctx.logger.info("💔 WORKFLOW COMPLETE - ERROR")
        ctx.logger.info("=" * 60)

        return WorkflowResult(
            success=False,
            task=task_description,
            iterations=ctx.state.get("retries", 0),
            error=f"Workflow exception: {str(e)}",
            code=ctx.state.get("generated_code"),
            tests=ctx.state.get("generated_tests"),
            sandbox_id=ctx.state.get("sandbox_id"),
        )

    ctx.logger.error("❌ Unexpected workflow termination")
    return WorkflowResult(
        success=False,
        task=task_description,
        iterations=max_retries,
        error="Workflow terminated unexpectedly",
        code=ctx.state.get("generated_code"),
        tests=ctx.state.get("generated_tests"),
        sandbox_id=ctx.state.get("sandbox_id"),
    )
