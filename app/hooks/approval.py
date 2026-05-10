"""
app/hooks/approval.py — Slice 4

ApprovalHook HookProvider: HITL gate on the report-writer graph node.

Protocol (two-call pattern):
  First call:  BeforeNodeCallEvent fires → event.interrupt() raises InterruptException
               → graph returns status=INTERRUPTED with interrupt carrying findings.
  Second call: BeforeNodeCallEvent fires → event.interrupt() returns user's response.
               hook stores accepted/rejected in invocation_state.
               BeforeInvocationEvent fires → hook overrides agent messages so the
               report-writer only sees the approved findings.

Satisfies homework rubric requirement #7 (Interrupt / HITL).
"""
import logging
from typing import Any

from rich.console import Console
from strands.hooks import BeforeInvocationEvent, BeforeNodeCallEvent, HookProvider
from strands.hooks.registry import HookRegistry

from app.models import Finding

logger = logging.getLogger(__name__)

_INTERRUPT_NAME = "review-approval"


class ApprovalHook(HookProvider):
    """Interrupt gate: pauses before report-writer, resumes with user's accept/reject decisions."""

    def __init__(self, console: Console) -> None:
        self._console = console

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeNodeCallEvent, self._on_before_node)
        registry.add_callback(BeforeInvocationEvent, self._on_before_invocation)

    # ------------------------------------------------------------------
    # Graph-level: fires once per graph invocation of the report-writer node
    # ------------------------------------------------------------------

    def _on_before_node(self, event: BeforeNodeCallEvent) -> None:
        if event.node_id != "report-writer":
            return

        findings_data: list[dict] = (event.invocation_state or {}).get("findings_json", [])
        findings = [Finding(**f) for f in findings_data]

        # First call: raises InterruptException → graph returns status=INTERRUPTED
        # Second call (resume): returns the user's response dict
        response: dict[str, Any] = event.interrupt(
            _INTERRUPT_NAME,
            reason={"findings": [f.model_dump() for f in findings]},
        )

        # ---- Resumed: store decisions in invocation_state for BeforeInvocationEvent ----
        accepted_data: list[dict] = response.get("accepted", [f.model_dump() for f in findings])
        rejected_data: list[dict] = response.get("rejected", [])

        inv = event.invocation_state or {}
        inv["accepted_findings"] = accepted_data
        inv["rejected_findings"] = rejected_data
        logger.debug(
            "accepted=%d rejected=%d | HITL decisions stored",
            len(accepted_data), len(rejected_data),
        )

    # ------------------------------------------------------------------
    # Agent-level: fires when the report-writer Agent's event loop begins
    # ------------------------------------------------------------------

    def _on_before_invocation(self, event: BeforeInvocationEvent) -> None:
        """On resume, replace the agent's task with only the accepted findings."""
        inv: dict[str, Any] = getattr(event, "invocation_state", {}) or {}
        accepted_data = inv.get("accepted_findings")
        if accepted_data is None:
            return  # Guard: not resumed yet — interrupt will fire first

        findings = [Finding(**f) for f in accepted_data]
        task_text = _format_accepted(findings)
        # messages is writeable on BeforeInvocationEvent
        event.messages = [{"role": "user", "content": [{"text": task_text}]}]
        logger.debug("report-writer messages replaced with %d accepted finding(s)", len(findings))


# ------------------------------------------------------------------
# Helper: format accepted findings for the report-writer's task
# ------------------------------------------------------------------

def _format_accepted(findings: list[Finding]) -> str:
    if not findings:
        return "No findings were approved. Emit exactly: No issues found."

    lines: list[str] = [
        f"Format the following {len(findings)} approved finding(s) into a markdown PR review report.",
        "Activate the swift-review-rubric skill first to load the formatting instructions.",
        "",
    ]
    for f in findings:
        lines += [
            f"FINDING [{f.severity.upper()}] {f.category} — {f.file_path}:{f.line}",
            f"  Title: {f.title}",
            f"  Body: {f.body}",
            f"  Action: {f.suggested_action}",
            "",
        ]
    return "\n".join(lines)
