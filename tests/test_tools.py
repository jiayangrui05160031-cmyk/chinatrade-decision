"""Tests for agent/tools.py — 用真实数据离线测试."""

from __future__ import annotations

import json

from wto_policy.agent.tools import (
    call_tool,
    generate_decision_card,
    get_tool_schemas,
    lookup_tariff,
    search_hs_codes,
)


class TestSearchHsCodes:
    def test_chinese_bluetooth(self) -> None:
        results = search_hs_codes("蓝牙耳机", lang="zh")
        assert len(results) > 0
        assert any("蓝牙" in r["description_zh"] for r in results)

    def test_english_lamp(self) -> None:
        results = search_hs_codes("led lamp", lang="en", limit=3)
        assert len(results) > 0

    def test_empty(self) -> None:
        results = search_hs_codes("不存在的品名zzzz", lang="zh")
        assert results == []


class TestLookupTariff:
    def test_led_lamp(self) -> None:
        r = lookup_tariff("9405408000", cif_value_usd=17200.0)
        assert r["hs_code"] == "9405408000"
        assert r["rates"]["section_301"] == 0.075
        assert r["rates"]["ieepa"] == 0.10
        assert r["effective_rate"] == 0.209

    def test_steel_has_232(self) -> None:
        r = lookup_tariff("720800", cif_value_usd=10000.0)
        assert r["rates"]["section_232"] == 0.25

    def test_amounts_sum(self) -> None:
        r = lookup_tariff("9405408000", cif_value_usd=1000.0)
        amts = r["amount_usd"]
        assert abs(amts["total"] - (amts["mfn"] + amts["section_301"] + amts["section_232"] + amts["ieepa"])) < 0.01


class TestGenerateDecisionCard:
    def test_basic(self) -> None:
        card = generate_decision_card(
            hs_code="9405408000", cif_value_usd=17200.0, quantity=1000,
            company_name="中山灯具厂", sector="灯具", annual_export_usd=2_000_000,
        )
        assert card["total_tax"] > 0
        assert len(card["risks"]) > 0


class TestRegistry:
    def test_schemas_valid(self) -> None:
        schemas = get_tool_schemas()
        names = {s["function"]["name"] for s in schemas}
        assert names == {
            "search_hs_codes", "lookup_tariff",
            "generate_decision_card", "search_recent_policy",
        }

    def test_call_tool_roundtrip(self) -> None:
        result_str = call_tool("search_hs_codes", {"query": "led lamp", "lang": "en", "limit": 2})
        result = json.loads(result_str)
        assert isinstance(result, list)

    def test_call_unknown_tool(self) -> None:
        r = json.loads(call_tool("nope", {}))
        assert "error" in r
