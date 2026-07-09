"""关税计算引擎 (美线).

输入: (hs_code, origin, destination, unit_value_usd, on_date, lookup)
输出: TariffBreakdown (MFN, Section 301, 232, IEEPA, 总计)

计算规则:
- MFN: 适用所有原产 (origin 通配)
- Section 301: 适用中国原产 (CN only)
- Section 232: 适用中国原产
- IEEPA: 适用中国原产
- 所有税率都是 **叠加** 的 (例 MFN 3.4% + 301 7.5% = 10.9%)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.core.tariff_model import MeasureType, TariffMeasure


class BreakdownLine(BaseModel):
    """一行关税明细."""

    model_config = ConfigDict(frozen=True)

    measure_type: MeasureType
    rate: float = Field(description="实际从价税率, 0.075 = 7.5%")
    duty_amount: float = Field(description="这一项的金额, USD")
    legal_basis: str | None
    source_url: str


class TariffBreakdown(BaseModel):
    """完整关税明细."""

    model_config = ConfigDict(frozen=True)

    hs_code: str
    origin: str
    destination: str
    cif_value_usd: float = Field(description="CIF 价值 (货值+运费+保险), USD")
    on_date: date

    mfn: float = Field(default=0.0, description="MFN 普通税率, USD")
    section_301: float = Field(default=0.0, description="Section 301 加征, USD")
    section_232: float = Field(default=0.0, description="Section 232 加征, USD")
    ieepa: float = Field(default=0.0, description="IEEPA 芬太尼税, USD")
    other: float = Field(default=0.0, description="其他 (反倾/反补/保障), USD")
    total_duty: float = Field(default=0.0, description="总关税, USD")
    effective_rate: float = Field(default=0.0, description="综合实际税率")

    lines: list[BreakdownLine] = Field(default_factory=list)

    @classmethod
    def from_measures(
        cls,
        *,
        hs_code: str,
        origin: str,
        destination: str,
        cif_value_usd: float,
        on_date: date,
        measures: list[TariffMeasure],
    ) -> Self:
        lines: list[BreakdownLine] = []
        mfn = s301 = s232 = ieepa = other = 0.0
        for m in measures:
            if m.ad_valorem_rate is None:
                continue
            amount = round(cif_value_usd * m.ad_valorem_rate, 2)
            line = BreakdownLine(
                measure_type=m.measure_type,
                rate=m.ad_valorem_rate,
                duty_amount=amount,
                legal_basis=m.legal_basis,
                source_url=m.source_url,
            )
            lines.append(line)
            match m.measure_type:
                case MeasureType.MFN:
                    mfn += amount
                case MeasureType.SECTION_301:
                    s301 += amount
                case MeasureType.SECTION_232:
                    s232 += amount
                case MeasureType.IEEPA:
                    ieepa += amount
                case _:
                    other += amount
        total = round(mfn + s301 + s232 + ieepa + other, 2)
        eff = total / cif_value_usd if cif_value_usd > 0 else 0.0
        return cls(
            hs_code=hs_code,
            origin=origin,
            destination=destination,
            cif_value_usd=cif_value_usd,
            on_date=on_date,
            mfn=round(mfn, 2),
            section_301=round(s301, 2),
            section_232=round(s232, 2),
            ieepa=round(ieepa, 2),
            other=round(other, 2),
            total_duty=total,
            effective_rate=round(eff, 4),
            lines=lines,
        )


def calculate_tariff(
    *,
    hs_code: str,
    cif_value_usd: float,
    origin: str = "CN",
    destination: str = "US",
    on: date | None = None,
    lookup: TariffLookup,
) -> TariffBreakdown:
    """计算总关税. 一次性返回明细.

    例:
        breakdown = calculate_tariff(
            hs_code="9405408000",
            cif_value_usd=15000.0,  # 1000 个 LED 灯, FOB 15 + 运费
            lookup=lookup,
        )
        print(f"总税: ${breakdown.total_duty}")
        print(f"实际税率: {breakdown.effective_rate:.1%}")
    """
    on_date = on or date.today()
    measures = lookup.find(
        hs_code=hs_code, origin=origin, destination=destination, on=on_date
    )

    # v0.2: 注入云端真实 MFN (HTSUS CSV 读到的 General Rate)
    # 优先级: 真 MFN > 种子 MFN
    # v0.2: 注入云端真实 MFN (HTSUS CSV 读到的 General Rate)
    # 优先级: 真 MFN > 种子 MFN
    real_mfn = lookup.get_mfn(hs_code)
    if real_mfn is not None:
        # 去掉种子里 MFN 类型的旧记录
        measures = [m for m in measures if m.measure_type != MeasureType.MFN]
        # 加一条真 MFN 记录
        real_measure = TariffMeasure(
            hs_code=hs_code,
            origin="XX",
            destination=destination,
            measure_type=MeasureType.MFN,
            ad_valorem_rate=real_mfn,
            effective_from=date(1995, 1, 1),  # 远早, 永远生效
            legal_basis="HTSUS 2026 Rev 2 General Rate of Duty (usitc.gov)",
            source_url="https://hts.usitc.gov/",
            crawled_at=datetime.now(UTC),
        )
        measures.append(real_measure)

    return TariffBreakdown.from_measures(
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        cif_value_usd=cif_value_usd,
        on_date=on_date,
        measures=measures,
    )


__all__ = ["BreakdownLine", "TariffBreakdown", "calculate_tariff"]
