"""中国海关/国务院公告抓取 — 真对接中国政府网 (gov.cn).

数据源:
- 中国政府网 (gov.cn) 通告: 关税调整方案 / 反倾销 / 反补贴
- 国务院关税税则委员会 (税委会公告): 进出口税则调整
- 商务部: 反倾销 / 反补贴决定 (cws.mofcom.gov.cn)

策略:
- 不直连 customs.gov.cn (反爬 WAF 412)
- 用 gov.cn / 商务部 镜像, 公开 + 无反爬
- 关键词: 关税 / 出口退税 / 反倾销 / 进出口税则 / HS 编码调整
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


def fetch_govcn_search(
    query: str = "关税",
    *,
    limit: int = 10,
    timeout: float = 15.0,
) -> list[dict]:
    """中国政府网搜索: 找最新关税/反倾销/出口退税 公告.

    URL: https://sousuo.www.gov.cn/zcwjk/policyRelevantList?q=...
    备用 URL: 国务院政策文件库 API
    """
    items: list[dict] = []
    # 中国政府网搜索 API (公开, 无需 key)
    urls_to_try = [
        # 国务院文件库 (公开 RSS-like)
        f"https://sousuo.www.gov.cn/search-gov/data?t=zhzs&q={query}&timetype=&mintime=&maxtime=&sort=&sortType=1&searchfield=&pcodeJiguan=&childtype=&subchildtype=&tsbq=&pubtimeyear=&puborg=&pcodeYear=&pcodeNum=&filetype=&p=1&n=10&inpro=&bmfl=&dup=",
    ]
    for url in urls_to_try:
        try:
            r = httpx.get(url, timeout=timeout, follow_redirects=True)
            if r.status_code != 200:
                continue
            # 可能是 JSON
            try:
                data = r.json()
                for item in data.get("searchList", [])[:limit]:
                    items.append({
                        "title": item.get("title", "").strip(),
                        "url": "https://www.gov.cn" + item.get("url", "").lstrip("./"),
                        "published": item.get("publishDate", ""),
                        "source": "gov.cn",
                        "summary": item.get("summary", ""),
                    })
                if items:
                    return items
            except Exception:
                pass
        except Exception:
            continue
    return items


def fetch_mofcom_announcements(
    *,
    limit: int = 10,
    timeout: float = 15.0,
) -> list[dict]:
    """商务部公告 — 反倾销/反补贴决定.

    URL: https://cws.mofcom.gov.cn/
    """
    items: list[dict] = []
    # 商务部贸易救济调查局公告列表 (公开页面)
    urls = [
        "https://cws.mofcom.gov.cn/antidumping/api/announcement/list?pageNum=1&pageSize=20&keyword=",
    ]
    for url in urls:
        try:
            r = httpx.get(url, timeout=timeout)
            if r.status_code != 200:
                continue
            data = r.json()
            for item in data.get("data", [])[:limit]:
                items.append({
                    "title": item.get("title", ""),
                    "url": "https://cws.mofcom.gov.cn" + item.get("url", ""),
                    "published": item.get("publishDate", ""),
                    "source": "mofcom.gov.cn",
                    "summary": item.get("content", "")[:200],
                })
            if items:
                return items
        except Exception:
            continue
    return items


def fetch_govcn_rss(*, limit: int = 20, timeout: float = 15.0) -> list[dict]:
    """中国政府网政策文件库 (RSS-like).

    URL: http://www.gov.cn/zhengce/...
    实际没有标准 RSS, 我们搜索 "关税" 关键词.
    """
    items: list[dict] = []
    # 1. 搜索通告
    items.extend(fetch_govcn_search("关税调整", limit=limit))
    items.extend(fetch_govcn_search("反倾销", limit=limit))
    items.extend(fetch_govcn_search("出口退税", limit=limit))
    items.extend(fetch_mofcom_announcements(limit=limit))
    return items


def to_china_policy_items(items: list[dict]) -> list[dict]:
    """标准化成 policy_cache 格式."""
    out = []
    for it in items:
        # 解析时间
        pub = it.get("published", "")
        try:
            dt = parsedate_to_datetime(pub) if pub else datetime.now(UTC)
        except (TypeError, ValueError):
            dt = datetime.now(UTC)
        out.append({
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "published": dt.isoformat(),
            "source": it.get("source", "gov.cn"),
            "summary": it.get("summary", ""),
        })
    return out


__all__ = [
    "fetch_govcn_rss",
    "fetch_govcn_search",
    "fetch_mofcom_announcements",
    "to_china_policy_items",
]
