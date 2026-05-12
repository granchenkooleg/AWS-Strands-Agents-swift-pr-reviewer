"""
Pydantic contracts that cross agent boundaries.

Strands' Agent supports `structured_output_model=...`, so reviewer agents
return Pydantic instances directly. We avoid hand-rolled JSON parsing.
"""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


Severity = Literal["blocker", "major", "minor", "nit"]
Category = Literal["correctness", "style", "api_design", "test_coverage"]


class AddedLine(BaseModel):
    """One added ('+') line with its post-change line number."""
    model_config = ConfigDict(frozen=True)
    line_no: int = Field(ge=1, description="target line number in the post-change file")
    text: str


class Hunk(BaseModel):
    """One contiguous block of changed lines in a single file."""
    model_config = ConfigDict(frozen=True)

    file_path: str
    start_line: int = Field(ge=1, description="hunk's first line in the post-change file")
    line_count: int = Field(ge=1)
    added_lines: list[AddedLine] = Field(description="'+' lines with target line numbers, for citation")
    raw_hunk: str = Field(description="full unified-diff hunk text incl. @@ header, +, -, and context lines")


class Finding(BaseModel):
    """One reviewer comment on one line of one file."""
    file_path: str
    line: int = Field(ge=1)
    severity: Severity
    category: Category
    title: str = Field(max_length=120)
    body: str = Field(max_length=600)
    suggested_action: str = Field(max_length=300)


class ReviewerOutput(BaseModel):
    """
    What every reviewer agent emits. Strands enforces this schema via
    `structured_output_model`; on validation failure Strands re-prompts
    automatically.
    """
    findings: list[Finding] = Field(default_factory=list)
    confidence_note: str = Field(default="", max_length=200)


class ReviewReport(BaseModel):
    """Final post-aggregation, post-HITL report shown to the user."""
    pr_id: str
    findings: list[Finding]
    rejected_findings: list[Finding] = Field(default_factory=list)
    rendered_markdown: str = ""
