"""
Eval harness entrypoint.

    python -m evals.run_evals
    python -m evals.run_evals --pr-dir data/prs/001_force_unwrap   # single PR
    python -m evals.run_evals --line-tolerance 1                    # loosen line match

For each PR under `data/prs/`:
  1. Load pr.diff + ground_truth.json.
  2. Run the four reviewers via the existing reviewer Graph (no HITL).
  3. Aggregate findings via the existing Python aggregator.
  4. Score emitted vs expected with evals.evaluators.score_pr.

Snapshots results to evals/results/<timestamp>.json for tracking over time.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from app.agents import aggregator
from app.graph import run_reviewers
from app.hooks.instrumentation import RunLogger
from app.tools.parse_diff import parse_unified_diff

from evals.evaluators import (
    AggregateEvalResult,
    GroundTruth,
    PREvalResult,
    aggregate,
    score_pr,
)


_PRS_ROOT = Path(__file__).parent.parent / "data" / "prs"
_RESULTS_DIR = Path(__file__).parent / "results"


def _discover_prs(root: Path) -> list[Path]:
    """Every immediate subdirectory of data/prs that contains a pr.diff."""
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "pr.diff").exists())


def _load_ground_truth(pr_dir: Path) -> GroundTruth:
    gt_path = pr_dir / "ground_truth.json"
    if not gt_path.exists():
        raise FileNotFoundError(f"{pr_dir}/ground_truth.json missing")
    return GroundTruth(**json.loads(gt_path.read_text()))


def _run_pipeline_for(pr_dir: Path, run_logger: RunLogger) -> list:
    """Parse diff, fan out reviewers in parallel, aggregate. No HITL."""
    diff_text = (pr_dir / "pr.diff").read_text()
    hunks = parse_unified_diff(diff_text)
    if not hunks:
        return []
    outputs = run_reviewers(hunks, agent_hooks=[run_logger])
    return aggregator.aggregate(outputs)


def _render_pr_row(console: Console, r: PREvalResult) -> None:
    rec = f"{r.recall:.2f}"
    prec = f"{r.precision:.2f}"
    sev = f"{r.severity_match_rate:.2f}"
    console.print(
        f"  [bold]{r.pr_id}[/bold]  "
        f"expected={r.n_expected:>2}  emitted={r.n_emitted:>2}  "
        f"matched={r.n_matched:>2}  "
        f"R={rec}  P={prec}  Sev={sev}"
    )
    if r.missing:
        for m in r.missing:
            console.print(f"    [red]missing[/red]  {m.file_path}:{m.line} "
                          f"[{m.severity}/{m.category}] {m.title_keywords}")
    if r.extra:
        for e in r.extra:
            console.print(f"    [yellow]extra[/yellow]    {e.file_path}:{e.line} "
                          f"[{e.severity}/{e.category}] {e.title}")
    # surface severity mismatches among matched pairs — useful for steering tuning
    for m in r.matched:
        if not m.severity_match:
            console.print(
                f"    [magenta]sev[/magenta]      {m.emitted.file_path}:{m.emitted.line} "
                f"[{m.expected.category}] expected={m.expected.severity} "
                f"got={m.emitted.severity}"
            )


def _render_aggregate(console: Console, agg: AggregateEvalResult) -> None:
    table = Table(title="Aggregate", show_header=True)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("PRs scored",        str(agg.n_prs))
    table.add_row("Expected findings", str(agg.n_expected_total))
    table.add_row("Emitted findings",  str(agg.n_emitted_total))
    table.add_row("Matched (TP)",      str(agg.n_matched_total))
    table.add_row("Recall",            f"{agg.recall:.3f}")
    table.add_row("Precision",         f"{agg.precision:.3f}")
    table.add_row("Severity match",    f"{agg.severity_match_rate:.3f}")
    console.print(table)


def _snapshot(results: list[PREvalResult], agg: AggregateEvalResult, run_id: str) -> Path:
    _RESULTS_DIR.mkdir(exist_ok=True)
    out_path = _RESULTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{run_id[:8]}.json"
    payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": agg.model_dump(),
        "per_pr": [r.model_dump() for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reviewer evals over data/prs/")
    parser.add_argument(
        "--pr-dir",
        type=Path,
        default=None,
        help="Score only this PR directory (default: every PR under data/prs/).",
    )
    parser.add_argument(
        "--line-tolerance",
        type=int,
        default=0,
        help="Accept matches off by N lines (default 0 = exact).",
    )
    args = parser.parse_args()

    console = Console()
    run_id = uuid.uuid4().hex[:12]
    run_logger = RunLogger(run_id)

    pr_dirs = [args.pr_dir] if args.pr_dir else _discover_prs(_PRS_ROOT)
    if not pr_dirs:
        console.print(f"[red]No PRs found under {_PRS_ROOT}[/red]")
        return 1

    console.print(f"[dim]run_id={run_id} — scoring {len(pr_dirs)} PR(s)[/dim]\n")

    results: list[PREvalResult] = []
    t0 = time.monotonic()

    for pr_dir in pr_dirs:
        try:
            gt = _load_ground_truth(pr_dir)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]skip {pr_dir.name}:[/red] {e}")
            continue

        try:
            emitted = _run_pipeline_for(pr_dir, run_logger)
        except Exception as e:
            console.print(f"[red]pipeline error on {pr_dir.name}:[/red] "
                          f"{type(e).__name__}: {e}")
            continue

        result = score_pr(gt.pr_id, emitted, gt, line_tolerance=args.line_tolerance)
        results.append(result)
        _render_pr_row(console, result)

    elapsed = time.monotonic() - t0
    console.print(f"\n[dim]Scored {len(results)} PR(s) in {elapsed:.1f}s[/dim]\n")

    if not results:
        return 1

    agg = aggregate(results)
    _render_aggregate(console, agg)

    snapshot_path = _snapshot(results, agg, run_id)
    console.print(f"\n[dim]Snapshot: {snapshot_path.relative_to(Path.cwd())}[/dim]")

    # Exit code: 0 if recall + precision both ≥ 0.8, else 1 (CI-friendly)
    threshold_ok = agg.recall >= 0.8 and agg.precision >= 0.8
    return 0 if threshold_ok else 1


if __name__ == "__main__":
    sys.exit(main())
