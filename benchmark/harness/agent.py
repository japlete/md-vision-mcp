"""Agent construction for benchmark arms."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_openai import ChatOpenAI

from .middleware import ImageToolMessageTextMiddleware
from .prompts import system_prompt


Arm = Literal["baseline", "mdvision"]


def build_model(agent_config: dict[str, Any]) -> Any:
    model = agent_config["model"]
    provider = agent_config.get("provider", "openrouter")

    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouter runs.")

        extra_body: dict[str, Any] = {}
        service_tier = agent_config.get("service_tier")
        if service_tier:
            extra_body["service_tier"] = service_tier

        reasoning_effort = agent_config.get("reasoning_effort")
        if reasoning_effort:
            extra_body["reasoning"] = {"effort": reasoning_effort}

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=agent_config.get("openrouter_base_url", "https://openrouter.ai/api/v1"),
            default_headers={
                "HTTP-Referer": "https://github.com/japlete/md-vision-mcp",
                "X-Title": "md-vision benchmark",
            },
            **({"extra_body": extra_body} if extra_body else {}),
        )

    return model


async def create_benchmark_agent(
    *,
    arm: Arm,
    corpus_dir: Path,
    agent_config: dict[str, Any],
    response_format: type[Any],
    mdvision_server: Path | None = None,
) -> Any:
    tools = []
    if arm == "mdvision":
        if mdvision_server is None:
            raise ValueError("mdvision_server is required for the mdvision arm.")
        from .mcp import load_mdvision_tools

        tools.extend(await load_mdvision_tools(corpus_dir=corpus_dir, server_path=mdvision_server))

    backend = FilesystemBackend(root_dir=corpus_dir, virtual_mode=True)
    return create_deep_agent(
        model=build_model(agent_config),
        tools=tools,
        system_prompt=system_prompt(arm=arm),
        backend=backend,
        response_format=response_format,
        middleware=[ImageToolMessageTextMiddleware()],
    )
