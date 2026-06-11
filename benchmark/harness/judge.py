"""LLM-as-judge fallback for low-confidence ANLS string matches."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from .scoring import FAIL_TO_ANSWER, NOT_ANSWERABLE, eval_score


JUDGE_ANSWER_TYPES = frozenset({"Str", "None", "List"})

JUDGE_SYSTEM_PROMPT = """You judge whether a predicted answer is semantically equivalent to a reference answer for a document QA benchmark.

Rules:
- equivalent=true when the prediction conveys the same factual content as the reference, allowing rephrasing, word order changes, abbreviations, and minor formatting differences.
- equivalent=false when the prediction is wrong, materially incomplete, adds conflicting facts, or mismatches answerability (reference is answerable but prediction is not, or vice versa).
- For list answers, the same items in any order count as equivalent; minor singular/plural or casing differences are fine when meaning is preserved.
- Ignore differences that do not change the answer's meaning."""

JUDGE_USER_TEMPLATE = """Question:
{question}

Reference answer:
{reference}

Predicted answer:
{prediction}

Answer format: {answer_format}"""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equivalent: bool = Field(description="True when the predicted answer is a semantic match for the reference.")


class SemanticJudge:
    def __init__(self, config: dict[str, Any]) -> None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required when the semantic judge is enabled.")

        extra_body: dict[str, Any] = {}
        service_tier = config.get("service_tier")
        if service_tier:
            extra_body["service_tier"] = service_tier

        reasoning_effort = config.get("reasoning_effort")
        if reasoning_effort:
            extra_body["reasoning"] = {"effort": reasoning_effort}

        model = ChatOpenAI(
            model=str(config["model"]),
            api_key=api_key,
            base_url=config.get("openrouter_base_url", "https://openrouter.ai/api/v1"),
            temperature=0,
            default_headers={
                "HTTP-Referer": "https://github.com/japlete/md-vision-mcp",
                "X-Title": "md-vision benchmark judge",
            },
            **({"extra_body": extra_body} if extra_body else {}),
        )
        self._model = model.with_structured_output(JudgeVerdict)
        self.threshold = float(config.get("threshold", 1.0))

    async def is_equivalent(
        self,
        *,
        question: str,
        reference: Any,
        prediction: Any,
        answer_format: str,
    ) -> bool:
        prompt = JUDGE_USER_TEMPLATE.format(
            question=question.strip(),
            reference=format_answer_for_judge(reference),
            prediction=format_answer_for_judge(prediction),
            answer_format=answer_format,
        )
        verdict = await self._model.ainvoke(
            [
                SystemMessage(content=JUDGE_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        if isinstance(verdict, JudgeVerdict):
            return verdict.equivalent
        if isinstance(verdict, dict):
            return bool(verdict.get("equivalent"))
        return bool(getattr(verdict, "equivalent", False))


def format_answer_for_judge(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def should_use_judge(
    *,
    anls_score: float,
    answer_type: str,
    gt: Any,
    pred: Any,
    threshold: float,
) -> bool:
    if anls_score >= threshold:
        return False
    if answer_type not in JUDGE_ANSWER_TYPES:
        return False
    if gt == NOT_ANSWERABLE:
        return False
    if pred == NOT_ANSWERABLE or pred == FAIL_TO_ANSWER:
        return False
    return True


async def resolve_score(
    *,
    gt: Any,
    pred: Any,
    answer_type: str,
    question: str,
    judge: SemanticJudge | None,
) -> dict[str, Any]:
    anls_score = eval_score(gt, pred, answer_type)
    result: dict[str, Any] = {
        "score_anls": anls_score,
        "score": anls_score,
        "judge_used": False,
        "judge_equivalent": None,
    }

    if judge is None:
        return result

    if not should_use_judge(
        anls_score=anls_score,
        answer_type=answer_type,
        gt=gt,
        pred=pred,
        threshold=judge.threshold,
    ):
        return result

    result["judge_used"] = True
    equivalent = await judge.is_equivalent(
        question=question,
        reference=gt,
        prediction=pred,
        answer_format=answer_type,
    )
    result["judge_equivalent"] = equivalent
    if equivalent:
        result["score"] = 1.0
    return result


def build_judge(config: dict[str, Any] | None) -> SemanticJudge | None:
    if not config or not config.get("enabled", True):
        return None
    return SemanticJudge(config)
