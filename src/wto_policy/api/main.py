"""FastAPI 接口 — POST /api/decision-card."""

from __future__ import annotations

from datetime import date

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from wto_policy.core.company_profile import CompanyProfile, TradeMode
from wto_policy.core.decision_card import DecisionCard
from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.data.seed import load_us_tariff_seed

# 全局 lookup (MVP 阶段用种子; 真实场景用 update.py 加载的 cache)
_LOOKUP = TariffLookup(load_us_tariff_seed())

app = FastAPI(
    title="WTO Policy Decision Support API",
    description=(
        "中国制造业出口企业决策支持: 输入 HS 码 × 目的国 × 货值, "
        "返回结构化决策卡 (关税 / 风险 / 政策 / 建议)"
    ),
    version="0.1.0",
    contact={"name": "jiaya", "url": "https://github.com/jiayangrui05160031-cmyk/wto-policy-support"},
    license_info={"name": "MIT (含非法律意见免责声明)"},
)


class CompanyProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "default"
    sector: str = "default"
    annual_export_usd: float = Field(default=0, ge=0)
    main_destinations: list[str] = Field(default_factory=lambda: ["US"])
    trade_mode: TradeMode = TradeMode.GENERAL
    has_aeo: bool = False
    main_hs_codes: list[str] = Field(default_factory=list)
    has_preferential_origin: bool = False


class DecisionCardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hs_code: str = Field(min_length=6, max_length=12, examples=["9405408000"])
    cif_value_usd: float = Field(gt=0, examples=[17200.0])
    quantity: int = Field(default=1, ge=1, examples=[1000])
    origin: str = Field(default="CN", min_length=2, max_length=2)
    destination: str = Field(default="US", min_length=2, max_length=2)
    on: date | None = Field(default=None, description="生效日期, 默认今天")
    profile: CompanyProfileIn = Field(default_factory=CompanyProfileIn)


@app.get("/")
def root() -> dict:
    return {
        "name": "WTO Policy Decision Support API",
        "version": "0.1.0",
        "disclaimer": (
            "本 API 仅供研究/学习/决策参考, 不构成法律/税务/报关意见. "
            "具体贸易活动请以官方海关 + 报关行 + 律师解释为准."
        ),
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "tariff_measures": len(_LOOKUP._measures)}


@app.post("/api/decision-card", response_model=DecisionCard)
def decision_card(req: DecisionCardRequest) -> DecisionCard:
    """生成一张决策卡.

    输入: HS 编码 + CIF 货值 + 数量 + 企业画像
    输出: DecisionCard (含关税明细、风险、政策警报、建议)
    """
    try:
        profile = CompanyProfile(
            name=req.profile.name,
            sector=req.profile.sector,
            annual_export_usd=req.profile.annual_export_usd,
            main_destinations=req.profile.main_destinations,
            trade_mode=req.profile.trade_mode,
            has_aeo=req.profile.has_aeo,
            main_hs_codes=req.profile.main_hs_codes,
            has_preferential_origin=req.profile.has_preferential_origin,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid profile: {e}") from e

    try:
        return DecisionCard.build(
            hs_code=req.hs_code,
            cif_value_usd=req.cif_value_usd,
            quantity=req.quantity,
            origin=req.origin,
            destination=req.destination,
            on=req.on,
            profile=profile,
            lookup=_LOOKUP,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decision card build failed: {e}") from e


def run() -> None:
    """CLI 入口: wto-api."""
    uvicorn.run("wto_policy.api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run()
