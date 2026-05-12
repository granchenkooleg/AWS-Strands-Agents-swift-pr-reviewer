"""
Diff parser.

`parse_unified_diff` is a pure function called directly by main.py after the
diff loader (MCP agent or direct read) returns raw text. Hand-rolled regex
for diff parsing is forbidden — `unidiff` handles renames, binary files,
and missing-newline-at-EOF correctly.
"""
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
                raw_hunk=str(hunk).rstrip("\n"),
            ))

    return hunks
