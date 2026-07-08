"""Tests for agent/llm_client.py.

只测配置/校验, 不实跑(避免消耗 API 配额, 也避免 CI 失败).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wto_policy.agent.llm_client import LlmClient, LlmMessage


class TestConfig:
    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        with pytest.raises(ValueError, match="MINIMAX_API_KEY"):
            LlmClient(api_key="")

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-123")
        c = LlmClient()
        assert c.api_key == "test-key-123"
        assert c.base_url.startswith("https://")


class TestMessage:
    def test_user_message(self) -> None:
        m = LlmMessage(role="user", content="hi")
        assert m.content == "hi"

    def test_tool_message(self) -> None:
        m = LlmMessage(role="tool", content='{"x":1}', tool_call_id="abc")
        d = m.model_dump(exclude_none=True)
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "abc"

    def test_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            LlmMessage(role="manager", content="x")  # type: ignore[arg-type]
