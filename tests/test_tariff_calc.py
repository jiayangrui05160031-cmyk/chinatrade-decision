"""Tests for core/tariff_calc.py."""

from __future__ import annotations

from datetime import date

import pytest

from wto_policy.core.tariff_calc import calculate_tariff
from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.core.tariff_model import MeasureType
from wto_policy.data.seed import load_us_tariff_seed


@pytest.fixture
def lookup() -> TariffLookup:
    return TariffLookup(load_us_tariff_seed())


class TestCalculateTariff:
    def test_led_lamp_breakdown(self, lookup: TariffLookup) -> None:
        """9405408000 (LED 灯) 从中国出口到美国, CIF 15000 USD.
        预期: MFN 3.4% + Section 301 List 4A 7.5% + IEEPA 10% = 20.9%
        """
        b = calculate_tariff(
            hs_code="9405408000",
            cif_value_usd=15000.0,
            lookup=lookup,
        )
        assert b.mfn == pytest.approx(510.0, rel=0.01)   # 15000 * 0.034
        assert b.section_301 == pytest.approx(1125.0, rel=0.01)  # 15000 * 0.075
        assert b.ieepa == pytest.approx(1500.0, rel=0.01)  # 15000 * 0.10
        # 总计 510 + 1125 + 1500 = 3135
        assert b.total_duty == pytest.approx(3135.0, rel=0.01)
        # 实际税率 3135/15000 = 0.209 = 20.9%
        assert b.effective_rate == pytest.approx(0.209, rel=0.01)

    def test_lines_include_all(self, lookup: TariffLookup) -> None:
        b = calculate_tariff(hs_code="9405408000", cif_value_usd=1000.0, lookup=lookup)
        types = {line.measure_type for line in b.lines}
        assert MeasureType.MFN in types
        assert MeasureType.SECTION_301 in types
        assert MeasureType.IEEPA in types

    def test_232_applies_to_steel(self, lookup: TariffLookup) -> None:
        """720800 钢铁应触发 Section 232 25%."""
        b = calculate_tariff(hs_code="720800", cif_value_usd=10000.0, lookup=lookup)
        assert b.section_232 == pytest.approx(2500.0, rel=0.01)

    def test_232_does_not_apply_to_lighting(self, lookup: TariffLookup) -> None:
        b = calculate_tariff(hs_code="9405408000", cif_value_usd=1000.0, lookup=lookup)
        assert b.section_232 == 0.0

    def test_future_date_excludes_301(self, lookup: TariffLookup) -> None:
        """2017 年, Section 301 还未生效, 应只算 MFN + IEEPA(也是未来)."""
        b = calculate_tariff(
            hs_code="9405408000",
            cif_value_usd=1000.0,
            on=date(2017, 1, 1),
            lookup=lookup,
        )
        assert b.section_301 == 0.0
        assert b.ieepa == 0.0  # IEEPA 2025 才有
        assert b.mfn > 0  # MFN 一直有

    def test_zero_value(self, lookup: TariffLookup) -> None:
        b = calculate_tariff(hs_code="9405408000", cif_value_usd=0.0, lookup=lookup)
        assert b.total_duty == 0.0
        assert b.effective_rate == 0.0
