"""Tests for core/tariff_lookup.py."""

from __future__ import annotations

from datetime import date

import pytest

from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.core.tariff_model import MeasureType
from wto_policy.data.seed import load_us_tariff_seed


@pytest.fixture
def lookup() -> TariffLookup:
    return TariffLookup(load_us_tariff_seed())


class TestFind:
    def test_lighting_finds_301_and_mfn(self, lookup: TariffLookup) -> None:
        """LED 灯 (9405408000) 在 US 应同时命中 Section 301 List 4A + MFN."""
        results = lookup.find(hs_code="9405408000", origin="CN", destination="US")
        types = {m.measure_type for m in results}
        assert MeasureType.SECTION_301 in types
        assert MeasureType.MFN in types

    def test_section_301_list4a_rate(self, lookup: TariffLookup) -> None:
        results = lookup.find(hs_code="9405408000", origin="CN", destination="US")
        s301 = [m for m in results if m.measure_type == MeasureType.SECTION_301]
        assert any(m.ad_valorem_rate == 0.075 for m in s301)

    def test_steel_chapter_72_finds_232(self, lookup: TariffLookup) -> None:
        results = lookup.find(hs_code="720800", origin="CN", destination="US")
        types = {m.measure_type for m in results}
        assert MeasureType.SECTION_232 in types

    def test_ieepa_always_matches(self, lookup: TariffLookup) -> None:
        """IEEPA 用 '000000' 占位, 应匹配所有 HS 码 (前缀匹配)."""
        results = lookup.find(hs_code="950300", origin="CN", destination="US")
        types = {m.measure_type for m in results}
        assert MeasureType.IEEPA in types

    def test_wrong_origin_returns_empty(self, lookup: TariffLookup) -> None:
        results = lookup.find(hs_code="9405408000", origin="VN", destination="US")
        # MFN 仍命中(通配 XX), 但 Section 301 不命中(精确 CN)
        s301 = [m for m in results if m.measure_type == MeasureType.SECTION_301]
        assert s301 == []

    def test_wrong_destination_returns_empty(self, lookup: TariffLookup) -> None:
        results = lookup.find(hs_code="9405408000", origin="CN", destination="DE")
        assert results == []

    def test_future_date_excludes_301(self, lookup: TariffLookup) -> None:
        """List 1 是 2018-07-06 生效, 查 2017-01-01 应不命中."""
        results = lookup.find(
            hs_code="854100",  # 8541 在 List 1
            origin="CN",
            destination="US",
            on=date(2017, 1, 1),
        )
        s301 = [m for m in results if m.measure_type == MeasureType.SECTION_301]
        assert s301 == []


class TestGroupByType:
    def test_lighting_grouping(self, lookup: TariffLookup) -> None:
        results = lookup.find(hs_code="9405408000", origin="CN", destination="US")
        groups = lookup.group_by_type(results)
        # 9405 应至少 1 条 Section 301
        assert len(groups[MeasureType.SECTION_301]) >= 1
        # MFN 至少 1 条
        assert MeasureType.MFN in groups


class TestExtraMfn:
    """v0.2 新增: 从云端 DB 注入真实 MFN."""

    def test_add_mfn(self) -> None:
        lk = TariffLookup([])
        lk.add_mfn("85183020", 0.0)  # 蓝牙耳机官方 "Free"
        lk.add_mkn = None
        assert lk.get_mfn("85183020") == 0.0
        assert lk.get_mfn("8518302000") == 0.0  # 10 位 fallback 8 位

    def test_longest_prefix_wins(self) -> None:
        lk = TariffLookup([])
        lk.add_mfn("851830", 0.034)
        lk.add_mfn("85183020", 0.0)  # 更具体
        # 10 位用更具体的
        assert lk.get_mfn("8518302000") == 0.0
        # 6 位只能用 6 位的
        assert lk.get_mfn("8518300000") == 0.034

    def test_miss_returns_none(self) -> None:
        lk = TariffLookup([])
        lk.add_mfn("85183020", 0.0)
        assert lk.get_mfn("9999999999") is None

    def test_normalized_input(self) -> None:
        """支持 '8518.30.20' / '8518 30 20' 输入."""
        lk = TariffLookup([])
        lk.add_mfn("85183020", 0.05)
        assert lk.get_mfn("8518.30.20") == 0.05
        assert lk.get_mfn("8518 30 20") == 0.05
