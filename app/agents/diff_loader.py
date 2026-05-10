"""
app/agents/diff_loader.py — Slice 4

Reads pr.diff from a PR directory via a local filesystem MCP server
(npx @modelcontextprotocol/server-filesystem).

Satisfies homework rubric requirement #3: MCP server integration.

The MCP server is scoped to pr_dir so the agent can only read files
inside that directory (least-privilege).
"""
import logging
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.tools.mcp import MCPClient

from app.provider import build_model

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a file reader. When asked to read a file, use the available "
    "MCP filesystem tools to read it. Return the raw file content VERBATIM. "
    "No prose, no explanation, no markdown fences, no prefix. "
    "Output ONLY the file content, character for character."
)


def load_diff(pr_dir: Path, hooks: list[Any] | None = None) -> str:
    """
    Read pr.diff from pr_dir via MCP filesystem server.

    Returns raw unified diff text ready for parse_unified_diff().
    """
    pr_dir = pr_dir.resolve()

    # MCPClient must NOT be pre-started; Agent starts it lazily.
    mcp = MCPClient(lambda: stdio_client(StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(pr_dir)],
    )))

    agent = Agent(
        name="diff-loader",
        model=build_model(max_tokens=2048),
        system_prompt=_SYSTEM_PROMPT,
        tools=[mcp],
        hooks=hooks or [],
        callback_handler=None,
    )

    result = agent(
        "Read the file 'pr.diff' using the MCP filesystem tools "
        "and return its contents verbatim."
    )
    raw = str(result)

    # Strip any prose the model prepended before the first diff header line.
    lines = raw.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("diff --git")), None)
    if start is None:
        logger.warning("diff-loader: no 'diff --git' header found — returning raw output")
        return raw
    return "\n".join(lines[start:])
