"""TariffMeasure / HsCode / Country 基础数据模型.

所有数据模型都是 pydantic BaseModel, 严格类型, JSON-friendly.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Country(BaseModel):
    """ISO 3166-1 alpha-2 国家代码 + 显示名."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    name_zh: str
    name_en: str

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class HsCode(BaseModel):
    """HS 编码(支持 6 / 8 / 10 位三种粒度).

    国际通用 6 位 + 中国/美国附加位.
    6 位 = 章节 + 子目(HS 锚点)
    8 位 = 国别附加(中国 / HTSUS 统计位)
    10 位 = 申报位(企业报关实际使用)
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(description="完整 HS 编码", min_length=6, max_length=10)
    level: int = Field(description="粒度, 6/8/10", ge=6, le=10)
    parent_code: str | None = Field(default=None, description="父级编码")
    chapter: str = Field(min_length=2, max_length=2, description="HS 章,2 位")
    description_zh: str
    description_en: str
    source: str = Field(description="数据源标识, 例: 'usitc-htsus-2026-rev3'")

    @field_validator("code")
    @classmethod
    def _digits_only(cls, v: str) -> str:
        if not v.isdigit():
            msg = f"HS code must be digits only, got {v!r}"
            raise ValueError(msg)
        return v

    @field_validator("level")
    @classmethod
    def _level_matches(cls, v: int, info) -> int:  # type: ignore[no-untyped-def]
        code: str = info.data.get("code", "")
        if code and len(code) != v:
            msg = f"level={v} but code length={len(code)} ({code})"
            raise ValueError(msg)
        return v


class MeasureType(StrEnum):
    """关税措施类型."""

    MFN = "mfn"  # 最惠国(普通)
    PREFERENTIAL = "preferential"  # 自贸协定优惠
    ANTI_DUMPING = "anti_dumping"  # 反倾销
    COUNTERVAILING = "countervailing"  # 反补贴
    SAFEGUARD = "safeguard"  # 保障措施
    SECTION_301 = "section_301"  # 美国 301 加征
    SECTION_232 = "section_232"  # 美国 232(国家安全)
    IEEPA = "ieepa"  # 美国 IEEPA 芬太尼等
    VAT = "vat"  # 增值税(消费税)


class TariffMeasure(BaseModel):
    """一条关税措施记录.

    一条记录代表"某 HS 码 + 某原产国 + 某目的国 + 某措施类型 + 某税率"
    多个 TariffMeasure 共同构成对一个货物的完整税则视图.
    """

    model_config = ConfigDict(frozen=True)

    hs_code: str = Field(min_length=6, max_length=10)
    origin: str = Field(min_length=2, max_length=2, description="ISO alpha-2")
    destination: str = Field(min_length=2, max_length=2, description="ISO alpha-2")
    measure_type: MeasureType
    ad_valorem_rate: float | None = Field(
        default=None, ge=0, le=10, description="从价税率, 例 0.25 = 25%"
    )
    specific_rate: float | None = Field(
        default=None, ge=0, description="从量税率, 例 0.05 美元/件"
    )
    specific_unit: str | None = Field(default=None, description="从量单位, 例 'each'")
    effective_from: date
    effective_to: date | None = None
    legal_basis: str | None = Field(default=None, description="法规依据, 例 'Section 301 List 4A'")
    source_url: str
    crawled_at: datetime

    @field_validator("ad_valorem_rate", "specific_rate")
    @classmethod
    def _no_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            msg = f"rate cannot be negative: {v}"
            raise ValueError(msg)
        return v


__all__ = ["Country", "HsCode", "MeasureType", "TariffMeasure"]
