"""LLM 客户端 (MiniMax) + 函数调用 / 对话补全封装.

MiniMax API 兼容 OpenAI Chat Completions 协议, 同时原生支持 function calling / tools.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict

DEFAULT_BASE = "https://api.minimaxi.com/v1"
DEFAULT_MODEL = "MiniMax-Text-01"


class LlmMessage(BaseModel):
    """一条消息."""

    model_config = ConfigDict(extra="ignore")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class LlmClient:
    """薄封装 MiniMax Chat Completions API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = (base_url or os.environ.get("MINIMAX_BASE_URL", DEFAULT_BASE)).rstrip("/")
        self.model = model or os.environ.get("MINIMAX_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        if not self.api_key:
            msg = "MINIMAX_API_KEY not set"
            raise ValueError(msg)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """一次 Chat Completions 调用. 返回原始 dict."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            )
        if r.status_code != 200:
            msg = f"LLM error {r.status_code}: {r.text[:500]}"
            raise RuntimeError(msg)
        return r.json()

    def text(self, messages: list[LlmMessage], **kw: Any) -> str:
        """只取第一个 choice 的 content."""
        resp = self.chat(messages, **kw)
        return resp["choices"][0]["message"].get("content", "") or ""


__all__ = ["LlmClient", "LlmMessage"]
