"""LangChain MCP adapter for the local md-vision server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient


def mdvision_connection(corpus_dir: Path, server_path: Path) -> dict[str, Any]:
    corpus_dir = corpus_dir.resolve()
    return {
        "md-vision": {
            "transport": "stdio",
            "command": "node",
            "args": [
                str(server_path),
                "--allow-path",
                str(corpus_dir),
                "--allow-domain",
                "none",
            ],
            "cwd": str(corpus_dir),
        }
    }


def prepare_mcp_tools(tools: list[Any]) -> list[Any]:
    """Return MCP tools that surface server errors as normal tool output.

    langchain-mcp-adapters raises ToolException when the MCP server sets
    isError=true. Enable handle_tool_error so the agent can read the message
    and retry with corrected arguments instead of aborting the run.
    """
    for tool in tools:
        tool.handle_tool_error = True
    return tools


async def load_mdvision_tools(corpus_dir: Path, server_path: Path) -> list[Any]:
    if not server_path.exists():
        raise FileNotFoundError(
            f"{server_path} does not exist. Run `npm run build` from the repo root first."
        )

    client = MultiServerMCPClient(mdvision_connection(corpus_dir, server_path))
    tools = await client.get_tools()
    return prepare_mcp_tools(tools)
