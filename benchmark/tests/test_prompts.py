"""Tests for benchmark harness prompts."""

from __future__ import annotations

import unittest

from harness.prompts import system_prompt


class SystemPromptTests(unittest.TestCase):
    def test_baseline_system_prompt_mentions_virtual_filesystem_paths(self) -> None:
        prompt = system_prompt(arm="baseline")

        self.assertIn("virtual", prompt)
        self.assertIn("read_file", prompt)
        self.assertNotIn("index_md", prompt)

    def test_mdvision_system_prompt_mentions_markdown_tool_paths(self) -> None:
        prompt = system_prompt(arm="mdvision")

        self.assertIn("index_md", prompt)
        self.assertIn("without a leading `/`", prompt)
        self.assertIn("try again", prompt)


if __name__ == "__main__":
    unittest.main()
