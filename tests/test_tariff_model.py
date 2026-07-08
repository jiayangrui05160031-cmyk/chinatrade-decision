"""Tests for core/tariff_model.py."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from wto_policy.core.tariff_model import (
    Country,
    HsCode,
    MeasureType,
    TariffMeasure,
)


class TestCountry:
    def test_basic(self):
        c = Country(code="us", name_zh="美国", name_en="United States")
        assert c.code == "US"  # 自动大写
        assert c.name_zh == "美国"

    def test_frozen(self):
        c = Country(code="US", name_zh="美国", name_en="United States")
        with pytest.raises(ValidationError):
            c.code = "DE"  # type: ignore[misc]

    def test_invalid_length(self):
        with pytest.raises(ValidationError):
            Country(code="USA", name_zh="美国", name_en="US")  # type: ignore[arg-type]


class TestHsCode:
    def test_6_digit(self):
        h = HsCode(
            code="940540",
            level=6,
            chapter="94",
            description_zh="其他电灯及照明装置",
            description_en="Other electric lamps and lighting fittings",
            source="usitc-htsus-2026",
        )
        assert h.chapter == "94"
        assert h.parent_code is None

    def test_10_digit_with_parent(self):
        h = HsCode(
            code="9405408000",
            level=10,
            parent_code="940540",
            chapter="94",
            description_zh="LED 台灯",
            description_en="LED table lamps",
            source="usitc-htsus-2026",
        )
        assert h.level == 10
        assert h.parent_code == "940540"

    def test_rejects_non_digits(self):
        with pytest.raises(ValidationError):
            HsCode(
                code="9405A0",
                level=6,
                chapter="94",
                description_zh="x",
                description_en="x",
                source="x",
            )

    def test_level_must_match_length(self):
        with pytest.raises(ValidationError):
            HsCode(
                code="940540",
                level=8,  # 不匹配 6 位
                chapter="94",
                description_zh="x",
                description_en="x",
                source="x",
            )


class TestTariffMeasure:
    def test_section_301(self):
        m = TariffMeasure(
            hs_code="9405408000",
            origin="CN",
            destination="US",
            measure_type=MeasureType.SECTION_301,
            ad_valorem_rate=0.075,
            effective_from=date(2018, 7, 6),
            legal_basis="Section 301 List 3",
            source_url="https://ustr.gov/issue-areas/enforcement/section-301-investigations",
            crawled_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        assert m.measure_type == MeasureType.SECTION_301
        assert m.ad_valorem_rate == 0.075

    def test_rejects_negative_rate(self):
        with pytest.raises(ValidationError):
            TariffMeasure(
                hs_code="9405408000",
                origin="CN",
                destination="US",
                measure_type=MeasureType.MFN,
                ad_valorem_rate=-0.1,
                effective_from=date(2026, 1, 1),
                source_url="x",
                crawled_at=datetime.now(tz=UTC),
            )

    def test_ad_valorem_above_one_allowed(self):
        """某些反倾销税率可能 > 100% (例 100%+)."""
        m = TariffMeasure(
            hs_code="0000000000",
            origin="CN",
            destination="US",
            measure_type=MeasureType.ANTI_DUMPING,
            ad_valorem_rate=2.5,  # 250%
            effective_from=date(2020, 1, 1),
            source_url="x",
            crawled_at=datetime.now(tz=UTC),
        )
        assert m.ad_valorem_rate == 2.5
