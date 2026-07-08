"""Agent 工具 — Agent 可调用的能力.

工具函数遵循 JSON Schema 描述, 与 OpenAI/MiniMax function-calling 协议一致.
每个工具有:
- name: 工具名 (LLM 调用用)
- description: 工具说明 (LLM 决策用)
- parameters: JSON Schema (LLM 拼参数用)
- handler(args) -> str: 实际执行, 返回 JSON 字符串作为 tool result
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wto_policy.agent.policy_fetcher import search_policy, to_dict as policy_to_dict
from wto_policy.core.company_profile import CompanyProfile, TradeMode
from wto_policy.core.decision_card import DecisionCard
from wto_policy.core.hs_resolver import HsResolver
from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.data.seed import load_sample, load_us_tariff_seed


# ============ Tool 1: HS 编码搜索 ============

def search_hs_codes(
    query: str,
    *,
    lang: str = "zh",
    limit: int = 5,
    resolver: HsResolver | None = None,
) -> list[dict[str, Any]]:
    """Agent 工具: 按关键词/描述搜索 HS 编码.

    Args:
        query: 中文/英文产品描述
        lang: 搜索语言 zh/en
        limit: 返回数量
    """
    r = resolver or HsResolver.from_list(load_sample())
    results = r.search(query, lang=lang, limit=limit)
    return [
        {
            "code": h.code,
            "level": h.level,
            "chapter": h.chapter,
            "description_zh": h.description_zh,
            "description_en": h.description_en,
        }
        for h in results
    ]


# ============ Tool 2: 关税计算 ============

def lookup_tariff(
    hs_code: str,
    cif_value_usd: float,
    *,
    origin: str = "CN",
    destination: str = "US",
    lookup: TariffLookup | None = None,
) -> dict[str, Any]:
    """Agent 工具: 查某 HS 码的关税.

    返回结构:
    {
        "mfn": 0.034, "section_301": 0.075, "section_232": 0.0, "ieepa": 0.10,
        "total_rate": 0.209, "amount_usd": {mfn, s301, s232, ieepa, total},
        "legal_basis": [...]
    }
    """
    lk = lookup or TariffLookup(load_us_tariff_seed())
    bd = DecisionCard.build(
        hs_code=hs_code,
        cif_value_usd=cif_value_usd,
        profile=CompanyProfile(
            name="agent", sector="default", annual_export_usd=0,
            main_destinations=[destination], trade_mode=TradeMode.GENERAL,
        ),
        lookup=lk,
    )
    return {
        "hs_code": bd.hs_code,
        "destination": bd.destination,
        "cif_value_usd": bd.cif_value_usd,
        "rates": {
            "mfn": bd.breakdown.mfn / cif_value_usd if cif_value_usd else 0,
            "section_301": bd.breakdown.section_301 / cif_value_usd if cif_value_usd else 0,
            "section_232": bd.breakdown.section_232 / cif_value_usd if cif_value_usd else 0,
            "ieepa": bd.breakdown.ieepa / cif_value_usd if cif_value_usd else 0,
        },
        "amount_usd": {
            "mfn": bd.breakdown.mfn,
            "section_301": bd.breakdown.section_301,
            "section_232": bd.breakdown.section_232,
            "ieepa": bd.breakdown.ieepa,
            "total": bd.total_tax,
        },
        "effective_rate": bd.effective_rate,
        "lines": [
            {
                "type": l.measure_type.value,
                "rate": l.rate,
                "amount": l.duty_amount,
                "legal_basis": l.legal_basis,
            }
            for l in bd.breakdown.lines
        ],
    }


# ============ Tool 3: 决策卡生成 ============

def generate_decision_card(
    hs_code: str,
    cif_value_usd: float,
    quantity: int,
    company_name: str = "企业",
    sector: str = "default",
    annual_export_usd: float = 0,
    trade_mode: str = "general_trade",
    destination: str = "US",
    lookup: TariffLookup | None = None,
) -> dict[str, Any]:
    """Agent 工具: 生成完整决策卡 (含风险/政策/建议)."""
    lk = lookup or TariffLookup(load_us_tariff_seed())
    profile = CompanyProfile(
        name=company_name, sector=sector, annual_export_usd=annual_export_usd,
        main_destinations=[destination], trade_mode=TradeMode(trade_mode),
    )
    card = DecisionCard.build(
        hs_code=hs_code, cif_value_usd=cif_value_usd, quantity=quantity,
        destination=destination, profile=profile, lookup=lk,
    )
    return card.model_dump(mode="json")


# ============ Tool 4: 实时政策搜索 ============

def search_recent_policy(
    query: str,
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 5,
) -> list[dict[str, Any]]:
    """Agent 工具: 实时搜索 USTR / Federal Register / 商务部 的最新政策公告.

    Args:
        query: 关键词, 例 'section 301' / 'list 4A' / 'ieepa fentanyl'
        sources: 子集 ['ustr', 'federal_register', 'mofcom']
        limit_per_source: 每源最多几条
    """
    items = search_policy(query, sources=sources, limit_per_source=limit_per_source)
    return policy_to_dict(items)


# ============ 工具注册表 ============

@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., Any]


def get_tool_schemas() -> list[dict[str, Any]]:
    """返回 OpenAI/MiniMax 兼容的 tools 列表."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _TOOL_REGISTRY.values()
    ]


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """执行工具, 返回 JSON string (作为 tool result)."""
    if name not in _TOOL_REGISTRY:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        result = _TOOL_REGISTRY[name].handler(**arguments)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


