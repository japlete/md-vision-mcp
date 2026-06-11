"""Benchmark middleware patches for provider compatibility."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AnyMessage, ToolMessage


def _ensure_tool_message_text(message: ToolMessage) -> ToolMessage:
    """Add a text block when a tool message is image-only.

    Deep Agents returns image reads as media-only ToolMessages. Some OpenRouter
    providers (e.g. Xiaomi) reject those requests with ``text is not set``.
    """
    blocks = list(message.content_blocks)
    if not blocks:
        return message

    has_text = any(block.get("type") == "text" for block in blocks)
    has_media = any(block.get("type") != "text" for block in blocks)
    if not has_media or has_text:
        return message

    kwargs = message.additional_kwargs or {}
    path = kwargs.get("read_file_path") or message.name or "file"
    return ToolMessage(
        content=[{"type": "text", "text": f"Contents of {path}:"}, *blocks],
        name=message.name,
        tool_call_id=message.tool_call_id,
        additional_kwargs=kwargs,
        status=message.status,
        id=message.id,
    )


def _patch_messages(messages: list[AnyMessage]) -> tuple[list[AnyMessage], bool]:
    patched: list[AnyMessage] = []
    changed = False
    for message in messages:
        if isinstance(message, ToolMessage):
            updated = _ensure_tool_message_text(message)
            if updated is not message:
                patched.append(updated)
                changed = True
                continue
        patched.append(message)
    return patched, changed


class ImageToolMessageTextMiddleware(AgentMiddleware):
    """Ensure multimodal tool results include a text block for strict providers."""

    def wrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        messages, changed = _patch_messages(request.messages)
        if changed:
            request = request.override(messages=messages)
        return handler(request)

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        messages, changed = _patch_messages(request.messages)
        if changed:
            request = request.override(messages=messages)
        return await handler(request)
