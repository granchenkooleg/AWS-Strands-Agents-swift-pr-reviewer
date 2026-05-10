"""
Style Reviewer agent.

Returns a Pydantic ReviewerOutput via Strands' built-in `structured_output_model`
— no hand-rolled JSON parsing. Strands re-prompts on validation failure.
"""
from pathlib import Path

from strands import Agent

from app.models import Hunk, ReviewerOutput
from app.provider import build_model


_STEERING_PATH = Path(__file__).parent / "_steering" / "style.md"


def _load_system_prompt() -> str:
    return _STEERING_PATH.read_text()


def _format_hunks_for_prompt(hunks: list[Hunk]) -> str:
    """Render hunks as a flat block the LLM can read line-by-line."""
    blocks: list[str] = []
    for h in hunks:
        numbered = "\n".join(
            f"  {al.line_no}: {al.text}" for al in h.added_lines
        )
        blocks.append(
            f"--- {h.file_path} ---\n"
            f"{h.context_header}\n"
            f"{numbered}"
        )
    return "\n\n".join(blocks)


def review(hunks: list[Hunk]) -> ReviewerOutput:
    """
    Run the style reviewer over a list of changed hunks.

    Returns a validated ReviewerOutput. On model error or persistent
    validation failure, propagates the exception — caller decides whether
    to degrade gracefully (the graph-level fail-soft policy).
    """
    if not hunks:
        return ReviewerOutput(findings=[], confidence_note="empty diff")

    agent = Agent(
        name="style-reviewer",
        model=build_model(max_tokens=2048),
        system_prompt=_load_system_prompt(),
        structured_output_model=ReviewerOutput,
        callback_handler=None,
    )

    prompt = (
        "Review the following Swift diff hunks for style issues only. "
        "Cite post-change line numbers exactly as shown.\n\n"
        f"{_format_hunks_for_prompt(hunks)}"
    )

    result = agent(prompt)
    output = result.structured_output
    if not isinstance(output, ReviewerOutput):
        raise TypeError(
            f"Expected ReviewerOutput, got {type(output).__name__}: {output!r}"
        )
    return output
