"""
app/agents/report_writer.py — Slice 4

Report-writer Agent: activates the swift-review-rubric skill, uses current_time
as a community tool, and formats the approved findings into a markdown report.

Satisfies homework rubric items:
  #2 — community tool: current_time from strands_tools
  #4 — skill: swift-review-rubric via AgentSkills plugin
"""
from pathlib import Path
from typing import Any

from strands import Agent, AgentSkills
from strands_tools import current_time

from app.provider import build_model

_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"
_STEERING_PATH = Path(__file__).parent / "_steering" / "report_writer.md"


def build_agent(hooks: list[Any] | None = None) -> Agent:
    """
    Build a fresh report-writer Agent.

    The AgentSkills plugin gives the agent access to the swift-review-rubric
    skill via the `skills` tool. The agent is instructed to activate it before
    writing the report.

    Args:
        hooks: Optional list of HookProvider instances (RunLogger, ApprovalHook).
    """
    skills_plugin = AgentSkills(skills=[str(_SKILLS_DIR)])

    return Agent(
        name="report-writer",
        model=build_model(max_tokens=4096),
        system_prompt=_STEERING_PATH.read_text(),
        tools=[current_time],
        plugins=[skills_plugin],
        hooks=hooks or [],
        callback_handler=None,
    )
