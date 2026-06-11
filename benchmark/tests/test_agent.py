"""Tests for benchmark agent model construction."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from harness.agent import build_model


class BuildModelTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    @patch("harness.agent.ChatOpenAI")
    def test_openrouter_extra_body_includes_service_tier_and_reasoning(self, mock_chat: object) -> None:
        build_model(
            {
                "model": "google/gemini-3.5-flash",
                "provider": "openrouter",
                "service_tier": "flex",
                "reasoning_effort": "minimal",
            }
        )

        kwargs = mock_chat.call_args.kwargs
        self.assertEqual(
            kwargs["extra_body"],
            {
                "service_tier": "flex",
                "reasoning": {"effort": "minimal"},
            },
        )

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    @patch("harness.agent.ChatOpenAI")
    def test_openrouter_omits_extra_body_when_unset(self, mock_chat: object) -> None:
        build_model(
            {
                "model": "google/gemini-3.5-flash",
                "provider": "openrouter",
            }
        )

        self.assertNotIn("extra_body", mock_chat.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
