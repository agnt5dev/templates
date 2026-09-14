// Coding agent workflow: plan once, then iterate generate -> sync -> install
// -> execute -> (on failure) analyze -> fix, until tests pass or retries run
// out.
//
// Each stage is wrapped in agnt5.Step. Step derives its checkpoint key from
// the step name plus a call-count index, so calling agnt5.Step with the same
// name on every loop iteration is safe — each iteration gets its own
// checkpoint (step:code_generator:0, :1, :2, ...) automatically. On replay
// after a crash, already-completed iterations return their cached result
// immediately instead of re-running.
package coding_agent

import (
	"context"
	"fmt"
	"sort"

	"github.com/agnt5dev/sdk-go/agnt5"
)

const defaultMaxRetries = 15

// Generated tests are written before any code and can be wrong. The error
// analysis may flag such tests, and the workflow corrects them — but at most
// this many times per run, so it cannot keep rewriting tests to escape a
// failing implementation.
const maxTestRepairs = 2

type CodingAgentInput struct {
	TaskDescription string `json:"task_description"`
	MaxRetries      int    `json:"max_retries"`
}

func CodingAgentWorkflow(ctx *agnt5.Context, in CodingAgentInput, model agnt5.LanguageModel, e2b *e2bClient) (WorkflowResult, error) {
	maxRetries := in.MaxRetries
	if maxRetries <= 0 {
		maxRetries = defaultMaxRetries
	}
	taskDescription := in.TaskDescription

	ctx.Logger().Info("INITIATING CODING AGENT WORKFLOW")
	ctx.Logger().Info("Task", "description", truncate(taskDescription, 100), "max_retries", maxRetries)

	ctx.Logger().Info("STEP 1: PLANNING")
	plan, err := agnt5.Step(ctx, "planner", func(context.Context) (Plan, error) {
		return plannerNode(ctx, model, taskDescription)
	})
	if err != nil {
		return failedResult(ctx, taskDescription, 0, "", "", "", fmt.Sprintf("Planning failed: %v", err)), nil
	}
	ctx.Logger().Info("Planning complete")

	var (
		generatedCode, generatedTests string
		sandboxID                     string
		executionStatus               = "initial"
		errorLogs                     string
		testRepairs                   int
		testsRepaired                 []string
	)

	for iteration := 0; iteration < maxRetries; iteration++ {
		ctx.Logger().Info("ITERATION", "n", iteration+1, "of", maxRetries)
		ctx.Logger().Info("STEP 2: CODE GENERATION")

		if iteration == 0 {
			ctx.Logger().Info("Generating test suite first")
			testResult, err := agnt5.Step(ctx, "test_generator", func(context.Context) (GeneratedCode, error) {
				return testGeneratorNode(ctx, model, taskDescription, plan.TestPlan)
			})
			if err != nil {
				return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Test generation failed: %v", err)), nil
			}
			generatedTests = testResult.Code

			ctx.Logger().Info("Generating implementation (guided by tests)")
			codeResult, err := agnt5.Step(ctx, "code_generator", func(context.Context) (GeneratedCode, error) {
				return codeGeneratorNode(ctx, model, codeGenInput{
					TaskDescription: taskDescription, DevPlan: plan.DevPlan,
					ExecutionStatus: "initial", GeneratedTests: generatedTests,
				})
			})
			if err != nil {
				return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Code generation failed: %v", err)), nil
			}
			generatedCode = codeResult.Code
		} else {
			ctx.Logger().Info("Fixing code based on test failures")
			analysis, err := agnt5.Step(ctx, "error_analyzer", func(context.Context) (ErrorAnalysis, error) {
				return errorAnalyzerNode(ctx, model, taskDescription, plan.DevPlan, generatedCode, generatedTests, errorLogs)
			})
			if err != nil {
				return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Error analysis failed: %v", err)), nil
			}
			ctx.Logger().Info("Analysis complete", "summary", truncate(analysis.AnalysisSummary, 100))

			// Some failures may be the tests' fault, not the code's. Correct
			// those tests first, so the fixer is not pushed toward a wrong value.
			analysisForFixer := analysis
			onlyTestFailures := false
			switch {
			case len(analysis.InvalidTests) > 0 && testRepairs < maxTestRepairs:
				ctx.Logger().Info("Correcting tests that contradict the task")
				repair, err := agnt5.Step(ctx, "test_repair", func(context.Context) (TestRepair, error) {
					return testRepairNode(ctx, model, taskDescription, generatedTests, analysis.InvalidTests)
				})
				if err != nil {
					return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Test repair failed: %v", err)), nil
				}
				testRepairs++
				if repair.Accepted {
					generatedTests = repair.Code
					testsRepaired = mergeSorted(testsRepaired, repair.Repaired)
					repaired := map[string]bool{}
					for _, name := range repair.Repaired {
						repaired[name] = true
					}
					var remaining []string
					for _, t := range analysis.FailedTests {
						if !repaired[baseTestName(t)] {
							remaining = append(remaining, t)
						}
					}
					analysisForFixer.FailedTests = remaining
					analysisForFixer.InvalidTests = nil
					onlyTestFailures = len(remaining) == 0
				}
			case len(analysis.InvalidTests) > 0:
				ctx.Logger().Warn("Test repair limit reached; treating failures as code bugs", "limit", maxTestRepairs)
			}

			if onlyTestFailures {
				// Every failure came from a test that is now corrected: the code
				// may already be right, so re-run before changing it.
				ctx.Logger().Info("All failures were in the tests; re-running without changing the code")
			} else {
				codeResult, err := agnt5.Step(ctx, "code_generator", func(context.Context) (GeneratedCode, error) {
					return codeGeneratorNode(ctx, model, codeGenInput{
						TaskDescription: taskDescription, DevPlan: plan.DevPlan,
						ExecutionStatus: executionStatus, GeneratedCode: generatedCode,
						GeneratedTests: generatedTests, ErrorLogs: errorLogs, ErrorAnalysis: &analysisForFixer,
					})
				})
				if err != nil {
					return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Code fix failed: %v", err)), nil
				}
				generatedCode = codeResult.Code
			}
		}

		ctx.Logger().Info("STEP 3: CODE SYNC")
		syncResult, err := agnt5.Step(ctx, "code_sync", func(context.Context) (SyncResult, error) {
			return codeSyncNode(ctx, e2b, generatedCode, generatedTests, sandboxID)
		})
		if err != nil {
			return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Code sync failed: %v", err)), nil
		}

		var nextAction, status string
		if !syncResult.Success {
			ctx.Logger().Error("Code sync failed", "message", syncResult.Message)
			executionStatus = "tests_failed"
			errorLogs = syncResult.Message
			if errorLogs == "" {
				errorLogs = "Code sync failed"
			}
			nextAction, status = "retry_code", "tests_failed"
		} else {
			sandboxID = syncResult.SandboxID
			ctx.Logger().Info("Synced to sandbox", "sandbox_id", sandboxID)

			ctx.Logger().Info("STEP 4: DEPENDENCY INSTALLATION")
			if _, err := agnt5.Step(ctx, "install_deps", func(context.Context) (bool, error) {
				return true, installDepsNode(ctx, e2b, generatedCode, sandboxID)
			}); err != nil {
				return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Dependency install failed: %v", err)), nil
			}

			ctx.Logger().Info("STEP 5: TEST EXECUTION")
			execResult, err := agnt5.Step(ctx, "code_executor", func(context.Context) (ExecutionResult, error) {
				return codeExecutorNode(ctx, e2b, sandboxID)
			})
			if err != nil {
				return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Test execution failed: %v", err)), nil
			}

			nextAction, status, errorLogs = execResult.NextAction, execResult.Status, execResult.ErrorLogs
			executionStatus = status
		}

		ctx.Logger().Info("STEP 6: DECISION")

		if nextAction == "success" {
			ctx.Logger().Info("SUCCESS! All tests passed")
			if len(testsRepaired) > 0 {
				ctx.Logger().Warn("Passed after correcting generated test(s)", "tests", testsRepaired)
			}
			ctx.Logger().Info("STEP 7: DOCUMENTATION")

			finalResult, err := agnt5.Step(ctx, "final_response", func(context.Context) (FinalResponse, error) {
				return finalResponseNode(ctx, model, taskDescription, generatedCode)
			})
			if err != nil {
				return failedResult(ctx, taskDescription, iteration+1, generatedCode, generatedTests, sandboxID, fmt.Sprintf("Documentation failed: %v", err)), nil
			}

			ctx.Logger().Info("WORKFLOW COMPLETE - SUCCESS")
			return WorkflowResult{
				Success: true, Task: taskDescription, Iterations: iteration + 1,
				Code: generatedCode, Tests: generatedTests, SandboxID: sandboxID,
				Documentation: finalResult.MarkdownContent, TestsRepaired: testsRepaired,
			}, nil
		}

		if iteration == maxRetries-1 {
			ctx.Logger().Warn("Maximum retries reached", "max_retries", maxRetries)
			return WorkflowResult{
				Success: false, Task: taskDescription, Iterations: iteration + 1,
				Error:     fmt.Sprintf("Maximum retries (%d) exhausted", maxRetries),
				ErrorLogs: errorLogs, Code: generatedCode, Tests: generatedTests, SandboxID: sandboxID,
				TestsRepaired: testsRepaired,
			}, nil
		}
		ctx.Logger().Warn("Retrying", "attempt", iteration+2, "of", maxRetries, "status", status)
	}

	return failedResult(ctx, taskDescription, maxRetries, generatedCode, generatedTests, sandboxID, "Workflow terminated unexpectedly"), nil
}

func failedResult(ctx *agnt5.Context, task string, iterations int, code, tests, sandboxID, errMsg string) WorkflowResult {
	ctx.Logger().Error("WORKFLOW COMPLETE - ERROR", "error", errMsg)
	return WorkflowResult{
		Success: false, Task: task, Iterations: iterations,
		Error: errMsg, Code: code, Tests: tests, SandboxID: sandboxID,
	}
}

// mergeSorted returns the union of two name lists, sorted and deduplicated.
func mergeSorted(a, b []string) []string {
	seen := map[string]bool{}
	for _, s := range append(append([]string{}, a...), b...) {
		seen[s] = true
	}
	out := make([]string, 0, len(seen))
	for s := range seen {
		out = append(out, s)
	}
	sort.Strings(out)
	return out
}
