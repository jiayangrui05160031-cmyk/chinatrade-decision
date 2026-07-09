"""LLM 客户端 (多 provider 支持) + 函数调用 / 对话补全封装.

支持的 provider (都兼容 OpenAI Chat Completions 协议):
- MiniMax    (默认, 推荐, 国内访问快)
- OpenAI    (gpt-4o / gpt-4-turbo)
- DeepSeek  (deepseek-chat / deepseek-coder, 国产)
- Qwen      (通义千问 qwen-plus / qwen-max, 阿里)
- Zhipu     (智谱 GLM-4)
- Ollama    (本地模型, 完全免费)

所有 provider 走 OpenAI 协议, 用 base_url + model 区分.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict

# ============ Provider 预设 ============
# 选 provider 自动填 base_url + 默认 model

PROVIDERS: dict[str, dict[str, str]] = {
    "minimax": {
        "base_url": "https://api.minimaxi.com/v1",
        "default_model": "MiniMax-Text-01",
        "api_key_env": "MINIMAX_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "api_key_env": "DASHSCOPE_API_KEY",  # 阿里
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "api_key_env": "ZHIPU_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.1:8b",
        "api_key_env": "",  # Ollama 不需 key
    },
    "custom": {
        "base_url": "",  # 用户自己提供
        "default_model": "",
        "api_key_env": "",
    },
}


class LlmMessage(BaseModel):
    """一条消息."""

    model_config = ConfigDict(extra="ignore")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class LlmClient:
    """多 provider LLM 客户端 (OpenAI 协议).

    用法:
        # 方式 1: provider 名字 (自动从 env 读 key)
        client = LlmClient(provider="openai")

        # 方式 2: 完整自定义
        client = LlmClient(
            base_url="https://your-api.com/v1",
            api_key="sk-xxx",
            model="gpt-4o",
        )

        # 方式 3: 环境变量 (兼容旧代码)
        # MINIMAX_API_KEY + MINIMAX_BASE_URL + MINIMAX_MODEL
        client = LlmClient()  # 默认 minimax
    """

    def __init__(
        self,
        *,
        provider: str = "minimax",
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        # 1. 找 provider 预设
        if provider not in PROVIDERS:
            raise ValueError(
                f"Unknown provider: {provider!r}. "
                f"选: {', '.join(PROVIDERS.keys())}"
            )
        cfg = PROVIDERS[provider]

        # 2. 按优先级读 api_key: 参数 > 对应 env > 通用 env
        if api_key:
            self.api_key = api_key
        elif cfg["api_key_env"] and os.environ.get(cfg["api_key_env"]):
            self.api_key = os.environ[cfg["api_key_env"]]
        elif os.environ.get("OPENAI_API_KEY"):  # 通用 fallback
            self.api_key = os.environ["OPENAI_API_KEY"]
        elif os.environ.get("MINIMAX_API_KEY"):  # 旧兼容
            self.api_key = os.environ["MINIMAX_API_KEY"]
        elif provider == "ollama":
            self.api_key = "ollama"  # 占位, 实际不需要
        else:
            raise ValueError(
                f"API key not set. 请设环境变量 {cfg['api_key_env']} "
                f"或在构造时传 api_key=..."
            )

        # 3. base_url
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif os.environ.get("LLM_BASE_URL"):
            self.base_url = os.environ["LLM_BASE_URL"].rstrip("/")
        elif cfg["base_url"]:
            self.base_url = cfg["base_url"]
        else:
            raise ValueError(
                f"base_url not set. provider={provider!r} 需自定义 base_url"
            )

        # 4. model
        if model:
            self.model = model
        elif os.environ.get("LLM_MODEL"):
            self.model = os.environ["LLM_MODEL"]
        else:
            self.model = cfg["default_model"]

        self.provider = provider
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        # Ollama 可以不传 key
        if self.api_key and self.api_key != "ollama":
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.2,
        max_tokens: int = 1024,
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

    def __repr__(self) -> str:
        return f"LlmClient(provider={self.provider!r}, model={self.model!r}, base_url={self.base_url})"


__all__ = ["PROVIDERS", "LlmClient", "LlmMessage"]
