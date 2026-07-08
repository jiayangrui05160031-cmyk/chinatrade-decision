"""Tests for core/decision_card.py."""

from __future__ import annotations

import pytest

from wto_policy.core.company_profile import CompanyProfile, TradeMode
from wto_policy.core.decision_card import DecisionCard, RiskLevel
from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.data.seed import load_us_tariff_seed


@pytest.fixture
def lookup() -> TariffLookup:
    return TariffLookup(load_us_tariff_seed())


@pytest.fixture
def zhongshan_lamp_factory() -> CompanyProfile:
    return CompanyProfile(
        name="中山灯具厂",
        sector="灯具",
        annual_export_usd=2_000_000,  # 中小企业
        main_destinations=["US"],
        trade_mode=TradeMode.GENERAL,
        has_aeo=False,
        main_hs_codes=["9405408000", "9405404000"],
    )


class TestDecisionCard:
    def test_basic_build(
        self, lookup: TariffLookup, zhongshan_lamp_factory: CompanyProfile
    ) -> None:
        card = DecisionCard.build(
            hs_code="9405408000",
            cif_value_usd=17200.0,  # 1000 灯 × $17.2
            quantity=1000,
            profile=zhongshan_lamp_factory,
            lookup=lookup,
        )
        assert card.profile_name == "中山灯具厂"
        assert card.total_tax > 0
        assert card.net_landed_cost > card.cif_value_usd
        # 3.59/件 * 1000 = 3590
        assert card.per_unit_tax == pytest.approx(3.59, rel=0.01)
        assert card.effective_rate > 0.20  # 20%+

    def test_section_301_risk_present(
        self, lookup: TariffLookup, zhongshan_lamp_factory: CompanyProfile
    ) -> None:
        card = DecisionCard.build(
            hs_code="9405408000",
            cif_value_usd=1000.0,
            profile=zhongshan_lamp_factory,
            lookup=lookup,
        )
        codes = {r.code for r in card.risks}
        assert "SECTION_301_APPLIES" in codes
        assert "IEEPA_FENTANYL" in codes

    def test_232_risk_for_steel(self, lookup: TariffLookup) -> None:
        profile = CompanyProfile(
            name="某钢制品公司",
            sector="钢铁",
            annual_export_usd=50_000_000,
            main_destinations=["US"],
            trade_mode=TradeMode.GENERAL,
        )
        card = DecisionCard.build(
            hs_code="720800",
            cif_value_usd=10000.0,
            profile=profile,
            lookup=lookup,
        )
        codes = {r.code for r in card.risks}
        assert "SECTION_232" in codes
        # 232 是 critical
        sec_232 = next(r for r in card.risks if r.code == "SECTION_232")
        assert sec_232.level == RiskLevel.CRITICAL

    def test_suggestions_for_sme_with_high_tariff(
        self, lookup: TariffLookup, zhongshan_lamp_factory: CompanyProfile
    ) -> None:
        card = DecisionCard.build(
            hs_code="9405408000",
            cif_value_usd=17200.0,
            profile=zhongshan_lamp_factory,
            lookup=lookup,
        )
        # 中小企业 + 20%+ 税率 → 应有 HIGH_TARIFF_EXPOSURE 建议
        codes = {s.code for s in card.suggestions}
        assert "HIGH_TARIFF_EXPOSURE" in codes

    def test_suggestions_for_express(
        self, lookup: TariffLookup
    ) -> None:
        profile = CompanyProfile(
            name="速卖通卖家",
            sector="小商品",
            annual_export_usd=500_000,
            main_destinations=["US"],
            trade_mode=TradeMode.EXPRESS,
        )
        card = DecisionCard.build(
            hs_code="9405408000",
            cif_value_usd=1000.0,
            profile=profile,
            lookup=lookup,
        )
        codes = {s.code for s in card.suggestions}
        assert "BULK_VS_EXPRESS" in codes

    def test_sources_collected(
        self, lookup: TariffLookup, zhongshan_lamp_factory: CompanyProfile
    ) -> None:
        card = DecisionCard.build(
            hs_code="9405408000",
            cif_value_usd=1000.0,
            profile=zhongshan_lamp_factory,
            lookup=lookup,
        )
        # 至少要有 source URL
        assert len(card.sources) >= 1
        assert any("federalregister.gov" in s for s in card.sources)
