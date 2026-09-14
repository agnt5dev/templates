// Data models for the coding agent's structured LLM outputs and sandbox
// results.
package coding_agent

// Plan holds the development and test plans produced by the planner node.
type Plan struct {
	DevPlan  string `json:"dev_plan"`
	TestPlan string `json:"test_plan"`
}

// GeneratedCode wraps a single generated source file.
type GeneratedCode struct {
	Code string `json:"code"`
}

// InvalidTest is a failing test whose expected value contradicts the task —
// the test is wrong, not the code.
type InvalidTest struct {
	TestName           string `json:"test_name"`
	Reason             string `json:"reason"`
	CorrectExpectation string `json:"correct_expectation"`
}

// ErrorAnalysis is the structured result of analyzing a failing test run.
type ErrorAnalysis struct {
	FailedTests     []string      `json:"failed_tests"`
	InvalidTests    []InvalidTest `json:"invalid_tests"`
	RootCauses      []string      `json:"root_causes"`
	SuggestedFixes  []string      `json:"suggested_fixes"`
	AnalysisSummary string        `json:"analysis_summary"`
}

// TestRepair is the outcome of correcting tests the analysis flagged as
// invalid. A rejected repair keeps the original suite in Code.
type TestRepair struct {
	Accepted bool     `json:"accepted"`
	Code     string   `json:"code"`
	Repaired []string `json:"repaired"`
	Reason   string   `json:"reason"`
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
	// TestsRepaired names generated tests whose expectations were corrected
	// during the run, so a pass that needed them changed is visible.
	TestsRepaired []string `json:"tests_repaired,omitempty"`
}