_TOOL_REGISTRY: dict[str, ToolDef] = {
    "search_hs_codes": ToolDef(
        name="search_hs_codes",
        description=(
            "按产品描述搜索 HS 编码候选. 输入中文或英文产品名/描述, "
            "返回匹配的 HS 编码列表 (6/8/10 位) 及中英文说明. "
            "当用户用自然语言描述产品但不直接给 HS 码时, 调此工具."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "产品描述, 例 '蓝牙耳机' 或 'led lamp'"},
                "lang": {"type": "string", "enum": ["zh", "en"], "description": "搜索语言, 默认 zh"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "返回数量"},
            },
            "required": ["query"],
        },
        handler=search_hs_codes,
    ),
    "lookup_tariff": ToolDef(
        name="lookup_tariff",
        description=(
            "查某 HS 码从中国出口到某目的国的关税明细. "
            "返回 MFN / Section 301 / Section 232 / IEEPA 各项税率和金额, "
            "以及法规依据. 已知 HS 码和 CIF 货值时调此工具."
        ),
        parameters={
            "type": "object",
            "properties": {
                "hs_code": {"type": "string", "description": "HS 编码 6-10 位"},
                "cif_value_usd": {"type": "number", "description": "CIF 货值 (USD)"},
                "destination": {"type": "string", "description": "目的国 ISO 2-letter, 默认 US"},
            },
            "required": ["hs_code", "cif_value_usd"],
        },
        handler=lookup_tariff,
    ),
    "generate_decision_card": ToolDef(
        name="generate_decision_card",
        description=(
            "生成完整决策卡. 需要: HS 码 + CIF + 数量 + 简单的企业画像. "
            "返回结构化卡片: 关税明细 + 风险 + 政策警报 + 行动建议 + 来源. "
            "用户最终想要'决策建议'时调此工具."
        ),
        parameters={
            "type": "object",
            "properties": {
                "hs_code": {"type": "string"},
                "cif_value_usd": {"type": "number"},
                "quantity": {"type": "integer", "minimum": 1},
                "company_name": {"type": "string", "description": "企业名, 默认 '企业'"},
                "sector": {"type": "string", "description": "行业, 例 '灯具' '消费电子'"},
                "annual_export_usd": {"type": "number", "description": "年出口额 (USD)"},
                "trade_mode": {
                    "type": "string",
                    "enum": ["general_trade", "express", "small_parcel", "overseas_warehouse"],
                    "description": "贸易方式",
                },
                "destination": {"type": "string"},
            },
            "required": ["hs_code", "cif_value_usd", "quantity"],
        },
        handler=generate_decision_card,
    ),
    "search_recent_policy": ToolDef(
        name="search_recent_policy",
        description=(
            "实时搜索最新政策公告 (USTR / Federal Register / 商务部). "
            "用户问 '现在 301 怎么样' / '最近有什么新政' / 'Section 232 状态' 时调此工具. "
            "返回近期公告列表 (标题 + URL + 摘要 + 发布日期)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词, 例 'section 301 list 4A'"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["ustr", "federal_register", "mofcom"]},
                    "description": "数据源, 默认 ustr + federal_register",
                },
                "limit_per_source": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
        handler=search_recent_policy,
    ),
}


__all__ = [
    "ToolDef",
    "get_tool_schemas",
    "call_tool",
    "search_hs_codes",
    "lookup_tariff",
    "generate_decision_card",
    "search_recent_policy",
]
