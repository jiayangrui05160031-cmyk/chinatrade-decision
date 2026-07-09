"""加载美线关税种子数据 (Section 301 / 232 / IEEPA / MFN)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from wto_policy.core.tariff_model import MeasureType, TariffMeasure

_SEED_FILE = Path(__file__).parent / "tariff_us_2026.yaml"


def load_us_tariff_seed() -> list[TariffMeasure]:
    """加载种子数据, 转成 TariffMeasure 列表.

    注意: 同一个 HS 码在多个清单上时, 生成多条 TariffMeasure 记录.
    YAML 字段约定:
        hs_codes (v0.2+)  /  sample_hs_codes (兼容旧版) — HS 前缀列表
    """
    data = yaml.safe_load(_SEED_FILE.read_text(encoding="utf-8"))
    crawled = datetime(2026, 7, 8, tzinfo=UTC)
    measures: list[TariffMeasure] = []

    def _codes(defn: dict) -> list[str]:
        """取 HS 码列表, 兼容新旧字段名."""
        return defn.get("hs_codes") or defn.get("sample_hs_codes") or []

    for list_def in data["section_301"]:
        for hs in _codes(list_def):
            measures.append(
                TariffMeasure(
                    hs_code=hs,  # 6 位, 已对齐
                    origin="CN",
                    destination="US",
                    measure_type=MeasureType.SECTION_301,
                    ad_valorem_rate=list_def["rate"],
                    effective_from=date.fromisoformat(list_def["effective_from"]),
                    legal_basis=list_def["legal_basis"],
                    source_url=list_def["source_url"],
                    crawled_at=crawled,
                )
            )

    for defn in data["section_232"]:
        for hs in _codes(defn):
            measures.append(
                TariffMeasure(
                    hs_code=hs,
                    origin="CN",
                    destination="US",
                    measure_type=MeasureType.SECTION_232,
                    ad_valorem_rate=defn["rate"],
                    effective_from=date.fromisoformat(defn["effective_from"]),
                    legal_basis=defn["legal_basis"],
                    source_url=defn["source_url"],
                    crawled_at=crawled,
                )
            )

    for ieepa in data["ieepa"]:
        for hs in _codes(ieepa):
            measures.append(
                TariffMeasure(
                    hs_code=hs,  # 000000 表示"通配, 见 TariffLookup.find 特殊处理"
                    origin="CN",
                    destination="US",
                    measure_type=MeasureType.IEEPA,
                    ad_valorem_rate=ieepa["rate"],
                    effective_from=date.fromisoformat(ieepa["effective_from"]),
                    legal_basis=ieepa["legal_basis"],
                    source_url=ieepa["source_url"],
                    crawled_at=crawled,
                )
            )

    for m in data["mfn_samples"]:
        measures.append(
            TariffMeasure(
                hs_code=m["hs_code"],
                origin="XX",  # ISO 3166-1 alpha-2 保留 XX = 未知, MFN 适用于所有原产
                destination="US",
                measure_type=MeasureType.MFN,
                ad_valorem_rate=m["rate"],
                effective_from=date(1995, 1, 1),  # 远早于任何 Section 301, 保证常在
                legal_basis="HTSUS General Rate",
                source_url=m["source_url"],
                crawled_at=crawled,
            )
        )

    return measures


__all__ = ["load_us_tariff_seed"]
