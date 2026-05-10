"""
app/graph.py — Slice 3

GraphBuilder topology: four reviewer agents as parallel entry-point nodes.
Nodes without incoming edges are auto-detected as entry points by the Graph
framework and executed concurrently.

The aggregator stays as plain Python for Slice 3; it becomes an Agent node
in Slice 4 when the skill and hooks land.
"""
import logging
from pathlib import Path

from strands import Agent
from strands.multiagent import GraphBuilder

from app.models import Hunk, ReviewerOutput
from app.provider import build_model


logger = logging.getLogger(__name__)

_STEERING_DIR = Path(__file__).parent / "agents" / "_steering"

# (node_id, steering_file, agent_name) — insertion order preserved for result extraction
_REVIEWER_CONFIGS: list[tuple[str, str, str]] = [
    ("correctness", "correctness.md", "correctness-reviewer"),
    ("style",       "style.md",       "style-reviewer"),
    ("api_design",  "api_design.md",  "api-design-reviewer"),
    ("test_coverage", "test_coverage.md", "test-coverage-reviewer"),
]


def _format_hunks(hunks: list[Hunk]) -> str:
    blocks: list[str] = []
    for h in hunks:
        numbered = "\n".join(f"  {al.line_no}: {al.text}" for al in h.added_lines)
        blocks.append(f"--- {h.file_path} ---\n{h.context_header}\n{numbered}")
    return "\n\n".join(blocks)


def run_reviewers(hunks: list[Hunk]) -> list[ReviewerOutput]:
    """
    Run all four reviewer agents in parallel via a Strands Graph.

    Each node receives the same formatted diff task. Node system_prompts
    constrain each agent to its domain (correctness / style / api_design /
    test_coverage). Nodes with no incoming edges are auto-detected as entry
    points and run concurrently.

    Returns one ReviewerOutput per reviewer that succeeded. Failed nodes are
    skipped (fail-soft); the caller aggregates and renders.
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
        # One execution per reviewer node; no cycles exist in this topology.
        .set_max_node_executions(len(_REVIEWER_CONFIGS))
    )

    for node_id, steering_file, agent_name in _REVIEWER_CONFIGS:
        system_prompt = (_STEERING_DIR / steering_file).read_text()
        agent = Agent(
            name=agent_name,
            model=build_model(max_tokens=2048),
            system_prompt=system_prompt,
            structured_output_model=ReviewerOutput,
            callback_handler=None,
        )
        builder.add_node(agent, node_id=node_id)
        # No set_entry_point calls needed: nodes without dependencies are
        # auto-detected as entry points and scheduled in the same parallel batch.

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
