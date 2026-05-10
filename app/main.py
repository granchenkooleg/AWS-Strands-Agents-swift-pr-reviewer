"""
CLI entry point — slice 3.

    python -m app.main --pr data/prs/001_force_unwrap

Slice 3 replaces the sequential reviewer loop with a Strands GraphBuilder
topology: all four reviewers run in parallel as entry-point nodes, results
are aggregated by plain Python, and the findings table includes a Category
column.
"""
import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.agents import aggregator
from app.graph import run_reviewers
from app.models import Finding
from app.tools.parse_diff import parse_unified_diff


SEVERITY_COLOR = {
    "blocker": "bold red",
    "major": "red1",
    "minor": "yellow",
    "nit": "dim white",
}


def _load_pr(pr_dir: Path) -> tuple[str, dict]:
    diff_path = pr_dir / "pr.diff"
    meta_path = pr_dir / "metadata.json"
    if not diff_path.exists() or not meta_path.exists():
        sys.exit(f"error: {pr_dir} missing pr.diff or metadata.json")
    return diff_path.read_text(), json.loads(meta_path.read_text())


def _render(console: Console, pr_id: str, findings: list[Finding]) -> None:
    if not findings:
        console.print(Panel(
            "[green]No issues found.[/green]",
            title=f"[bold]Review — {pr_id}[/bold]",
            border_style="green",
        ))
        return

    table = Table(title=f"Review — {pr_id}", show_lines=True)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("Location", no_wrap=True)
    table.add_column("Title")
    for f in findings:
        color = SEVERITY_COLOR.get(f.severity, "white")
        table.add_row(
            f"[{color}]{f.severity}[/{color}]",
            f.category,
            f"{f.file_path}:{f.line}",
            f.title,
        )
    console.print(table)
    for f in findings:
        color = SEVERITY_COLOR.get(f.severity, "white")
        console.print(Panel(
            f"{f.body}\n\n[bold]Suggested:[/bold] {f.suggested_action}",
            title=f"[{color}]{f.severity}[/{color}] {f.file_path}:{f.line} — {f.title}",
            border_style=color,
            padding=(0, 1),
        ))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Swift PR reviewer over a synthetic PR (slice 3)."
    )
    parser.add_argument(
        "--pr",
        required=True,
        type=Path,
        help="Path to a data/prs/<pr_id>/ directory.",
    )
    args = parser.parse_args()

    console = Console()
    diff_text, metadata = _load_pr(args.pr)
    pr_id = metadata.get("pr_id", args.pr.name)

    hunks = parse_unified_diff(diff_text)
    if not hunks:
        console.print("[yellow]No changed lines parsed from diff. Nothing to review.[/yellow]")
        return 0

    console.print(f"[dim]Parsed {len(hunks)} hunk(s) across "
                  f"{len({h.file_path for h in hunks})} file(s). "
                  f"Running four reviewers in parallel via Graph…[/dim]")

    try:
        outputs = run_reviewers(hunks)
    except Exception as e:
        console.print(f"[red]Graph execution failed:[/red] {type(e).__name__}: {e}")
        return 1

    console.print(f"[dim]{len(outputs)}/4 reviewer(s) returned findings.[/dim]")
    findings = aggregator.aggregate(outputs)
    _render(console, pr_id, findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
