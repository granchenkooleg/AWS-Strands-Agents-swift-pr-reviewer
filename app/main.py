"""
CLI entry point — slice 4.

    python -m app.main --pr data/prs/001_force_unwrap

Slice 4 adds:
  - MCP-based diff loader (npx @modelcontextprotocol/server-filesystem)
  - RunLogger hook writing per-agent JSONL to runs/<run_id>.jsonl
  - Report-writer Agent with swift-review-rubric skill + current_time tool
  - HITL interrupt on the report-writer graph node (BeforeNodeCallEvent)
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.agents import aggregator
from app.agents import diff_loader as diff_loader_module
from app.graph import build_report_writer_graph, run_reviewers
from app.hooks.approval import ApprovalHook
from app.hooks.instrumentation import RunLogger
from app.models import Finding
from app.observability.tracing import setup_tracing
from app.tools.parse_diff import parse_unified_diff


SEVERITY_COLOR = {
    "blocker": "bold red",
    "major":   "red1",
    "minor":   "yellow",
    "nit":     "dim white",
}


# ---------------------------------------------------------------------------
# PR loading — falls back to direct filesystem read if MCP/model fails
# ---------------------------------------------------------------------------

def _load_pr(pr_dir: Path, run_logger: RunLogger) -> tuple[str, dict]:
    """Read pr.diff (via MCP agent) and metadata.json (direct read)."""
    meta_path = pr_dir / "metadata.json"
    if not meta_path.exists():
        sys.exit(f"error: {pr_dir}/metadata.json not found")
    metadata = json.loads(meta_path.read_text())

    try:
        diff_text = diff_loader_module.load_diff(pr_dir, hooks=[run_logger])
    except Exception as e:
        # Fail-soft: fall back to direct read so the rest of the pipeline can run
        console_fallback = Console()
        console_fallback.print(
            f"[yellow]diff-loader MCP agent failed ({type(e).__name__}: {e}), "
            f"falling back to direct read.[/yellow]"
        )
        diff_path = pr_dir / "pr.diff"
        if not diff_path.exists():
            sys.exit(f"error: {pr_dir}/pr.diff not found")
        diff_text = diff_path.read_text()

    return diff_text, metadata


# ---------------------------------------------------------------------------
# HITL prompt
# ---------------------------------------------------------------------------

def _prompt_hitl(console: Console, findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """
    Prompt the user to accept or reject each finding.

    Returns (accepted, rejected).
    """
    console.print("\n[bold cyan]── HITL Review Gate ──────────────────────────────────[/bold cyan]")
    console.print("[dim]For each finding, press Enter to accept or type 'n' to reject.[/dim]\n")

    accepted: list[Finding] = []
    rejected: list[Finding] = []

    for i, f in enumerate(findings, 1):
        color = SEVERITY_COLOR.get(f.severity, "white")
        console.print(
            f"[{i}/{len(findings)}] [{color}]{f.severity}[/{color}] "
            f"[bold]{f.category}[/bold]  {f.file_path}:{f.line}"
        )
        console.print(f"  [italic]{f.title}[/italic]")

        try:
            answer = input("  Accept? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Non-interactive mode: accept all
            answer = ""

        if answer in ("n", "no"):
            rejected.append(f)
            console.print("  [dim]→ rejected[/dim]")
        else:
            accepted.append(f)
            console.print("  [dim]→ accepted[/dim]")

    console.print()
    return accepted, rejected


# ---------------------------------------------------------------------------
# Findings table
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Swift PR reviewer over a synthetic PR (slice 4)."
    )
    parser.add_argument(
        "--pr",
        required=True,
        type=Path,
        help="Path to a data/prs/<pr_id>/ directory.",
    )
    parser.add_argument(
        "--no-hitl",
        action="store_true",
        help="Skip the HITL approval gate and accept all findings.",
    )
    args = parser.parse_args()

    console = Console()
    run_id = uuid.uuid4().hex[:12]
    run_logger = RunLogger(run_id)

    if setup_tracing():
        console.print("[dim]OTel tracing → ADOT/CloudWatch enabled.[/dim]")

    console.print(f"[dim]run_id={run_id}[/dim]")

    # ------------------------------------------------------------------
    # 1. Load PR diff via MCP agent
    # ------------------------------------------------------------------
    console.print("[dim]Loading PR diff via MCP filesystem agent…[/dim]")
    diff_text, metadata = _load_pr(args.pr, run_logger)
    pr_id = metadata.get("pr_id", args.pr.name)

    hunks = parse_unified_diff(diff_text)
    if not hunks:
        console.print("[yellow]No changed lines parsed from diff. Nothing to review.[/yellow]")
        return 0

    console.print(f"[dim]Parsed {len(hunks)} hunk(s) across "
                  f"{len({h.file_path for h in hunks})} file(s). "
                  f"Running four reviewers in parallel via Graph…[/dim]")

    # ------------------------------------------------------------------
    # 2. Run reviewer graph (parallel fan-out)
    # ------------------------------------------------------------------
    try:
        outputs = run_reviewers(hunks, agent_hooks=[run_logger])
    except Exception as e:
        console.print(f"[red]Reviewer graph failed:[/red] {type(e).__name__}: {e}")
        return 1

    console.print(f"[dim]{len(outputs)}/4 reviewer(s) returned findings.[/dim]")

    # ------------------------------------------------------------------
    # 3. Aggregate (plain Python dedup + sort)
    # ------------------------------------------------------------------
    findings = aggregator.aggregate(outputs)
    _render(console, pr_id, findings)

    if not findings:
        return 0

    # ------------------------------------------------------------------
    # 4. HITL gate + report-writer graph
    # ------------------------------------------------------------------
    approval_hook = ApprovalHook(console)
    rw_graph = build_report_writer_graph(
        agent_hooks=[approval_hook, run_logger],
        graph_hooks=[approval_hook],
    )

    inv_state: dict = {"findings_json": [f.model_dump() for f in findings]}

    console.print("[dim]Running report-writer graph (HITL gate will fire)…[/dim]")
    try:
        rw_result = rw_graph("Generate the markdown PR review report.", invocation_state=inv_state)
    except Exception as e:
        console.print(f"[red]Report-writer graph failed:[/red] {type(e).__name__}: {e}")
        return 1

    # ------------------------------------------------------------------
    # 5. Handle HITL interrupt
    # ------------------------------------------------------------------
    from strands.multiagent.graph import Status  # local import avoids circular

    if rw_result.status == Status.INTERRUPTED and rw_result.interrupts:
        interrupt = rw_result.interrupts[0]
        interrupt_findings = [
            Finding(**f) for f in interrupt.reason.get("findings", [])
        ]

        if args.no_hitl:
            accepted, rejected = interrupt_findings, []
            console.print(f"[dim]--no-hitl: accepting all {len(accepted)} findings.[/dim]")
        else:
            accepted, rejected = _prompt_hitl(console, interrupt_findings)

        console.print(
            f"[dim]HITL: {len(accepted)} accepted, {len(rejected)} rejected. "
            f"Resuming report-writer…[/dim]"
        )

        resume_input = [{"interruptResponse": {
            "interruptId": interrupt.id,
            "response": {
                "accepted": [f.model_dump() for f in accepted],
                "rejected": [f.model_dump() for f in rejected],
            },
        }}]

        try:
            rw_result = rw_graph(resume_input, invocation_state=inv_state)
        except Exception as e:
            console.print(f"[red]Report-writer resume failed:[/red] {type(e).__name__}: {e}")
            return 1

    # ------------------------------------------------------------------
    # 6. Display markdown report
    # ------------------------------------------------------------------
    rw_node = rw_result.results.get("report-writer")
    if rw_node and not isinstance(rw_node.result, Exception):
        markdown = str(rw_node.result)
        console.print(Panel(
            markdown,
            title="[bold]Markdown Report[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))
    else:
        console.print("[yellow]Report-writer produced no output.[/yellow]")

    console.print(f"\n[dim]JSONL log: runs/{run_id}.jsonl[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
