"""WTO Policy Support — 抓取层.

每个子模块负责一类数据源的抓取、解析、校验。
所有抓取应:
- 支持离线 VCR fixture (tests/fixtures/vcr/)
- 输出 pydantic 模型,而不是裸 dict
- 记录 source_url + crawled_at
"""

from __future__ import annotations

__all__ = [
    "hs_code",
    "policy_news",
    "tariff_section232",
    "tariff_us",
    "tariff_ustr301",
    "wto_disputes",
]
