"""
app/hooks/instrumentation.py — Slice 4

RunLogger HookProvider: writes one JSONL line per agent invocation to
runs/<run_id>.jsonl.  Captures: agent name, latency, input/output tokens.

Satisfies homework rubric requirement #6 (Hook).
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strands.hooks import AfterInvocationEvent, BeforeInvocationEvent, HookProvider
from strands.hooks.registry import HookRegistry

logger = logging.getLogger(__name__)

_RUNS_DIR = Path(__file__).parent.parent.parent / "runs"


class RunLogger(HookProvider):
    """Writes one JSONL line per agent invocation to runs/<run_id>.jsonl."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        _RUNS_DIR.mkdir(exist_ok=True)
        self._log_path = _RUNS_DIR / f"{run_id}.jsonl"
        # Keyed by agent name; supports parallel agents without collision
        # because each agent name is unique in our topology.
        self._start_times: dict[str, float] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self._on_before)
        registry.add_callback(AfterInvocationEvent, self._on_after)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_before(self, event: BeforeInvocationEvent) -> None:
        agent_name = getattr(event.agent, "name", "unknown")
        self._start_times[agent_name] = time.monotonic()

    def _on_after(self, event: AfterInvocationEvent) -> None:
        agent_name = getattr(event.agent, "name", "unknown")
        start = self._start_times.pop(agent_name, time.monotonic())
        latency_ms = round((time.monotonic() - start) * 1000)

        input_tokens = output_tokens = 0
        if event.result is not None:
            usage = getattr(event.result.metrics, "accumulated_usage", None)
            if isinstance(usage, dict):
                input_tokens = usage.get("inputTokens", 0) or 0
                output_tokens = usage.get("outputTokens", 0) or 0

        record: dict[str, Any] = {
            "event": "invocation",
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "agent": agent_name,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

        with self._log_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

        logger.debug(
            "agent=<%s> latency_ms=<%d> in=%d out=%d | logged",
            agent_name, latency_ms, input_tokens, output_tokens,
        )
