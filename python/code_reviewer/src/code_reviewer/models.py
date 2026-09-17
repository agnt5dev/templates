from enum import Enum
from typing import List
from pydantic import BaseModel, ConfigDict, Field


def _require_all_properties(schema: dict, _model: type) -> None:
    """Keep every property in the JSON schema's `required` list.

    The review fields default so a partial answer (findings but no summary)
    is kept instead of discarded (AGNT5-1165). Pydantic then drops defaulted
    fields from `required`, and OpenAI structured outputs rejects a schema
    whose `required` does not list every property ("Missing 'filename'"), so
    the review never ran (AGNT5-1189). Defaults stay for parsing; the schema
    sent to the model still asks for every field.
    """
    schema["required"] = list(schema.get("properties", {}))


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NITPICK = "nitpick"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Severity
    category: str = Field(description="correctness, performance, quality, standards, or security")
    description: str = Field(description="Clear description of the issue")
    line_reference: str = Field(description="File and line reference e.g. 'auth.py:45-52'. Use empty string if not applicable.")
    suggestion: str = Field(description="Concrete fix suggestion")


# Findings are the substance of a review; the rest is metadata. Every field
# but findings defaults, because a required `summary` meant a response
# carrying real critical findings and no summary failed validation, and after
# the retries those findings were discarded -- hiding exactly what the review
# exists to surface (AGNT5-1165).
class FileReview(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_require_all_properties)

    filename: str = Field(default="", description="File reviewed")
    language: str = Field(default="unknown", description="Programming language detected")
    findings: List[Finding] = Field(default_factory=list, description="List of findings. Use empty list [] if no issues found.")
    summary: str = Field(default="", description="One-sentence summary of the file review")

    def is_empty(self) -> bool:
        """True when the model answered with nothing: no findings and no summary.
        A clean file legitimately has no findings, so the summary is the evidence."""
        return not self.findings and not self.summary.strip()


class SecurityReview(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_require_all_properties)

    findings: List[Finding] = Field(default_factory=list, description="Security findings. Use empty list [] if no issues found.")
    overall_risk: str = Field(default="", description="low, medium, high, or critical")
    summary: str = Field(default="", description="Summary of security posture")

    def is_empty(self) -> bool:
        return not self.findings and not self.summary.strip() and not self.overall_risk.strip()

    def risk_or_from_findings(self) -> str:
        """The model's overall_risk, or one derived from the worst finding when it
        was left out, so a batch that reported real findings still counts."""
        if self.overall_risk.strip():
            return self.overall_risk.strip()
        rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        by_severity = {"critical": "critical", "major": "high", "minor": "medium"}
        worst = "low"
        for finding in self.findings:
            level = by_severity.get(str(getattr(finding.severity, "value", finding.severity)).lower())
            if level and rank[level] > rank[worst]:
                worst = level
        return worst


class TechStack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    test_files_present: bool = Field(default=False)
    config_files: List[str] = Field(default_factory=list)
    notes: str = Field(default="")
