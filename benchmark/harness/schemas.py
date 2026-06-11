"""Structured answer schemas for MMLongBench-Doc answer formats."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AnswerStatus = Literal["answered", "not_answerable", "fail_to_answer"]


class AnswerBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AnswerStatus = Field(
        default="answered",
        description="Use not_answerable only when the document does not contain enough evidence.",
    )


class IntAnswer(AnswerBase):
    answer: int | None = None


class FloatAnswer(AnswerBase):
    answer: float | None = None


class StrAnswer(AnswerBase):
    answer: str | None = None


class ListAnswer(AnswerBase):
    answer: list[str] | None = None


SCHEMAS: dict[str, type[AnswerBase]] = {
    "Int": IntAnswer,
    "Integer": IntAnswer,
    "Float": FloatAnswer,
    "Str": StrAnswer,
    "String": StrAnswer,
    "List": ListAnswer,
    "None": StrAnswer,
}


def schema_for_answer_format(answer_format: str | None) -> type[AnswerBase]:
    return SCHEMAS.get(str(answer_format or "Str"), StrAnswer)


def structured_to_prediction(value: Any) -> Any:
    if value is None:
        return "Fail to answer"
    if isinstance(value, BaseModel):
        payload = value.model_dump()
    elif isinstance(value, dict):
        payload = value
    else:
        return str(value).strip()

    status = payload.get("status", "answered")
    if status == "not_answerable":
        return "Not answerable"
    if status == "fail_to_answer":
        return "Fail to answer"

    answer = payload.get("answer")
    if answer is None:
        return "Fail to answer"
    return answer
