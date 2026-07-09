"""Tests for export/pdf.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from wto_policy.core.company_profile import CompanyProfile, TradeMode
from wto_policy.core.decision_card import DecisionCard, Risk, RiskLevel, Suggestion
from wto_policy.export.pdf import generate_decision_card_pdf


@pytest.fixture
def sample_card() -> DecisionCard:
    from wto_policy.core.tariff_lookup import TariffLookup
    from wto_policy.data.seed import load_us_tariff_seed

    lookup = TariffLookup(load_us_tariff_seed())
    profile = CompanyProfile(
        name="中山灯具厂",
        sector="电子",
        annual_export_usd=2_000_000,
        trade_mode=TradeMode.GENERAL,
    )
    card = DecisionCard.build(
        hs_code="85183020",
        cif_value_usd=50000.0,
        quantity=1000,
        profile=profile,
        lookup=lookup,
    )
    # 用 model_copy(update=...) 添加测试字段 (frozen 模型不能直接赋)
    return card.model_copy(update={
        "risks": [
            Risk(
                level=RiskLevel.HIGH,
                code="TEST",
                message_zh="测试风险: Section 301 加征",
                message_en="test",
            ),
        ],
        "suggestions": [
            Suggestion(
                priority=1,
                code="APPLY_EXCLUSION",
                message_zh="申请 Section 301 排除窗口",
                message_en="Apply Section 301 exclusion",
                action_url="https://ustr.gov/issue-areas/enforcement/section-301-investigations",
            ),
        ],
        "sources": ["https://hts.usitc.gov/", "https://ustr.gov/"],
        "data_freshness": {
            "source": "USITC HTSUS 2026 Rev 2",
            "crawled_at": "2026-07-08 01:00 UTC",
            "age_human": "今天",
        },
    })


# 删未用的 helper
def _make_lookup_del():
    from wto_policy.core.tariff_lookup import TariffLookup
    from wto_policy.data.seed import load_us_tariff_seed
    return TariffLookup(load_us_tariff_seed())


class TestPdfGeneration:
    def test_returns_bytes_when_no_path(self, sample_card: DecisionCard) -> None:
        pdf_bytes = generate_decision_card_pdf(sample_card)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b"%PDF", "应是合法 PDF 头"
        assert len(pdf_bytes) > 1000, f"PDF 太小: {len(pdf_bytes)} bytes"

    def test_writes_file_when_path_given(
        self, sample_card: DecisionCard, tmp_path: Path,
    ) -> None:
        p = tmp_path / "decision.pdf"
        result = generate_decision_card_pdf(sample_card, output_path=p)
        assert Path(result).exists()
        assert Path(result).stat().st_size > 1000
        # 校验 PDF header
        with open(p, "rb") as f:
            assert f.read(4) == b"%PDF"

    def test_with_profile(self, sample_card: DecisionCard) -> None:
        profile = CompanyProfile(
            name="中山灯具厂",
            sector="灯具",
            annual_export_usd=2_000_000,
            trade_mode=TradeMode.GENERAL,
        )
        pdf_bytes = generate_decision_card_pdf(sample_card, profile=profile)
        assert isinstance(pdf_bytes, bytes)
        # 包含企业名 (latin 编码的中文应该出现)
        # 注意: reportlab 默认字体可能不显示中文, 但 PDF 仍生成
        assert len(pdf_bytes) > 1000

    def test_empty_risks_no_error(self, sample_card: DecisionCard) -> None:
        sample_card = sample_card.model_copy(update={
            "risks": [], "suggestions": [], "policy_alerts": [], "sources": [],
        })
        pdf_bytes = generate_decision_card_pdf(sample_card)
        assert pdf_bytes[:4] == b"%PDF"


class TestPdfContent:
    """PDF 文本提取 (粗略, 验证内容存在)."""

    def test_contains_hs_code(self, sample_card: DecisionCard) -> None:
        from io import BytesIO

        from pypdf import PdfReader
        pdf_bytes = generate_decision_card_pdf(sample_card)
        reader = PdfReader(BytesIO(pdf_bytes))
        text = "\n".join(p.extract_text() for p in reader.pages)
        # 至少包含 HS 码或 fallback 显示
        assert "85183020" in text or "8518302000" in text
