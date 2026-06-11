"""Tests for benchmark harness middleware."""

from langchain_core.messages import HumanMessage, ToolMessage

from harness.middleware import ImageToolMessageTextMiddleware, _ensure_tool_message_text


def test_ensure_tool_message_text_adds_caption_for_image_only() -> None:
    message = ToolMessage(
        content=[{"type": "image", "base64": "abc", "mime_type": "image/png"}],
        name="read_file",
        tool_call_id="call-1",
        additional_kwargs={"read_file_path": "/doc/assets/chart.png"},
    )

    patched = _ensure_tool_message_text(message)

    assert patched.content_blocks[0] == {
        "type": "text",
        "text": "Contents of /doc/assets/chart.png:",
    }
    assert patched.content_blocks[1]["type"] == "image"


def test_ensure_tool_message_text_leaves_text_messages_unchanged() -> None:
    message = ToolMessage(content="line 1\nline 2", name="read_file", tool_call_id="call-2")

    assert _ensure_tool_message_text(message) is message


def test_image_tool_message_text_middleware_patches_model_request() -> None:
    middleware = ImageToolMessageTextMiddleware()
    image_message = ToolMessage(
        content=[{"type": "image", "base64": "abc", "mime_type": "image/png"}],
        name="read_file",
        tool_call_id="call-3",
        additional_kwargs={"read_file_path": "/doc/assets/chart.png"},
    )

    class Request:
        def __init__(self, messages: list[object]) -> None:
            self.messages = messages

        def override(self, *, messages: list[object]) -> "Request":
            return Request(messages)

    request = Request([HumanMessage(content="hello"), image_message])
    seen: list[object] = []

    def handler(updated_request: Request) -> str:
        seen.append(updated_request.messages[1])
        return "ok"

    assert middleware.wrap_model_call(request, handler) == "ok"
    assert seen[0].content_blocks[0]["type"] == "text"
