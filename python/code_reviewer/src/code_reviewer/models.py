from enum import Enum
from typing import List
from pydantic import BaseModel, ConfigDict, Field


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


class FileReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(description="File reviewed")
    language: str = Field(description="Programming language detected")
    findings: List[Finding] = Field(description="List of findings. Use empty list [] if no issues found.")
    summary: str = Field(description="One-sentence summary of the file review")


class SecurityReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: List[Finding] = Field(description="Security findings. Use empty list [] if no issues found.")
    overall_risk: str = Field(description="low, medium, high, or critical")
    summary: str = Field(description="Summary of security posture")


class TechStack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    test_files_present: bool = Field(default=False)
    config_files: List[str] = Field(default_factory=list)
    notes: str = Field(default="")
