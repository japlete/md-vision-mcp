"""Neutral prompts shared by benchmark arms."""

from __future__ import annotations

from typing import Literal

Arm = Literal["baseline", "mdvision"]

_BASE_SYSTEM_PROMPT = """You answer questions using the documents available in the working folder.

Use tools to inspect the relevant document before answering. Keep the final
answer concise and use the requested structured answer format. If the available
document does not contain enough evidence, return status "not_answerable".

Path conventions:
- Filesystem tools (read_file, ls, glob, grep, write_file, edit_file) use virtual
  absolute paths: a leading `/` is relative to the document workspace root, not the
  system root. Example: `/my-doc/index.md` refers to `my-doc/index.md` under the
  workspace.
- Shell/bash/terminal tools use regular filesystem paths. A leading `/` is the system
  root, not the document workspace.
"""

_MDVISION_PATH_PROMPT = """- Markdown tools (index_md, read_md_with_images) also use regular filesystem
  paths. Pass paths relative to the document workspace without a leading `/`, for
  example `my-doc/index.md` or `my-doc/` for a folder. If a markdown tool returns an
  error, read the message, fix the path or arguments, and try again.
"""

# Backward-compatible alias for callers that import a single prompt string.
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT


def system_prompt(*, arm: Arm) -> str:
    if arm == "mdvision":
        return _BASE_SYSTEM_PROMPT + "\n" + _MDVISION_PATH_PROMPT
    return _BASE_SYSTEM_PROMPT


def question_prompt(doc_folder: str, question: str) -> str:
    return f"""Use the document folder `{doc_folder}` to answer this question:

{question}

Return only the structured final answer."""
