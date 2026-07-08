"""Tests for agent/policy_summarizer.py — 离线基本校验, 不实跑 LLM."""

from __future__ import annotations

import pytest

from wto_policy.agent.policy_summarizer import summarize


def test_empty_text() -> None:
    assert summarize("") == "(无摘要)"
    assert summarize("   ") == "(无摘要)"


def test_prompt_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock LLM 验证 prompt 模板正确性."""
    captured: list[list] = []

    class FakeLlm:
        def text(self, messages, **kw):  # type: ignore[no-untyped-def]
            captured.append(messages)
            return "对华 Section 301 List 4A 7.5%"

    from wto_policy.agent import policy_summarizer as mod
    out = summarize(
        "USTR modifies Section 301 List 4A duty rate to 7.5% effective Feb 2026",
        llm=FakeLlm(),  # type: ignore[arg-type]
    )
    assert out == "对华 Section 301 List 4A 7.5%"
    # 检查 prompt 包含原文本 + 模板关键词
    user_msg = captured[0][0].content
    assert "7.5%" in user_msg
    assert "80 字中文摘要" in user_msg
