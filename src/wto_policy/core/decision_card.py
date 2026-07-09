"""决策卡 — 装配器.

输入: (hs_code, origin, destination, cif_value_usd, on_date, company_profile)
输出: DecisionCard

内容:
- 总税负 + 分类
- 实际税率
- 风险提示 (例: HS 码在 Section 301 清单上)
- 政策警报 (例: 即将到期/已生效)
- 行动建议 (例: 申请 Section 301 排除, 申请 FORM A)
- 数据来源链接
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from wto_policy.core.company_profile import CompanyProfile, TradeMode
from wto_policy.core.tariff_calc import TariffBreakdown, calculate_tariff
from wto_policy.core.tariff_lookup import TariffLookup


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Risk(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: RiskLevel
    code: str
    message_zh: str
    message_en: str
    legal_basis: str | None = None


class PolicyAlert(BaseModel):
    """政策警报 — 政策变化, 即将到期, 排除窗口等."""

    model_config = ConfigDict(frozen=True)

    code: str
    severity: RiskLevel
    message_zh: str
    message_en: str
    source_url: str | None = None


class Suggestion(BaseModel):
    """行动建议."""

    model_config = ConfigDict(frozen=True)

    priority: int = Field(ge=1, le=5, description="1=最高优先级")
    code: str
    message_zh: str
    message_en: str
    action_url: str | None = None


class DecisionCard(BaseModel):
    """一张完整的决策卡."""

    model_config = ConfigDict(frozen=True)

    # 元数据
    hs_code: str
    origin: str
    destination: str
    cif_value_usd: float
    cif_unit_value_usd: float
    quantity: int
    on_date: date
    generated_at: date  # 决策卡生成日
    profile_name: str

    # 关税计算
    breakdown: TariffBreakdown
    total_tax: float  # = breakdown.total_duty
    net_landed_cost: float  # CIF + 总税
    per_unit_tax: float
    effective_rate: float  # = breakdown.effective_rate

    # 智能分析
    risks: list[Risk] = Field(default_factory=list)
    policy_alerts: list[PolicyAlert] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)

    # 实时性 (数据截至时间)
    data_freshness: dict = Field(
        default_factory=dict,
        description="数据时效: {source: '2026-07-08T12:00:00Z', age_minutes: 45}",
    )

    # 溯源
    sources: list[str] = Field(default_factory=list)

    @classmethod
    def build(
        cls,
        *,
        hs_code: str,
        cif_value_usd: float,
        quantity: int = 1,
        origin: str = "CN",
        destination: str = "US",
        on: date | None = None,
        profile: CompanyProfile,
        lookup: TariffLookup,
    ) -> Self:
        on_date = on or date.today()
        breakdown = calculate_tariff(
            hs_code=hs_code,
            cif_value_usd=cif_value_usd,
            origin=origin,
            destination=destination,
            on=on_date,
            lookup=lookup,
        )

        risks: list[Risk] = []
        alerts: list[PolicyAlert] = []
        suggestions: list[Suggestion] = []
        sources: set[str] = set()

        # ---- 风险分析 ----
        if breakdown.section_301 > 0:
            risks.append(
                Risk(
                    level=RiskLevel.HIGH,
                    code="SECTION_301_APPLIES",
                    message_zh=(
                        f"该 HS 码适用美国 Section 301 加征, "
                        f"金额 ${breakdown.section_301:,.2f} "
                        f"(实约 {breakdown.section_301 / cif_value_usd:.1%})"
                    ),
                    message_en=(
                        f"Subject to U.S. Section 301 additional tariff: "
                        f"${breakdown.section_301:,.2f}"
                    ),
                )
            )

        if breakdown.ieepa > 0:
            risks.append(
                Risk(
                    level=RiskLevel.MEDIUM,
                    code="IEEPA_FENTANYL",
                    message_zh=(
                        f"该 HS 码被 IEEPA 芬太尼税覆盖, 金额 ${breakdown.ieepa:,.2f} (10%)"
                    ),
                    message_en=(
                        f"Subject to IEEPA fentanyl tariff: ${breakdown.ieepa:,.2f} (10%)"
                    ),
                )
            )

        if breakdown.section_232 > 0:
            risks.append(
                Risk(
                    level=RiskLevel.CRITICAL,
                    code="SECTION_232",
                    message_zh=(
                        f"钢铁/铝 Section 232 适用, 金额 ${breakdown.section_232:,.2f} (25%)"
                    ),
                    message_en=(
                        f"Subject to Section 232 steel/aluminum: ${breakdown.section_232:,.2f}"
                    ),
                )
            )

        # ---- 政策警报 ----
        if breakdown.section_301 > 0:
            alerts.append(
                PolicyAlert(
                    code="USTR_301_LIST4A_75",
                    severity=RiskLevel.HIGH,
                    message_zh=(
                        "List 4A 当前税率 7.5% (2026-02 调降前为 15%)。"
                        "USTR 2025-2026 期间政策可能再调整, 关注联邦公告"
                    ),
                    message_en=(
                        "List 4A is currently 7.5% (down from 15% in Feb 2026). "
                        "USTR may further adjust; check Federal Register"
                    ),
                    source_url="https://ustr.gov/issue-areas/enforcement/section-301-investigations",
                )
            )
        if breakdown.ieepa > 0:
            alerts.append(
                PolicyAlert(
                    code="IEEPA_FENTANYL_LITIGATION",
                    severity=RiskLevel.MEDIUM,
                    message_zh=(
                        "IEEPA 芬太尼税面临法院挑战 (V.O.S. Selections v. Trump), "
                        "退税可能, 但已征税款不退"
                    ),
                    message_en=(
                        "IEEPA fentanyl tariff under court challenge "
                        "(V.O.S. Selections v. Trump); refunds possible for future entries"
                    ),
                    source_url="https://www.federalregister.gov/d/2025-02044",
                )
            )

        # ---- 行动建议 (按优先级) ----
        if breakdown.section_301 > 0 and profile.is_small and profile.has_aeo:
            suggestions.append(
                Suggestion(
                    priority=2,
                    code="AEQ_EXCLUSION_TRACK",
                    message_zh=(
                        "你是 AEO 认证企业: 关注 USTR Section 301 排除申请窗口, "
                        "可申请单类产品排除"
                    ),
                    message_en=(
                        "AEO-certified: monitor USTR Section 301 exclusion windows "
                        "for product-specific relief"
                    ),
                    action_url="https://ustr.gov/issue-areas/enforcement/section-301-investigations",
                )
            )

        if breakdown.section_301 > 0 and not profile.has_preferential_origin:
            suggestions.append(
                Suggestion(
                    priority=3,
                    code="CHECK_FTA",
                    message_zh=(
                        "中美无 FTA, 但若你有第三国加工 (例越南/墨西哥), "
                        "可考虑原产地优化; 若在 RCEP/CPTPP 成员国, 申请 FORM RCEP"
                    ),
                    message_en=(
                        "No US-China FTA, but consider origin optimization via "
                        "third-country processing; if in RCEP/CPTPP country, "
                        "apply for FORM RCEP"
                    ),
                )
            )

        if profile.trade_mode == TradeMode.EXPRESS and breakdown.total_duty > 0:
            suggestions.append(
                Suggestion(
                    priority=1,
                    code="BULK_VS_EXPRESS",
                    message_zh=(
                        "走国际快递每单都有税单成本 + 美国邮政/快递商加收服务费。"
                        "量大的话, 走海运一般贸易 + 当地清关可能省 5-8%"
                    ),
                    message_en=(
                        "Express shipping has per-parcel duty processing fees. "
                        "For volume, consider sea freight + local customs broker."
                    ),
                )
            )

        if profile.is_small and breakdown.effective_rate > 0.20:
            suggestions.append(
                Suggestion(
                    priority=1,
                    code="HIGH_TARIFF_EXPOSURE",
                    message_zh=(
                        f"综合实际税率 {breakdown.effective_rate:.1%}, "
                        "对中小企业是巨大负担。"
                        "考虑: (a) 提高售价转嫁; (b) 调整 HS 归类; "
                        "(c) 转第三国生产; (d) 申请 Section 301 排除"
                    ),
                    message_en=(
                        f"Effective rate {breakdown.effective_rate:.1%} is "
                        "significant for SMEs. Consider: (a) price pass-through; "
                        "(b) HS reclassification; (c) third-country manufacturing; "
                        "(d) Section 301 exclusion"
                    ),
                )
            )

        # ---- 收集来源 ----
        for line in breakdown.lines:
            sources.add(line.source_url)

        # ---- 计算最终值 ----
        net_landed = round(cif_value_usd + breakdown.total_duty, 2)
        per_unit = round(breakdown.total_duty / quantity, 4) if quantity > 0 else 0.0
        cif_unit = round(cif_value_usd / quantity, 4) if quantity > 0 else 0.0

        return cls(
            hs_code=hs_code,
            origin=origin,
            destination=destination,
            cif_value_usd=round(cif_value_usd, 2),
            cif_unit_value_usd=cif_unit,
            quantity=quantity,
            on_date=on_date,
            generated_at=date.today(),
            profile_name=profile.name,
            breakdown=breakdown,
            total_tax=breakdown.total_duty,
            net_landed_cost=net_landed,
            per_unit_tax=per_unit,
            effective_rate=breakdown.effective_rate,
            risks=risks,
            policy_alerts=alerts,
            suggestions=suggestions,
            sources=sorted(sources),
        )


__all__ = [
    "DecisionCard",
    "PolicyAlert",
    "Risk",
    "RiskLevel",
    "Suggestion",
    ]
