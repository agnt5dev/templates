// Function nodes for the coding agent workflow. Prompts here are condensed
// from the Python/TypeScript templates' much longer originals, preserving
// the same role, constraints, and required JSON output shape.
package coding_agent

import (
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/agnt5dev/sdk-go/agnt5"
)

const plannerSystemPrompt = `You are an Expert Planning Agent that creates perfectly synchronized development and test plans for Python projects.

Produce two plans that describe exactly the same public interface (function names, signatures, and behavior), so that code written from the dev plan will pass tests written from the test plan without any mismatch.

Respond with a JSON object matching this shape: {"dev_plan": string, "test_plan": string}`

func plannerUserPrompt(taskDescription string) string {
	return fmt.Sprintf(`MISSION: Create perfectly synchronized development and test plans.

Task: %s

Produce:
1. A development plan describing the module's public functions/classes, their signatures, parameters, return types, and behavior (including edge cases and error handling).
2. A test plan describing the pytest test cases that verify every behavior in the development plan, using the exact same function/class names and signatures.

The implementation is always a single file, main.py, so tests import it with `+"`from main import <name>`"+`. Do not name any other module.`, taskDescription)
}

const coderSystemPrompt = `You are an Expert Python Coder Agent specialized in implementing code from development plans. Your core identity is absolute precision and plan adherence — implement exactly what the plan specifies, no more, no less.

Respond with a JSON object matching this shape: {"code": string}`

func coderUserPrompt(taskDescription, devPlan, testSuite string) string {
	return fmt.Sprintf(`CRITICAL MISSION: Implement code with 100 percent development plan fidelity.

Task: %s

Development Plan:
%s

Test Suite (for reference, must pass unmodified):
%s

Write complete, runnable Python code in main.py implementing exactly what the development plan specifies. Include all necessary imports.`, taskDescription, devPlan, testSuite)
}

const testSystemPrompt = `You are a Python Test Engineer specialized in creating comprehensive pytest test suites.

Respond with a JSON object matching this shape: {"code": string}`

func testUserPrompt(taskDescription, testPlan string) string {
	return fmt.Sprintf(`MISSION: Generate a comprehensive pytest test suite from test plan specifications.

Task: %s

Test Plan:
%s

Write a complete test.py file that tests every behavior in the test plan, including edge cases and error conditions.

The code under test is in main.py: import it with `+"`from main import <name>`"+`, never from any other module name, even if the plan mentions one.`, taskDescription, testPlan)
}

const markdownSystemPrompt = `You are a Technical Documentation Specialist with expertise in code analysis and technical communication. Transform programming tasks and their implementations into clear, professional markdown documentation.`

func markdownUserPrompt(taskDescription, generatedCode string) string {
	return fmt.Sprintf(`MISSION: Create comprehensive markdown documentation for a programming task and its implementation.

Task: %s

Implementation:
%s

Write a markdown document covering: overview, usage, function reference, and examples.`, taskDescription, generatedCode)
}

const errorAnalyzerSystemPrompt = `You are an Expert Error Analysis Specialist with deep expertise in debugging Python code, interpreting test failures, and diagnosing root causes.

Parse error logs systematically, map failures to specific code locations and logic, and distinguish between syntax errors, logic errors, and algorithmic flaws.

Recognize when a test is wrong rather than the code: the tests were generated before any code and can contain mistaken expected values.

Respond with a JSON object matching this shape: {"failed_tests": [string], "invalid_tests": [{"test_name": string, "reason": string, "correct_expectation": string}], "root_causes": [string], "suggested_fixes": [string], "analysis_summary": string}`

func errorAnalyzerUserPrompt(taskDescription, devPlan, generatedCode, generatedTests, errorLogs string) string {
	return fmt.Sprintf(`MISSION: Analyze test failures and provide comprehensive error analysis.

Task: %s

Development Plan:
%s

Failing Code:
%s

Test Suite:
%s

Error Logs:
%s

STEP 0 — check each failing test against the task before blaming the code:
- Work out the expected value from the task's own rules, not from what the code does.
- If the task's rules produce a different value than the test expects, the test is wrong: record it in "invalid_tests" with the reason and the value the task requires.
- Only flag a test when the task settles the answer. If the task is ambiguous or silent, assume the test is right and the code is wrong.
- Never flag a test merely because the code disagrees with it — the code may be the thing that is wrong.
- A test can be invalid while the code is also wrong: report both.
- "invalid_tests" must always be present; use [] when every failing test is consistent with the task.

Then identify which tests failed and why, the root causes, and specific suggested fixes.`, taskDescription, devPlan, generatedCode, generatedTests, errorLogs)
}

