"""
Diff parser tool.

Pure function `parse_unified_diff` is unit-testable; the @tool wrapper
exposes it to Strands agents. Hand-rolled regex for diff parsing is
forbidden — `unidiff` handles renames, binary files, and missing-newline-
at-EOF correctly.
"""
from pathlib import Path

from strands import tool
from unidiff import PatchSet

from app.models import AddedLine, Hunk


def parse_unified_diff(diff_text: str) -> list[Hunk]:
    """
    Parse a unified diff string into a list of Hunk records.

    Each hunk corresponds to one @@ block in one file. We emit only the
    added lines (post-change) because reviewer agents must comment only
    on changed lines, never on unchanged context.
    """
    patch = PatchSet(diff_text)
    hunks: list[Hunk] = []

    for patched_file in patch:
        if patched_file.is_binary_file:
            continue

        file_path = patched_file.target_file.removeprefix("b/")

        for hunk in patched_file:
            added = [
                AddedLine(line_no=line.target_line_no, text=line.value.rstrip("\n"))
                for line in hunk
                if line.is_added and line.target_line_no is not None
            ]
            if not added:
                # pure deletion or context-only — no changed lines to review
                continue

            hunks.append(Hunk(
                file_path=file_path,
                start_line=hunk.target_start,
                line_count=hunk.target_length,
                added_lines=added,
                context_header=str(hunk).splitlines()[0],
            ))

    return hunks


@tool
def load_pr_diff(pr_directory: str) -> list[dict]:
    """
    Load and parse a PR's unified diff from its corpus directory.

    Args:
        pr_directory: Absolute or relative path to a `data/prs/<pr_id>/`
            folder containing `pr.diff` and `metadata.json`.

    Returns:
        A list of hunk dicts (Pydantic-serialized) ready for an LLM to read.
        Each entry has: file_path, start_line, line_count, added_lines,
        context_header.
    """
    diff_path = Path(pr_directory) / "pr.diff"
    if not diff_path.exists():
        raise FileNotFoundError(f"No pr.diff under {pr_directory!r}")

    hunks = parse_unified_diff(diff_path.read_text())
    return [h.model_dump() for h in hunks]
