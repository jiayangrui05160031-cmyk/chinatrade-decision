"""企业画像.

中国制造业出口企业的基本档案, 用于决策卡个性化推荐.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TradeMode(StrEnum):
    """贸易方式."""

    GENERAL = "general_trade"  # 一般贸易 (海运/空运整柜/拼箱)
    EXPRESS = "express"        # 国际快递 (DHL/FedEx/UPS)
    PARCEL = "small_parcel"    # 小包直邮 (邮政/E-packet)
    OVERSEAS_WAREHOUSE = "overseas_warehouse"  # 海外仓 (B2B 整柜 + 海外分发)


class CompanyProfile(BaseModel):
    """一个出口企业的画像."""

    model_config = ConfigDict(frozen=True)

    name: str
    sector: str = Field(description="行业, 例 '灯具', '消费电子', '服装'")
    annual_export_usd: float = Field(ge=0, description="年出口额, USD")
    main_destinations: list[str] = Field(
        default_factory=list, description="主要目的国 ISO 2-letter"
    )
    trade_mode: TradeMode
    has_aeo: bool = Field(default=False, description="是否 AEO 认证")
    main_hs_codes: list[str] = Field(
        default_factory=list, description="主营 HS 码列表"
    )
    # 可选: 是否能拿到原产证 (FORM A/E/RCEP 等)
    has_preferential_origin: bool = False

    @property
    def is_small(self) -> bool:
        """中小企业判断 (出口额 < 5M USD)."""
        return self.annual_export_usd < 5_000_000


__all__ = ["CompanyProfile", "TradeMode"]
