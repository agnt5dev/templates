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

export interface ErrorAnalysis {
  failed_tests: string[];
  root_causes: string[];
  suggested_fixes: string[];
  analysis_summary: string;
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
  required: ['failed_tests', 'root_causes', 'suggested_fixes', 'analysis_summary'],
  additionalProperties: false,
};