const codeFixerSystemPrompt = `You are an elite Python debugging specialist. Your sole mission: analyze failing code and produce a corrected version that passes ALL tests.

Respond with a JSON object matching this shape: {"code": string}`

func codeFixerUserPrompt(devCode, testCode, errorLogs, taskDescription, devPlan, errorAnalysisText string) string {
	return fmt.Sprintf(`CRITICAL MISSION: Fix the failing code to pass all tests.

Task: %s

Development Plan:
%s

Current Code:
%s

Test Suite (must pass unmodified):
%s

Error Logs:
%s

%s

Produce a corrected, complete main.py that passes all tests.`, taskDescription, devPlan, devCode, testCode, errorLogs, errorAnalysisText)
}

func plannerNode(ctx *agnt5.Context, model agnt5.LanguageModel, taskDescription string) (Plan, error) {
	ctx.Logger().Info("Planning process started")
	plan, err := GenerateStructured[Plan](ctx, model, plannerSystemPrompt, plannerUserPrompt(taskDescription))
	if err != nil {
		ctx.Logger().Error("Planner failed", "error", err)
		return Plan{}, err
	}
	ctx.Logger().Info("Plan generated successfully")
	return plan, nil
}

func testGeneratorNode(ctx *agnt5.Context, model agnt5.LanguageModel, taskDescription, testPlan string) (GeneratedCode, error) {
	ctx.Logger().Info("Generating test suite")
	result, err := GenerateStructured[GeneratedCode](ctx, model, testSystemPrompt, testUserPrompt(taskDescription, testPlan))
	if err != nil {
		return GeneratedCode{}, err
	}
	result.Code = cleanCode(result.Code)
	ctx.Logger().Info("Tests generated", "chars", len(result.Code))
	return result, nil
}

type codeGenInput struct {
	TaskDescription string
	DevPlan         string
	ExecutionStatus string
	GeneratedCode   string
	GeneratedTests  string
	ErrorLogs       string
	ErrorAnalysis   *ErrorAnalysis
}

func codeGeneratorNode(ctx *agnt5.Context, model agnt5.LanguageModel, in codeGenInput) (GeneratedCode, error) {
	var systemPrompt, userPrompt string

	if in.ExecutionStatus != "tests_failed" {
		ctx.Logger().Info("Generating initial code from plan")
		testSuite := in.GeneratedTests
		if testSuite == "" {
			testSuite = "Tests will be validated after implementation."
		}
		systemPrompt = coderSystemPrompt
		userPrompt = coderUserPrompt(in.TaskDescription, in.DevPlan, testSuite)
	} else {
		ctx.Logger().Info("Fixing code based on test failures")
		analysisText := ""
		if in.ErrorAnalysis != nil {
			analysisText = fmt.Sprintf("### ERROR ANALYSIS\n\nFailed Tests: %v\nRoot Causes: %v\nSuggested Fixes: %v\nSummary: %s\n",
				in.ErrorAnalysis.FailedTests, in.ErrorAnalysis.RootCauses, in.ErrorAnalysis.SuggestedFixes, in.ErrorAnalysis.AnalysisSummary)
		}
		systemPrompt = codeFixerSystemPrompt
		userPrompt = codeFixerUserPrompt(in.GeneratedCode, in.GeneratedTests, in.ErrorLogs, in.TaskDescription, in.DevPlan, analysisText)
	}

	result, err := GenerateStructured[GeneratedCode](ctx, model, systemPrompt, userPrompt)
	if err != nil {
		ctx.Logger().Error("Code generation/fixing failed", "error", err)
		return GeneratedCode{}, err
	}
	result.Code = cleanCode(result.Code)
	ctx.Logger().Info("Code processed", "chars", len(result.Code))
	return result, nil
}

