"""Data models for the coding agent."""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Plan(BaseModel):
    """Plan model containing development and test plans."""

    model_config = ConfigDict(extra='forbid')

    dev_plan: str
    test_plan: str


class GeneratedCode(BaseModel):
    """Model for generated code."""

    model_config = ConfigDict(extra='forbid')

    code: str


class InvalidTest(BaseModel):
    """A failing test whose own expectation contradicts the task."""

    model_config = ConfigDict(extra='forbid')

    test_name: str
    reason: str
    correct_expectation: str


class ErrorAnalysis(BaseModel):
    """Model for error analysis results."""

    model_config = ConfigDict(extra='forbid')

    failed_tests: list[str]
    # Failing tests that are wrong rather than the code: their expected value
    # contradicts the task. Generated tests are written before any code and can
    # be wrong; without this the fixer bends correct code toward a bad test.
    invalid_tests: list[InvalidTest]
    root_causes: list[str]
    suggested_fixes: list[str]
    analysis_summary: str


class TestRepair(BaseModel):
    """Outcome of correcting tests the error analysis flagged as invalid."""

    model_config = ConfigDict(extra='forbid')

    accepted: bool
    code: str
    repaired: list[str]
    reason: str


class SyncResult(BaseModel):
    """Result from syncing code to sandbox."""

    model_config = ConfigDict(extra='forbid')

    success: bool
    sandbox_id: Optional[str] = None
    message: Optional[str] = None


class ExecutionResult(BaseModel):
    """Result from executing tests in sandbox."""

    model_config = ConfigDict(extra='forbid')

    status: str = Field(description="Execution status: tests_passed, tests_failed, or error")
    next_action: str = Field(description="Next action: success, retry_code, or abort")
    test_results: Optional[dict] = Field(default=None, description="Raw test execution results")
    error_logs: Optional[str] = Field(default=None, description="Error logs if tests failed")


class FinalResponse(BaseModel):
    """Final documentation response."""

    model_config = ConfigDict(extra='forbid')

    markdown_content: str


class WorkflowResult(BaseModel):
    """Result from the complete coding agent workflow."""

    model_config = ConfigDict(extra='forbid')

    success: bool = Field(description="Whether the workflow completed successfully")
    task: str = Field(description="The original task description")
    iterations: int = Field(description="Number of iterations executed")
    code: Optional[str] = Field(default=None, description="Final generated code")
    tests: Optional[str] = Field(default=None, description="Final generated tests")
    sandbox_id: Optional[str] = Field(default=None, description="E2B sandbox ID used")
    documentation: Optional[str] = Field(default=None, description="Generated documentation (markdown)")
    error: Optional[str] = Field(default=None, description="Error message if workflow failed")
    error_logs: Optional[str] = Field(default=None, description="Last test/execution error logs")
    tests_repaired: list[str] = Field(
        default_factory=list,
        description="Generated tests whose expected values were corrected against the task. "
        "A pass that needed these is still a pass, but the tests changed.",
    )
