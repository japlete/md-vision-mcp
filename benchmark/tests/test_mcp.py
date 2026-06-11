"""Tests for benchmark MCP tool wiring."""

from __future__ import annotations

import asyncio
import unittest

from langchain_core.tools import StructuredTool, ToolException

from harness.mcp import prepare_mcp_tools


async def _raise_tool_exception() -> str:
    raise ToolException("index_md failed: Path is not allowed: /doc/index.md")


class PrepareMcpToolsTests(unittest.TestCase):
    def test_prepare_mcp_tools_enables_handle_tool_error(self) -> None:
        tool = StructuredTool.from_function(
            coroutine=_raise_tool_exception,
            name="index_md",
            description="test",
        )

        prepared = prepare_mcp_tools([tool])[0]

        self.assertTrue(prepared.handle_tool_error)

    def test_prepare_mcp_tools_returns_error_as_tool_output(self) -> None:
        tool = StructuredTool.from_function(
            coroutine=_raise_tool_exception,
            name="index_md",
            description="test",
        )
        prepared = prepare_mcp_tools([tool])[0]

        result = asyncio.run(prepared.ainvoke({}))

        self.assertEqual(result, "index_md failed: Path is not allowed: /doc/index.md")


if __name__ == "__main__":
    unittest.main()
