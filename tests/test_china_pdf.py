"""Tests for ingest/china_pdf.py — 中国海关 PDF 解析器."""

from __future__ import annotations

from pathlib import Path

import pytest

from wto_policy.ingest.china_pdf import (
    ChinaDutyRow,
    download_china_pdfs,
    parse_china_import_duty_pdf,
)

PDF_DIR = Path(__file__).parent.parent / "data" / "raw" / "china_2026"


@pytest.fixture(scope="module")
def pdf_path() -> Path:
    """下载/获取进口税率 PDF (跳过已下载)."""
    download_china_pdfs()
    p = PDF_DIR / "import_duty.pdf"
    if not p.exists():
        pytest.skip(f"PDF 未下载: {p}")
    return p


class TestParseChinaDuty:
    def test_real_pdf(self, pdf_path: Path) -> None:
        rows = parse_china_import_duty_pdf(pdf_path)
        assert len(rows) > 500, f"应至少 500 行, 实际 {len(rows)}"
        # 抽样验证格式
        sample = rows[0]
        assert len(sample.hs_code) >= 8
        assert 0 <= sample.mfn_rate <= 200
        assert 0 <= sample.provisional_rate <= 200
        assert sample.description_zh, "描述不能为空"

    def test_real_contains_fish(self, pdf_path: Path) -> None:
        """第 2 行是冻大西洋鲑鱼 (官方数据)."""
        rows = parse_china_import_duty_pdf(pdf_path)
        fish = [r for r in rows if "鲑鱼" in r.description_zh]
        assert len(fish) > 0, "应含鲑鱼 (03021410)"
        # 看 03021410
        for r in fish:
            if r.hs_code == "03021410":
                assert r.mfn_rate == 10.0
                assert r.provisional_rate == 7.0

    def test_is_ex_flag(self, pdf_path: Path) -> None:
        """ex 标记正确."""
        rows = parse_china_import_duty_pdf(pdf_path)
        ex_rows = [r for r in rows if r.is_ex]
        assert len(ex_rows) > 0, "应有 ex 子目"

    def test_schema(self) -> None:
        """ChinaDutyRow 字段验证."""
        r = ChinaDutyRow(
            hs_code="01061211",
            description_zh="改良种用鲸",
            mfn_rate=10.0,
            provisional_rate=0.0,
        )
        assert r.hs_code == "01061211"
        assert r.mfn_rate == 10.0
        assert r.provisional_rate == 0.0
        assert r.is_ex is False  # default
