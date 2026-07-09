"""Tests for agent/memory.py."""

from __future__ import annotations

from wto_policy.agent.memory import (
    SessionMemory,
    load_memory,
    memory_to_system_msg,
    save_memory,
)


class TestExtractContext:
    def test_chinese_money_wan(self) -> None:
        m = SessionMemory()
        m.update_from_user("1 万美金")
        assert m.cif_value_usd == 10000.0

    def test_english_money_k(self) -> None:
        m = SessionMemory()
        m.update_from_user("17.2k USD")
        assert m.cif_value_usd == 17200.0

    def test_plain_number(self) -> None:
        m = SessionMemory()
        m.update_from_user("17200 美元")
        assert m.cif_value_usd == 17200.0

    def test_hs_code(self) -> None:
        m = SessionMemory()
        m.update_from_user("HS 9405408000")
        assert "9405408000" in m.hs_codes

    def test_quantity(self) -> None:
        m = SessionMemory()
        m.update_from_user("1000 件")
        assert m.quantity == 1000
        m.update_from_user("改成 2000 个")
        assert m.quantity == 2000  # 覆盖

    def test_destination(self) -> None:
        m = SessionMemory()
        m.update_from_user("发往美国")
        assert m.destination == "US"
        m.update_from_user("卖往德国")
        assert m.destination == "DE"

    def test_complex_msg(self) -> None:
        m = SessionMemory()
        m.update_from_user("HS 8518302000 蓝牙耳机, 25 美金一个, 100 个, 走 DHL 到美国")
        assert "8518302000" in m.hs_codes
        assert m.quantity == 100
        assert m.destination == "US"


class TestContextStr:
    def test_empty(self) -> None:
        m = SessionMemory()
        assert memory_to_system_msg(m) == ""

    def test_has_context(self) -> None:
        m = SessionMemory()
        m.update_from_user("HS 9405408000, 17200 美元, 美国")
        s = memory_to_system_msg(m)
        assert "9405408000" in s
        assert "17200" in s
        assert "US" in s

    def test_includes_tool_result(self) -> None:
        m = SessionMemory()
        m.last_tool_result = {"amount_usd": {"total": 1234.5}, "effective_rate": 0.21}
        s = memory_to_system_msg(m)
        assert "$1234.5" in s
        assert "21.0%" in s


class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path, monkeypatch) -> None:
        # 切到 tmp 目录
        from wto_policy.agent import memory
        monkeypatch.setattr(memory, "SESSION_DIR", tmp_path)
        m = SessionMemory()
        m.update_from_user("HS 9405408000, 100 万 USD")
        m.hs_codes.append("940510")

        p = save_memory(m, "test_session")
        assert p.exists()

        m2 = load_memory("test_session")
        assert "9405408000" in m2.hs_codes
        assert m2.cif_value_usd == 1000000.0

    def test_load_missing_returns_empty(self, monkeypatch, tmp_path) -> None:
        from wto_policy.agent import memory
        monkeypatch.setattr(memory, "SESSION_DIR", tmp_path)
        m = load_memory("nonexistent")
        assert m.hs_codes == []
        assert m.cif_value_usd is None


class TestTurnAppend:
    def test_turn_history(self) -> None:
        m = SessionMemory()
        m.update_from_user("HS 9405408000")
        m.update_from_assistant("MFN 3.4%...")
        assert len(m.turns) == 2
        assert m.turns[0]["role"] == "user"
        assert m.turns[1]["role"] == "assistant"