func codeSyncNode(ctx *agnt5.Context, e2b *e2bClient, mainCode, testCode, sandboxID string) (SyncResult, error) {
	ctx.Logger().Info("Syncing code and tests to sandbox")
	if mainCode == "" || testCode == "" {
		return SyncResult{}, fmt.Errorf("cannot sync: main_code or test_code is empty")
	}

	var err error
	if sandboxID == "" {
		ctx.Logger().Info("Creating new E2B sandbox")
		sandboxID, err = e2b.createSandbox(ctx)
		if err != nil {
			ctx.Logger().Error("Sandbox creation failed", "error", err)
			return SyncResult{Success: false, Message: err.Error()}, nil
		}
		ctx.Logger().Info("Created sandbox", "sandbox_id", sandboxID)
	} else {
		ctx.Logger().Info("Using existing sandbox", "sandbox_id", sandboxID)
	}

	// A sandbox is created with a 300s timeout, and this workflow retries for
	// far longer than that. Once it expires the ID stays in the state and every
	// later sync failed against a sandbox that no longer exists, so a run that
	// took too long could never recover (AGNT5-1160). A failed write -- of
	// either file -- is taken as "the sandbox is gone": a fresh one costs a
	// few seconds, and both files are written from scratch anyway. The ID that
	// comes back is always the one the files are in, so the workflow state
	// never keeps pointing at a dead sandbox.
	writeBoth := func(id string) error {
		if err := e2b.writeFile(ctx, id, "main.py", mainCode); err != nil {
			return err
		}
		return e2b.writeFile(ctx, id, "test.py", testCode)
	}
	if err := writeBoth(sandboxID); err != nil {
		ctx.Logger().Warn("Sandbox write failed, recreating the sandbox", "sandbox_id", sandboxID, "error", err)
		replacement, createErr := e2b.createSandbox(ctx)
		if createErr != nil {
			return SyncResult{Success: false, Message: fmt.Sprintf("sandbox write failed (%v) and a replacement could not be created: %v", err, createErr)}, nil
		}
		sandboxID = replacement
		ctx.Logger().Info("Recreated sandbox", "sandbox_id", sandboxID)
		if err := writeBoth(sandboxID); err != nil {
			return SyncResult{Success: false, SandboxID: sandboxID, Message: err.Error()}, nil
		}
	}

	ctx.Logger().Info("Code and tests synced successfully")
	return SyncResult{Success: true, SandboxID: sandboxID, Message: "Code and tests synced successfully"}, nil
}

func installDepsNode(ctx *agnt5.Context, e2b *e2bClient, mainCode, sandboxID string) error {
	pkgs := extractThirdPartyImports(mainCode)
	if len(pkgs) == 0 {
		ctx.Logger().Info("No third-party dependencies detected")
		return nil
	}

	ctx.Logger().Info("Installing dependencies", "packages", pkgs)
	command := "pip install -q"
	for _, p := range pkgs {
		command += " " + p
	}
	command += " 2>&1 | tail -5"

	result, err := e2b.runCommand(ctx, sandboxID, command, 120*time.Second)
	if err != nil {
		ctx.Logger().Warn("pip install request failed", "error", err)
		return nil // non-fatal, matching the Python template
	}
	if result.Success {
		ctx.Logger().Info("Dependencies installed", "packages", pkgs)
	} else {
		ctx.Logger().Warn("pip install completed with warnings", "stdout", truncate(result.Stdout, 200))
	}
	return nil
}

func codeExecutorNode(ctx *agnt5.Context, e2b *e2bClient, sandboxID string) (ExecutionResult, error) {
	ctx.Logger().Info("Executing tests in sandbox")
	if sandboxID == "" {
		return ExecutionResult{}, fmt.Errorf("no sandbox_id provided")
	}

	result, err := e2b.runCommand(ctx, sandboxID, "pytest test.py --tb=short -q 2>&1", 30*time.Second)
	if err != nil {
		ctx.Logger().Error("Test execution failed", "error", err)
		return ExecutionResult{Status: "tests_failed", NextAction: "retry_code", ErrorLogs: err.Error()}, nil
	}

	if result.ExitCode == 0 {
		ctx.Logger().Info("All tests passed!")
		return ExecutionResult{Status: "tests_passed", NextAction: "success"}, nil
	}

	// exit_code 1 = test failures, exit_code 2 = collection error (syntax/import
	// error) — both are recoverable; let the error analyzer + code fixer handle them.
	errorOutput := result.Stdout
	if errorOutput == "" {
		errorOutput = result.Stderr
	}
	ctx.Logger().Warn("Tests failed — retry needed", "exit_code", result.ExitCode, "stdout", truncate(result.Stdout, 200))
	return ExecutionResult{Status: "tests_failed", NextAction: "retry_code", ErrorLogs: errorOutput}, nil
}

