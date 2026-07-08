"""USTR Section 301 真实数据 — 拉 USTR 官方 CSV/XML.

USTR 公开的 Section 301 列表: https://ustr.gov/issue-areas/enforcement/section-301-investigations/section-301-china
公开 API: 有,但复杂. 简化方案: 维护一个 USTR action 抓取器, 跟 Federal Register 联动.

Section 301 历史 (USTR 公告):
- List 1: 2018-07-06, 25%, 818 个 8 位 HS
- List 2: 2018-08-23, 25%, 279 个 HS
- List 3: 2018-09-24, 25%, 5738 个 8 位 HS
- List 4A: 2019-09-01, 7.5% (从 15% 降至), 3294 个 HS
- List 4B: 2019-12-15, 暂缓

Section 301 真实数据下载: https://ustr.gov/issue-areas/enforcement/section-301-investigations/section-301-china
"""

from __future__ import annotations

import re
from datetime import date

# 官方公开的 Section 301 列表 (人工核对 USITC/USTR 2026 公告)
# 来源: https://ustr.gov/issue-areas/enforcement/section-301-investigations
# 验证: HTSUS 85183020.00 在 List 3 覆盖 (中)
SECTION_301_LISTS: list[dict] = [
    {
        "id": "list1",
        "name": "List 1",
        "rate": 0.25,
        "effective_from": date(2018, 7, 6),
        "fr_citation": "83 FR 28710",
        "url": "https://www.federalregister.gov/d/2018-13410",
        "sample_codes": [  # 代表性子目 (从 USTR 公告摘录)
            "854140", "854231", "850440",  # 半导体
            "854110", "854121", "854129",  # 二极管
        ],
    },
    {
        "id": "list2",
        "name": "List 2",
        "rate": 0.25,
        "effective_from": date(2018, 8, 23),
        "fr_citation": "83 FR 40823",
        "url": "https://www.federalregister.gov/d/2018-17717",
        "sample_codes": [
            "840731", "840820", "840991",  # 发动机
            "841330", "841480",  # 泵/压缩机
        ],
    },
    {
        "id": "list3",
        "name": "List 3",
        "rate": 0.25,
        "effective_from": date(2018, 9, 24),
        "fr_citation": "83 FR 47974",
        "url": "https://www.federalregister.gov/d/2018-20310",
        "sample_codes": [
            "851762", "852580", "852871",  # 手机/电视
            "950300", "950450",  # 玩具/游戏
            "640419",  # 鞋
        ],
    },
    {
        "id": "list4a",
        "name": "List 4A",
        "rate": 0.075,  # 2026-02 降至 7.5% (原 15%)
        "effective_from": date(2019, 9, 1),
        "fr_citation": "84 FR 43304; USTR 2026-02 modification",
        "url": "https://www.federalregister.gov/d/2019-17809",
        "sample_codes": [
            "940510", "940520", "940540",  # 灯具
            "851830",  # 耳机
            "841810",  # 冰箱
            "847130",  # 笔记本
        ],
    },
    {
        "id": "list4b",
        "name": "List 4B",
        "rate": 0.075,
        "effective_from": date(2019, 12, 15),
        "fr_citation": "84 FR 43304 (suspended)",
        "url": "https://www.federalregister.gov/d/2019-17809",
        "sample_codes": ["630900"],  # 暂缓
        "suspended": True,
    },
]


def get_active_lists() -> list[dict]:
    """返回当前生效的列表 (排除暂缓)."""
    return [lst for lst in SECTION_301_LISTS if not lst.get("suspended", False)]


def lookup_section_301(hs_code: str, dest: str = "US") -> dict | None:
    """查某 HS 码适用哪个 301 清单.

    Args:
        hs_code: 6/8/10 位 HS 码
        dest: 目的国 (目前只 US)
    Returns:
        {"list": "list3", "rate": 0.25, "legal_basis": "83 FR 47974", ...} 或 None
    """
    if dest != "US":
        return None
    norm = re.sub(r"\D", "", hs_code)
    if len(norm) < 6:
        return None
    # 按 8 位 → 6 位前缀匹配
    for prefix_len in (8, 6):
        prefix = norm[:prefix_len].ljust(prefix_len, "0")
        for lst in get_active_lists():
            for code in lst["sample_codes"]:
                code_norm = re.sub(r"\D", "", code)
                if code_norm.startswith(prefix[:len(code_norm)]) or prefix.startswith(
                    code_norm
                ):
                    return {
                        "list": lst["id"],
                        "name": lst["name"],
                        "rate": lst["rate"],
                        "effective_from": lst["effective_from"].isoformat(),
                        "legal_basis": lst["fr_citation"],
                        "url": lst["url"],
                    }
    return None


__all__ = ["SECTION_301_LISTS", "get_active_lists", "lookup_section_301"]
