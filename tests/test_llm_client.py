"""Tests for agent/llm_client.py — 多 provider 支持."""

from __future__ import annotations

import pytest

from wto_policy.agent.llm_client import PROVIDERS, LlmClient, LlmMessage


class TestProviderRegistry:
    def test_all_providers_have_base_url(self) -> None:
        """除 'custom' / 'ollama' 外, 每个 provider 都有 api_key_env (ollama 免 key)."""
        for name, cfg in PROVIDERS.items():
            if name in ("custom", "ollama"):  # 不需要 API key
                continue
            assert cfg.get("base_url"), f"{name} 缺 base_url"
            assert cfg.get("default_model"), f"{name} 缺 default_model"
            assert cfg.get("api_key_env"), f"{name} 缺 api_key_env"

    def test_provider_count(self) -> None:
        assert len(PROVIDERS) == 7  # minimax/openai/deepseek/qwen/zhipu/ollama/custom


class TestMissingKey:
    def test_no_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k in ("OPENAI_API_KEY", "MINIMAX_API_KEY",
                  "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY",
                  "ZHIPU_API_KEY", "LLM_BASE_URL"):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(ValueError, match="API key not set"):
            LlmClient(provider="openai")

    def test_minimax_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """默认 provider=minimax, 读 MINIMAX_API_KEY."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        c = LlmClient()
        assert c.provider == "minimax"
        assert c.model == "MiniMax-Text-01"


class TestExplicitKey:
    def test_api_key_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        c = LlmClient(provider="minimax", api_key="explicit-key")
        assert c.api_key == "explicit-key"

    def test_base_url_override(self) -> None:
        c = LlmClient(
            provider="minimax", api_key="x",
            base_url="https://my-proxy.com/v1",
        )
        assert c.base_url == "https://my-proxy.com/v1"

    def test_model_override(self) -> None:
        c = LlmClient(provider="openai", api_key="x", model="gpt-4-turbo")
        assert c.model == "gpt-4-turbo"


class TestEnvPriority:
    """环境变量优先级: LLM_MODEL > provider 专用 env."""

    def test_generic_model_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "x")
        monkeypatch.setenv("LLM_MODEL", "custom-model-123")
        c = LlmClient()
        assert c.model == "custom-model-123"

    def test_generic_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "x")
        monkeypatch.setenv("LLM_BASE_URL", "https://proxy.example.com/v1")
        c = LlmClient()
        assert c.base_url == "https://proxy.example.com/v1"


class TestOllama:
    """Ollama 本地, 无需 API key."""

    def test_ollama_no_key_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k in ("OPENAI_API_KEY", "MINIMAX_API_KEY",
                  "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY",
                  "ZHIPU_API_KEY", "LLM_BASE_URL"):
            monkeypatch.delenv(k, raising=False)
        c = LlmClient(provider="ollama")
        assert c.provider == "ollama"
        assert "11434" in c.base_url


class TestFallback:
    """OPENAI_API_KEY 作为通用 fallback."""

    def test_openai_key_universally_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-universal")
        c = LlmClient(provider="minimax")
        assert c.api_key == "sk-universal"


class TestMessageModel:
    def test_basic(self) -> None:
        m = LlmMessage(role="user", content="hi")
        d = m.model_dump(exclude_none=True)
        assert d["role"] == "user"
        assert d["content"] == "hi"

    def test_tool_message(self) -> None:
        m = LlmMessage(role="tool", content='{"x":1}', tool_call_id="t1")
        d = m.model_dump(exclude_none=True)
        assert d["tool_call_id"] == "t1"

    def test_invalid_role(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            LlmMessage(role="hacker", content="x")  # type: ignore[arg-type]


class TestRepr:
    def test_repr_shows_config(self) -> None:
        c = LlmClient(provider="deepseek", api_key="x")
        s = repr(c)
        assert "deepseek" in s
        assert "deepseek-chat" in s
