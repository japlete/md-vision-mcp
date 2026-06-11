"""Trace and token metric extraction from LangChain/Deep Agents outputs."""

from __future__ import annotations

from collections import Counter
from typing import Any


def get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def iter_messages(run_output: Any) -> list[Any]:
    messages = get_value(run_output, "messages", [])
    return list(messages or [])


def extract_structured_response(run_output: Any) -> Any:
    for key in ("structured_response", "response", "final_response"):
        value = get_value(run_output, key)
        if value is not None:
            return value
    return None


def extract_tool_calls(run_output: Any) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    total = 0

    for message in iter_messages(run_output):
        tool_calls = get_value(message, "tool_calls", None) or []
        if tool_calls:
            for call in tool_calls:
                name = get_value(call, "name") or get_value(call, "function", {}).get("name")
                if name:
                    counts[str(name)] += 1
                    total += 1
            continue

        additional_kwargs = get_value(message, "additional_kwargs", {}) or {}
        for call in additional_kwargs.get("tool_calls", []) or []:
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name") or call.get("name")
            if name:
                counts[str(name)] += 1
                total += 1

    return {"tool_calls_total": total, "tool_calls_by_name": dict(counts)}


def extract_token_usage(run_output: Any) -> dict[str, int]:
    input_tokens = 0
    output_tokens = 0

    for message in iter_messages(run_output):
        usage = get_value(message, "usage_metadata", None)
        if usage:
            input_tokens += int(get_value(usage, "input_tokens", 0) or 0)
            output_tokens += int(get_value(usage, "output_tokens", 0) or 0)
            continue

        response_metadata = get_value(message, "response_metadata", {}) or {}
        token_usage = response_metadata.get("token_usage", {})
        input_tokens += int(token_usage.get("prompt_tokens", 0) or 0)
        output_tokens += int(token_usage.get("completion_tokens", 0) or 0)

    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def collect_metrics(run_output: Any) -> dict[str, Any]:
    return {
        **extract_tool_calls(run_output),
        **extract_token_usage(run_output),
    }
