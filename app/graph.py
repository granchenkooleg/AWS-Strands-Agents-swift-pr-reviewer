"""
app/graph.py — Slice 4

Two graph topologies:

1. run_reviewers() — four reviewer agents as parallel entry-point nodes (Slice 3).
   Accepts optional agent-level hooks (RunLogger) for per-invocation logging.

2. build_report_writer_graph() — single report-writer node with HITL interrupt
   (Slice 4). Graph-level hooks fire BeforeNodeCallEvent (ApprovalHook).
   Agent-level hooks fire BeforeInvocationEvent (ApprovalHook + RunLogger).
"""
import logging
from pathlib import Path
from typing import Any

from strands import Agent
from strands.hooks import HookProvider
from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph

from app.agents import report_writer as report_writer_module
from app.models import Hunk, ReviewerOutput
from app.provider import build_model


logger = logging.getLogger(__name__)

_STEERING_DIR = Path(__file__).parent / "agents" / "_steering"

# (node_id, steering_file, agent_name) — insertion order preserved for result extraction
_REVIEWER_CONFIGS: list[tuple[str, str, str]] = [
    ("correctness",   "correctness.md",   "correctness-reviewer"),
    ("style",         "style.md",         "style-reviewer"),
    ("api_design",    "api_design.md",    "api-design-reviewer"),
    ("test_coverage", "test_coverage.md", "test-coverage-reviewer"),
]


def _format_hunks(hunks: list[Hunk]) -> str:
    """
    Render hunks for the reviewer prompt.

    Each hunk shows TWO views:
      1. RAW DIFF — full unified-diff text with '+', '-', and context lines.
         Use this to detect *changes* (e.g. return type narrowed, parameter
         removed). The api_design reviewer in particular needs to compare
         '-' against '+' to spot source-breaking changes.
      2. ADDED LINES — numbered list of '+' lines only. Use these line
         numbers when citing findings; they are the authoritative post-change
         line numbers.
    """
    blocks: list[str] = []
    for h in hunks:
        numbered = "\n".join(f"  {al.line_no}: {al.text}" for al in h.added_lines)
        blocks.append(
            f"--- {h.file_path} ---\n"
            f"RAW DIFF (read this to detect changes):\n"
            f"{h.raw_hunk}\n\n"
            f"ADDED LINES (cite these line numbers in findings):\n"
            f"{numbered}"
        )
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Reviewer graph
# ---------------------------------------------------------------------------

def run_reviewers(
    hunks: list[Hunk],
    agent_hooks: list[HookProvider] | None = None,
) -> list[ReviewerOutput]:
    """
    Run all four reviewer agents in parallel via a Strands Graph.

    Args:
        hunks: Parsed diff hunks.
        agent_hooks: Hooks registered on each reviewer Agent (e.g. RunLogger).

    Returns one ReviewerOutput per reviewer that succeeded; failed nodes skipped.
    """
    if not hunks:
        return []

    task = (
        "Review the following Swift diff hunks according to your assigned role. "
        "Cite post-change line numbers exactly as shown.\n\n"
        f"{_format_hunks(hunks)}"
    )

    builder = (
        GraphBuilder()
        .set_graph_id("swift-pr-reviewer")
        .set_max_node_executions(len(_REVIEWER_CONFIGS))
    )

    for node_id, steering_file, agent_name in _REVIEWER_CONFIGS:
        system_prompt = (_STEERING_DIR / steering_file).read_text()
        agent = Agent(
            name=agent_name,
            model=build_model(max_tokens=2048),
            system_prompt=system_prompt,
            structured_output_model=ReviewerOutput,
            hooks=agent_hooks or [],
            callback_handler=None,
        )
        builder.add_node(agent, node_id=node_id)

    graph = builder.build()
    graph_result = graph(task)

    outputs: list[ReviewerOutput] = []
    for node_id, _, _ in _REVIEWER_CONFIGS:
        node_result = graph_result.results.get(node_id)
        if node_result is None:
            logger.warning("node_id=%s result missing from graph output", node_id)
            continue
        if isinstance(node_result.result, Exception):
            logger.warning(
                "node_id=%s failed: %s: %s",
                node_id, type(node_result.result).__name__, node_result.result,
            )
            continue
        structured = node_result.result.structured_output
        if isinstance(structured, ReviewerOutput):
            outputs.append(structured)
        else:
            logger.warning("node_id=%s produced no structured output", node_id)

    return outputs


# ---------------------------------------------------------------------------
# Report-writer graph (HITL)
# ---------------------------------------------------------------------------

def build_report_writer_graph(
    agent_hooks: list[HookProvider] | None = None,
    graph_hooks: list[HookProvider] | None = None,
) -> Graph:
    """
    Build a single-node graph containing the report-writer Agent.

    Graph-level hooks (graph_hooks) receive BeforeNodeCallEvent — this is where
    ApprovalHook raises the interrupt for the HITL gate.

    Agent-level hooks (agent_hooks) receive BeforeInvocationEvent — ApprovalHook
    uses this to replace the agent's task with only the accepted findings on resume.

    The graph uses execution_timeout instead of max_node_executions because the
    report-writer node executes twice (interrupted first call + resumed second call).
    """
    rw_agent = report_writer_module.build_agent(hooks=agent_hooks)

    builder = (
        GraphBuilder()
        .set_graph_id("swift-pr-reviewer-report")
        .set_execution_timeout(300)  # 5 min; also suppresses the no-limits warning
    )
    builder.add_node(rw_agent, node_id="report-writer")

    if graph_hooks:
        builder.set_hook_providers(graph_hooks)

    return builder.build()
