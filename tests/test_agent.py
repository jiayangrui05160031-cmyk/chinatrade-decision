"""Tests for agent/agent.py — 离线测试 sanitize + run 边界, 不实跑 LLM."""

from __future__ import annotations

from wto_policy.agent.agent import Agent


class TestSanitize:
    def test_empty(self) -> None:
        assert Agent._sanitize_input("") == ""

    def test_whitespace(self) -> None:
        assert Agent._sanitize_input("   \n\t  ") == ""

    def test_normal(self) -> None:
        assert Agent._sanitize_input("蓝牙耳机") == "蓝牙耳机"

    def test_truncate(self) -> None:
        long = "x" * 5000
        out = Agent._sanitize_input(long, max_len=100)
        assert len(out) <= 110

    def test_strip_control_chars(self) -> None:
        # \x00, \x07 是控制字符
        assert Agent._sanitize_input("hi\x00\x07there") == "hithere"

    def test_emoji_preserved(self) -> None:
        assert "🎉" in Agent._sanitize_input("我要 🎉 出货")

    def test_chinese_preserved(self) -> None:
        assert Agent._sanitize_input("中山 LED 灯具厂 5万美金") == "中山 LED 灯具厂 5万美金"


class TestRunEmpty:
    def test_empty_input_friendly(self) -> None:
        """空输入 → 友好反问, 不调 LLM."""
        # 走 sanitize 路径, 不实例化 Agent (避免需 API key)
        s = Agent._sanitize_input("   ")
        assert s == ""
        s = Agent._sanitize_input("")
        assert s == ""
