/**
 * Data models and JSON schemas for the coding agent workflow.
 *
 * Each interface has a corresponding JSON schema object used for
 * LM structured output (responseFormat with formatType: 'json_schema').
 */

// ============================================================================
// Interfaces
// ============================================================================

export interface Plan {
  dev_plan: string;
  test_plan: string;
}

export interface GeneratedCode {
  code: string;
}

/** A failing test whose own expectation contradicts the task. */
export interface InvalidTest {
  test_name: string;
  reason: string;
  correct_expectation: string;
}

export interface ErrorAnalysis {
  failed_tests: string[];
  /**
   * Failing tests that are wrong rather than the code: their expected value
   * contradicts the task. Generated tests are written before any code and can
   * be wrong; without this the fixer bends correct code toward a bad test.
   */
  invalid_tests: InvalidTest[];
  root_causes: string[];
  suggested_fixes: string[];
  analysis_summary: string;
}

/** Outcome of correcting tests the error analysis flagged as invalid. */
export interface TestRepair {
  accepted: boolean;
  code: string;
  repaired: string[];
  reason: string;
}

export interface SyncResult {
  success: boolean;
  sandbox_id?: string;
  message?: string;
}

export interface ExecutionResult {
  /** Execution status: tests_passed, tests_failed, or error */
  status: string;
  /** Next action: success, retry_code, or abort */
  next_action: string;
  /** Raw test execution results */
  test_results?: Record<string, any>;
  /** Error logs if tests failed */
  error_logs?: string;
}

export interface FinalResponse {
  markdown_content: string;
}

export interface WorkflowResult {
  /** Whether the workflow completed successfully */
  success: boolean;
  /** The original task description */
  task: string;
  /** Number of iterations executed */
  iterations: number;
  /** Final generated code */
  code?: string;
  /** Final generated tests */
  tests?: string;
  /** E2B sandbox ID used */
  sandbox_id?: string;
  /** Generated documentation (markdown) */
  documentation?: string;
  /** Error message if workflow failed */
  error?: string;
  /** Last test/execution error logs */
  error_logs?: string;
  /**
   * Generated tests whose expected values were corrected against the task.
   * A pass that needed these is still a pass, but the tests changed.
   */
  tests_repaired?: string[];
}

// ============================================================================
// JSON Schemas (for LM structured output)
// ============================================================================

export const PLAN_SCHEMA = {
  type: 'object',
  properties: {
    dev_plan: {
      type: 'string',
      description: 'Complete development plan with function specs, algorithms, and edge cases',
    },
    test_plan: {
      type: 'string',
      description: 'Complete test plan with test suites for all functions',
    },
  },
  required: ['dev_plan', 'test_plan'],
  additionalProperties: false,
};

export const GENERATED_CODE_SCHEMA = {
  type: 'object',
  properties: {
    code: {
      type: 'string',
      description: 'Complete Python source code, no markdown fences, newlines escaped as \\n',
    },
  },
  required: ['code'],
  additionalProperties: false,
};

export const ERROR_ANALYSIS_SCHEMA = {
  type: 'object',
  properties: {
    failed_tests: {
      type: 'array',
      items: { type: 'string' },
      description: 'List of failing test function names',
    },
    invalid_tests: {
      type: 'array',
      description:
        'Failing tests whose expected value contradicts the task (empty when the tests are consistent with it)',
      items: {
        type: 'object',
        properties: {
          test_name: { type: 'string' },
          reason: { type: 'string' },
          correct_expectation: { type: 'string' },
        },
        required: ['test_name', 'reason', 'correct_expectation'],
        additionalProperties: false,
      },
    },
    root_causes: {
      type: 'array',
      items: { type: 'string' },
      description: 'Specific explanations of each root cause category',
    },
    suggested_fixes: {
      type: 'array',
      items: { type: 'string' },
      description: 'Concrete recommendations for fixing each issue',
    },
    analysis_summary: {
      type: 'string',
      description: 'Overall assessment of what is wrong and the strategy to fix it',
    },
  },
  required: ['failed_tests', 'invalid_tests', 'root_causes', 'suggested_fixes', 'analysis_summary'],
  additionalProperties: false,
};
