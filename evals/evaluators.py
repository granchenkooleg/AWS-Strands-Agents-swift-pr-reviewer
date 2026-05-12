"""
Eval scoring for the Swift PR reviewer.

Matching rule (single source of truth):
  An emitted Finding matches an ExpectedFinding when ALL of:
    - file_path equal
    - line within line_tolerance (default ±0 — exact)
    - category equal
    - title contains at least one of title_keywords (case-insensitive)

Severity match is reported separately from match/no-match; a finding that
matches but has wrong severity counts as a TP for recall/precision but
contributes 0 to severity_match_rate.
"""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

from app.models import Finding, Severity, Category


class ExpectedFinding(BaseModel):
    """One expected finding from a ground_truth.json file."""
    model_config = ConfigDict(frozen=True)

    file_path: str
    line: int = Field(ge=1)
    severity: Severity
    category: Category
    title_keywords: list[str] = Field(min_length=1)
    rationale: str = ""


class GroundTruth(BaseModel):
    """Schema for data/prs/<pr_id>/ground_truth.json."""
    model_config = ConfigDict(extra="allow")  # tolerate must_not_flag etc.

    pr_id: str
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)


class MatchedPair(BaseModel):
    """One emitted finding matched to one expected finding."""
    emitted: Finding
    expected: ExpectedFinding
    severity_match: bool


class PREvalResult(BaseModel):
    """Per-PR scoring output."""
    pr_id: str
    n_expected: int
    n_emitted: int
    n_matched: int            # TP: emitted matched an expected
    n_severity_correct: int   # of n_matched, how many had correct severity
    matched: list[MatchedPair] = Field(default_factory=list)  # all TP pairs
    missing: list[ExpectedFinding]   # expected with no match (false negatives)
    extra: list[Finding]             # emitted with no match (false positives)

    @property
    def recall(self) -> float:
        return self.n_matched / self.n_expected if self.n_expected else 1.0

    @property
    def precision(self) -> float:
        return self.n_matched / self.n_emitted if self.n_emitted else 1.0

    @property
    def severity_match_rate(self) -> float:
        return self.n_severity_correct / self.n_matched if self.n_matched else 1.0


class AggregateEvalResult(BaseModel):
    """Roll-up across all PRs."""
    n_prs: int
    n_expected_total: int
    n_emitted_total: int
    n_matched_total: int
    n_severity_correct_total: int

    @property
    def recall(self) -> float:
        return self.n_matched_total / self.n_expected_total if self.n_expected_total else 1.0

    @property
    def precision(self) -> float:
        return self.n_matched_total / self.n_emitted_total if self.n_emitted_total else 1.0

    @property
    def severity_match_rate(self) -> float:
        return self.n_severity_correct_total / self.n_matched_total if self.n_matched_total else 1.0


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _is_match(emitted: Finding, expected: ExpectedFinding, line_tolerance: int = 0) -> bool:
    """Does this emitted Finding satisfy this ExpectedFinding?"""
    if emitted.file_path != expected.file_path:
        return False
    if abs(emitted.line - expected.line) > line_tolerance:
        return False
    if emitted.category != expected.category:
        return False
    title_lc = emitted.title.lower()
    return any(kw.lower() in title_lc for kw in expected.title_keywords)


def score_pr(
    pr_id: str,
    emitted: list[Finding],
    ground_truth: GroundTruth,
    line_tolerance: int = 0,
) -> PREvalResult:
    """
    Score one PR's emitted findings against its ground truth.

    Greedy 1-to-1 matching: each expected finding is matched to at most one
    emitted finding, and vice versa. Order of expected_findings determines
    matching priority — earlier expected finds first dibs.
    """
    expected_list = list(ground_truth.expected_findings)
    unmatched_emitted = list(emitted)
    missing: list[ExpectedFinding] = []
    matched_pairs: list[tuple[Finding, ExpectedFinding]] = []

    for exp in expected_list:
        match_idx = next(
            (i for i, e in enumerate(unmatched_emitted) if _is_match(e, exp, line_tolerance)),
            None,
        )
        if match_idx is None:
            missing.append(exp)
        else:
            matched_pairs.append((unmatched_emitted.pop(match_idx), exp))

    matched_records = [
        MatchedPair(
            emitted=e,
            expected=exp,
            severity_match=(e.severity == exp.severity),
        )
        for e, exp in matched_pairs
    ]
    n_severity_correct = sum(1 for m in matched_records if m.severity_match)

    return PREvalResult(
        pr_id=pr_id,
        n_expected=len(expected_list),
        n_emitted=len(emitted),
        n_matched=len(matched_records),
        n_severity_correct=n_severity_correct,
        matched=matched_records,
        missing=missing,
        extra=unmatched_emitted,
    )


def aggregate(results: list[PREvalResult]) -> AggregateEvalResult:
    return AggregateEvalResult(
        n_prs=len(results),
        n_expected_total=sum(r.n_expected for r in results),
        n_emitted_total=sum(r.n_emitted for r in results),
        n_matched_total=sum(r.n_matched for r in results),
        n_severity_correct_total=sum(r.n_severity_correct for r in results),
    )
