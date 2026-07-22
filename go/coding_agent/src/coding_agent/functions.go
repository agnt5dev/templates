// Function nodes for the coding agent workflow. Prompts here are condensed
// from the Python/TypeScript templates' much longer originals, preserving
// the same role, constraints, and required JSON output shape.
package coding_agent

import (
	"fmt"
	"os"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

const plannerSystemPrompt = `You are an Expert Planning Agent that creates perfectly synchronized development and test plans for Python projects.

Produce two plans that describe exactly the same public interface (function names, signatures, and behavior), so that code written from the dev plan will pass tests written from the test plan without any mismatch.

Respond with a JSON object matching this shape: {"dev_plan": string, "test_plan": string}`

func plannerUserPrompt(taskDescription string) string {
	return fmt.Sprintf(`MISSION: Create perfectly synchronized development and test plans.

Task: %s

Produce:
1. A development plan describing the module's public functions/classes, their signatures, parameters, return types, and behavior (including edge cases and error handling).
2. A test plan describing the pytest test cases that verify every behavior in the development plan, using the exact same function/class names and signatures.`, taskDescription)
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

Write a complete test.py file that imports from main.py and tests every behavior in the test plan, including edge cases and error conditions.`, taskDescription, testPlan)
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

Respond with a JSON object matching this shape: {"failed_tests": [string], "root_causes": [string], "suggested_fixes": [string], "analysis_summary": string}`

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

Identify which tests failed and why, the root causes, and specific suggested fixes.`, taskDescription, devPlan, generatedCode, generatedTests, errorLogs)
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

	if err := e2b.writeFile(ctx, sandboxID, "main.py", mainCode); err != nil {
		return SyncResult{Success: false, SandboxID: sandboxID, Message: err.Error()}, nil
	}
	if err := e2b.writeFile(ctx, sandboxID, "test.py", testCode); err != nil {
		return SyncResult{Success: false, SandboxID: sandboxID, Message: err.Error()}, nil
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

func finalResponseNode(ctx *agnt5.Context, model agnt5.LanguageModel, taskDescription, generatedCode string) (FinalResponse, error) {
	ctx.Logger().Info("Generating documentation")

	temperature := 0.0
	resp, err := model.Generate(ctx, agnt5.GenerateRequest{
		Messages: []agnt5.Message{
			{Role: agnt5.MessageRoleSystem, Content: markdownSystemPrompt},
			{Role: agnt5.MessageRoleUser, Content: markdownUserPrompt(taskDescription, generatedCode)},
		},
		Temperature: &temperature,
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
