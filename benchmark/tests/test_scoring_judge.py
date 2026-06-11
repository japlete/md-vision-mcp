"""Tests for semantic judge fallback scoring."""

from __future__ import annotations

import unittest
from typing import Any

from harness.judge import SemanticJudge, resolve_score, should_use_judge
from harness.scoring import eval_score


class FakeJudge(SemanticJudge):
    def __init__(self, *, equivalent: bool, threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.equivalent = equivalent
        self.calls: list[dict[str, Any]] = []

    async def is_equivalent(self, **kwargs: Any) -> bool:
        self.calls.append(kwargs)
        return self.equivalent


class JudgeFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_match_skips_judge(self) -> None:
        gt = "Less well-off"
        pred = "Less well-off"
        judge = FakeJudge(equivalent=True)

        result = await resolve_score(
            gt=gt,
            pred=pred,
            answer_type="Str",
            question="Which subgroup?",
            judge=judge,
        )

        self.assertEqual(result["score_anls"], 1.0)
        self.assertEqual(result["score"], 1.0)
        self.assertFalse(result["judge_used"])
        self.assertEqual(judge.calls, [])

    async def test_low_anls_upgrades_when_judge_agrees(self) -> None:
        gt = (
            "Elements of objects tend to be perceptually grouped together if they form "
            "a pattern that is regular, simple, and orderly."
        )
        pred = (
            "Elements tend to be grouped perceptually if they form regular, simple, "
            "orderly patterns."
        )
        self.assertEqual(eval_score(gt, pred, "Str"), 0.0)

        judge = FakeJudge(equivalent=True)
        result = await resolve_score(
            gt=gt,
            pred=pred,
            answer_type="Str",
            question="How does this document define the law of good gestalt?",
            judge=judge,
        )

        self.assertEqual(result["score_anls"], 0.0)
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["judge_used"])
        self.assertTrue(result["judge_equivalent"])
        self.assertEqual(len(judge.calls), 1)

    async def test_low_anls_keeps_score_when_judge_rejects(self) -> None:
        gt = "Less well-off"
        pred = "Better off"
        judge = FakeJudge(equivalent=False)

        result = await resolve_score(
            gt=gt,
            pred=pred,
            answer_type="Str",
            question="Which subgroup?",
            judge=judge,
        )

        self.assertLess(result["score_anls"], 1.0)
        self.assertEqual(result["score"], result["score_anls"])
        self.assertTrue(result["judge_used"])
        self.assertFalse(result["judge_equivalent"])

    async def test_int_answer_skips_judge(self) -> None:
        judge = FakeJudge(equivalent=True)
        result = await resolve_score(
            gt="42",
            pred="41",
            answer_type="Int",
            question="How many?",
            judge=judge,
        )

        self.assertEqual(result["score"], 0.0)
        self.assertFalse(result["judge_used"])
        self.assertEqual(judge.calls, [])


class ShouldUseJudgeTests(unittest.TestCase):
    def test_not_answerable_skips(self) -> None:
        self.assertFalse(
            should_use_judge(
                anls_score=0.0,
                answer_type="Str",
                gt="Not answerable",
                pred="Not answerable",
                threshold=1.0,
            )
        )

    def test_fail_to_answer_skips(self) -> None:
        self.assertFalse(
            should_use_judge(
                anls_score=0.0,
                answer_type="Str",
                gt="Berlin School of Experimental Psychology",
                pred="Fail to answer",
                threshold=1.0,
            )
        )

    def test_list_prediction_can_use_judge(self) -> None:
        self.assertTrue(
            should_use_judge(
                anls_score=0.0,
                answer_type="List",
                gt=["foo", "bar"],
                pred=["foo", "baz"],
                threshold=1.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
