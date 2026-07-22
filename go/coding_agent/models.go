// Data models for the coding agent's structured LLM outputs and sandbox
// results.
package main

// Plan holds the development and test plans produced by the planner node.
type Plan struct {
	DevPlan  string `json:"dev_plan"`
	TestPlan string `json:"test_plan"`
}

// GeneratedCode wraps a single generated source file.
type GeneratedCode struct {
	Code string `json:"code"`
}

// ErrorAnalysis is the structured result of analyzing a failing test run.
type ErrorAnalysis struct {
	FailedTests     []string `json:"failed_tests"`
	RootCauses      []string `json:"root_causes"`
	SuggestedFixes  []string `json:"suggested_fixes"`
	AnalysisSummary string   `json:"analysis_summary"`
}

// SyncResult is the result of syncing generated code to the sandbox.
type SyncResult struct {
	Success   bool   `json:"success"`
	SandboxID string `json:"sandbox_id,omitempty"`
	Message   string `json:"message,omitempty"`
}

// ExecutionResult is the result of running the test suite in the sandbox.
type ExecutionResult struct {
	Status     string `json:"status"`      // tests_passed, tests_failed, or error
	NextAction string `json:"next_action"` // success, retry_code, or abort
	ErrorLogs  string `json:"error_logs,omitempty"`
}

// FinalResponse is the generated documentation.
type FinalResponse struct {
	MarkdownContent string `json:"markdown_content"`
}

// WorkflowResult is the final result of the complete coding agent workflow.
type WorkflowResult struct {
	Success       bool   `json:"success"`
	Task          string `json:"task"`
	Iterations    int    `json:"iterations"`
	Code          string `json:"code,omitempty"`
	Tests         string `json:"tests,omitempty"`
	SandboxID     string `json:"sandbox_id,omitempty"`
	Documentation string `json:"documentation,omitempty"`
	Error         string `json:"error,omitempty"`
	ErrorLogs     string `json:"error_logs,omitempty"`
}