func errorAnalyzerNode(ctx *agnt5.Context, model agnt5.LanguageModel, taskDescription, devPlan, generatedCode, generatedTests, errorLogs string) (ErrorAnalysis, error) {
	ctx.Logger().Info("Analyzing test failures")
	analysis, err := GenerateStructured[ErrorAnalysis](ctx, model, errorAnalyzerSystemPrompt,
		errorAnalyzerUserPrompt(taskDescription, devPlan, generatedCode, generatedTests, errorLogs))
	if err != nil {
		ctx.Logger().Error("Error analysis failed", "error", err)
		return ErrorAnalysis{}, err
	}
	ctx.Logger().Info("Error analysis complete", "failed_tests", len(analysis.FailedTests))
	return analysis, nil
}

const testRepairSystemPrompt = `You are a meticulous Python Test Engineer. You correct mistaken expectations in an existing pytest suite.

The suite was generated before the implementation, and an error analysis has identified specific tests whose expected values contradict the task.

Your rules:
- Change ONLY the tests you are given, and within them only what makes the expectation match the task
- Keep every other test exactly as it is, character for character
- Never delete, skip, xfail or weaken a test; never loosen an assertion to make it pass (no wider tolerances, no removed checks)
- Keep the imports, fixtures and structure of the file
- If a listed test's correct value is not settled by the task, leave that test unchanged

Respond with a JSON object matching this shape: {"code": string}`

func testRepairUserPrompt(taskDescription, generatedTests, invalidTests string) string {
	return fmt.Sprintf(`MISSION: Correct the listed tests so their expectations match the task.

Original Task:
%s

Current Test Suite:
%s

Tests With Invalid Expectations:
%s

1. For each listed test, recompute the expected value from the Original Task and update only that expectation.
2. Leave every unlisted test exactly as it is.
3. Do not remove or weaken any test.

Return the complete corrected test file.`, taskDescription, generatedTests, invalidTests)
}

// testRepairNode corrects the tests the error analysis found to contradict the
// task. A rejected repair keeps the original tests: a wrong repair is worse
// than none.
func testRepairNode(ctx *agnt5.Context, model agnt5.LanguageModel, taskDescription, generatedTests string, invalidTests []InvalidTest) (TestRepair, error) {
	targets := map[string]bool{}
	var names, listing []string
	for _, t := range invalidTests {
		name := baseTestName(t.TestName)
		targets[name] = true
		names = append(names, name)
		listing = append(listing, fmt.Sprintf("- `%s`: %s Correct expectation: %s", t.TestName, t.Reason, t.CorrectExpectation))
	}
	sort.Strings(names)
	ctx.Logger().Info("Repairing tests with invalid expectations", "tests", names)

	repaired, err := GenerateStructured[GeneratedCode](ctx, model, testRepairSystemPrompt,
		testRepairUserPrompt(taskDescription, generatedTests, strings.Join(listing, "\n")))
	if err != nil {
		ctx.Logger().Error("Test repair failed", "error", err)
		return TestRepair{}, err
	}

	candidate := cleanCode(repaired.Code)
	accepted, why, changed := checkTestRepair(generatedTests, candidate, targets)
	if !accepted {
		ctx.Logger().Warn("Test repair rejected, keeping the original tests", "reason", why)
		return TestRepair{Accepted: false, Code: generatedTests, Reason: why}, nil
	}
	ctx.Logger().Info("Repaired tests", "tests", changed)
	return TestRepair{Accepted: true, Code: candidate, Repaired: changed}, nil
}

func finalResponseNode(ctx *agnt5.Context, model agnt5.LanguageModel, taskDescription, generatedCode string) (FinalResponse, error) {
	ctx.Logger().Info("Generating documentation")

	temperature := 0.0
	maxTokens := maxOutputTokens
	resp, err := model.Generate(ctx, agnt5.GenerateRequest{
		Messages: []agnt5.Message{
			{Role: agnt5.MessageRoleSystem, Content: markdownSystemPrompt},
			{Role: agnt5.MessageRoleUser, Content: markdownUserPrompt(taskDescription, generatedCode)},
		},
		Temperature: &temperature,
		MaxTokens:   &maxTokens,
	})
	if err != nil {
		ctx.Logger().Error("Documentation generation failed", "error", err)
		return FinalResponse{}, err
	}

	if err := os.WriteFile("final_response.md", []byte(resp.Content), 0o644); err != nil {
		ctx.Logger().Warn("Failed to save documentation to disk", "error", err)
	} else {
		ctx.Logger().Info("Documentation saved to final_response.md")
	}
	return FinalResponse{MarkdownContent: resp.Content}, nil
}
