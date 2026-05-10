"""
Plain-Python aggregator — no Strands Agent (that is Slice 4).

Deduplicates findings across reviewers and sorts by severity.
"""
from app.models import Finding, ReviewerOutput


SEVERITY_RANK = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}


def aggregate(outputs: list[ReviewerOutput]) -> list[Finding]:
    """
    Merge findings from all reviewers, dedup, and sort.

    Dedup key: (file_path, line, category) — when two reviewers flag the same
    key, keep the one with higher severity (lower SEVERITY_RANK value).
    """
    best: dict[tuple, Finding] = {}
    for output in outputs:
        for f in output.findings:
            key = (f.file_path, f.line, f.category)
            if key not in best or SEVERITY_RANK[f.severity] < SEVERITY_RANK[best[key].severity]:
                best[key] = f
    return sorted(
        best.values(),
        key=lambda f: (SEVERITY_RANK[f.severity], f.file_path, f.line),
    )
