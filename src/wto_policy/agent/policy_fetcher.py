"""实时政策抓取 (USTR / Federal Register / 商务部).

策略:
- 离线优先: 失败时返回缓存/空结果, Agent 不崩
- 真实抓取: Federal Register API + USTR/商务部官方列表页
- 单源失败返回空列表, 不阻塞其他来源
- 数据带官方 URL 与发布时间
- 用 VCR.py 录制 fixture, 测试不真打网络
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


@dataclass
class PolicyItem:
    """一条政策公告."""

    title: str
    url: str
    published: datetime
    source: str
    summary: str | None = None
    raw: str | None = None


def _parse_ustr_page(html: str, *, base_url: str, limit: int) -> list[PolicyItem]:
    """Parse the official USTR press-release listing."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[PolicyItem] = []
    for row in soup.select(".views-row"):
        time_element = row.select_one("time[datetime]")
        link = row.select_one('a[href*="/press-releases/"]')
        if time_element is None or link is None:
            continue
        try:
            published = datetime.fromisoformat(
                time_element.get("datetime", "").replace("Z", "+00:00")
            ).astimezone(UTC)
        except ValueError:
            continue
        title = link.get_text(" ", strip=True)
        href = link.get("href", "")
        if not title or not href:
            continue
        items.append(PolicyItem(
            title=title,
            url=urljoin(base_url, href),
            published=published,
            source="ustr",
        ))
        if len(items) >= limit:
            break
    return items


def _parse_mofcom_page(html: str, *, base_url: str, limit: int) -> list[PolicyItem]:
    """Parse the official MOFCOM policy listing."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[PolicyItem] = []
    seen_urls: set[str] = set()
    for link in soup.select('a[href*="/art/"]'):
        href = link.get("href", "")
        if "/zcfb/" not in href:
            continue
        row = link.find_parent("li")
        date_element = row.find("span") if row else None
        if date_element is None:
            continue
        try:
            published = datetime.fromisoformat(
                date_element.get_text(strip=True)
            ).replace(tzinfo=UTC)
        except ValueError:
            continue
        title = link.get("title", "").strip() or link.get_text(" ", strip=True)
        url = urljoin(base_url, href)
        if url.startswith("http://www.mofcom.gov.cn/"):
            url = url.replace("http://", "https://", 1)
        if not title or url in seen_urls:
            continue
        category = row.find("em")
        items.append(PolicyItem(
            title=title,
            url=url,
            published=published,
            source="mofcom",
            summary=category.get_text(" ", strip=True) if category else None,
        ))
        seen_urls.add(url)
        if len(items) >= limit:
            break
    return items


def fetch_ustr_press(*, limit: int = 10, timeout: float = 15.0) -> list[PolicyItem]:
    """USTR 办公室新闻稿 (官方列表页).

    URL: https://ustr.gov/about-us/policy-offices/press-office/press-releases
    """
    url = "https://ustr.gov/about-us/policy-offices/press-office/press-releases"
    try:
        r = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "wto-policy-support/0.1"},
        )
        if r.status_code != 200:
            return []
        return _parse_ustr_page(r.text, base_url=str(r.url), limit=limit)
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
                source="federal_register",
                summary=doc.get("abstract", "")[:500] or None,
            ))
        return items
    except Exception:
        return []


def fetch_mofcom_rss(*, limit: int = 10, timeout: float = 15.0) -> list[PolicyItem]:
    """商务部政策发布列表 (函数名为向后兼容保留).

    URL: https://www.mofcom.gov.cn/zcfb/index.html
    """
    url = "https://www.mofcom.gov.cn/zcfb/index.html"
    try:
        r = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "wto-policy-support/0.1"},
        )
        if r.status_code != 200:
            return []
        return _parse_mofcom_page(r.text, base_url=str(r.url), limit=limit)
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
