from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Provider = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class LLMConfig:
    provider: Provider
    model: str
    temperature: float = 0.2
    max_tokens: int | None = 1500
    base_url: str | None = None
    api_key: str | None = None


def get_chat_model(cfg: LLMConfig):
    """
    Create a LangChain chat model.

    Notes:
    - We intentionally do not auto-pick a model string; the user config/UI supplies it.
    - API keys are expected via env vars (OPENAI_API_KEY / ANTHROPIC_API_KEY).
    """

    if cfg.provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {"model": cfg.model, "temperature": cfg.temperature}
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        return ChatOpenAI(**kwargs)

    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs = {"model": cfg.model, "temperature": cfg.temperature}
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        return ChatAnthropic(**kwargs)

    raise ValueError(f"Unsupported provider: {cfg.provider}")

