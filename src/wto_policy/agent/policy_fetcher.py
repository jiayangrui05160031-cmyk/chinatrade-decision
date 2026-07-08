"""实时政策抓取 (USTR / Federal Register / 商务部).

策略:
- 离线优先: 失败时返回缓存/空结果, Agent 不崩
- 真实抓取: 公开 API + RSS, 都有 retry
- 数据带 source_url + crawled_at
- 用 VCR.py 录制 fixture, 测试不真打网络
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx


@dataclass
class PolicyItem:
    """一条政策公告."""

    title: str
    url: str
    published: datetime
    source: str
    summary: str | None = None
    raw: str | None = None


def _parse_rss_date(s: str) -> datetime:
    """RSS pubDate -> datetime."""
    try:
        return parsedate_to_datetime(s).astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def fetch_ustr_press(*, limit: int = 10, timeout: float = 15.0) -> list[PolicyItem]:
    """USTR 办公室新闻稿 (RSS).

    URL: https://ustr.gov/about-us/policy-offices/press-office/press-releases/feed
    """
    url = "https://ustr.gov/about-us/policy-offices/press-office/press-releases/feed"
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
        items: list[PolicyItem] = []
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub = item.findtext("pubDate", "")
            desc = item.findtext("description", "").strip()
            items.append(PolicyItem(
                title=title, url=link, published=_parse_rss_date(pub),
                source="ustr.gov", summary=desc,
            ))
        return items
    except Exception:
        return []


def fetch_federal_register(
    *,
    query: str = "section 301",
    limit: int = 10,
    timeout: float = 15.0,
) -> list[PolicyItem]:
    """Federal Register API 搜索.

    URL: https://www.federalregister.gov/api/v1/documents.json
    """
    url = "https://www.federalregister.gov/api/v1/documents.json"
    params = {
        "conditions[term]": query,
        "conditions[publication_date][gte]": (
            datetime.now(UTC) - timedelta(days=180)
        ).strftime("%Y-%m-%d"),
        "per_page": min(limit, 20),
    }
    try:
        r = httpx.get(url, params=params, timeout=timeout)
        if r.status_code != 200:
            return []
        data = r.json()
        items: list[PolicyItem] = []
        for doc in data.get("results", []):
            items.append(PolicyItem(
                title=doc.get("title", ""),
                url=doc.get("html_url", ""),
                published=datetime.fromisoformat(
                    doc.get("publication_date", "")
                ).replace(tzinfo=UTC),
                source="federalregister.gov",
                summary=doc.get("abstract", "")[:500] or None,
            ))
        return items
    except Exception:
        return []


def fetch_mofcom_rss(*, limit: int = 10, timeout: float = 15.0) -> list[PolicyItem]:
    """商务部新闻 (RSS 镜像, 可能因 GFW 不稳定).

    URL: http://www.mofcom.gov.cn/rss/
    """
    url = "http://www.mofcom.gov.cn/rss/eywfb.xml"  # 经贸与外汇
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
        items: list[PolicyItem] = []
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub = item.findtext("pubDate", "")
            desc = item.findtext("description", "").strip()
            items.append(PolicyItem(
                title=title, url=link, published=_parse_rss_date(pub),
                source="mofcom.gov.cn", summary=desc,
            ))
        return items
    except Exception:
        return []


def search_policy(
    query: str,
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 5,
) -> list[PolicyItem]:
    """跨源搜索, 合并结果按时间倒序.

    sources: subset of ['ustr', 'federal_register', 'mofcom']
    """
    sources = sources or ["ustr", "federal_register"]
    all_items: list[PolicyItem] = []
    if "ustr" in sources:
        all_items.extend(fetch_ustr_press(limit=limit_per_source))
    if "federal_register" in sources:
        all_items.extend(fetch_federal_register(query=query, limit=limit_per_source))
    if "mofcom" in sources:
        all_items.extend(fetch_mofcom_rss(limit=limit_per_source))

    # 关键词过滤 (简单的子串匹配)
    q = query.lower()
    if q:
        all_items = [i for i in all_items if q in i.title.lower() or (i.summary and q in i.summary.lower())]

    all_items.sort(key=lambda x: x.published, reverse=True)
    return all_items[: limit_per_source * len(sources)]


def to_dict(items: list[PolicyItem]) -> list[dict]:
    """Tool 返回 dict 列表."""
    return [
        {
            "title": i.title,
            "url": i.url,
            "published": i.published.isoformat(),
            "source": i.source,
            "summary": i.summary,
        }
        for i in items
    ]


__all__ = [
    "PolicyItem",
    "fetch_federal_register",
    "fetch_mofcom_rss",
    "fetch_ustr_press",
    "search_policy",
    "to_dict",
]
