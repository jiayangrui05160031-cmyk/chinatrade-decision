"""Tests for agent/policy_fetcher.py — 离线 + 网络标记.

网络测试默认 skip, CI 跑时不打真实 API.
"""

from __future__ import annotations

import pytest

from wto_policy.agent.policy_fetcher import (
    PolicyItem,
    _parse_mofcom_page,
    _parse_ustr_page,
    search_policy,
    to_dict,
)


class TestOfflineBasic:
    def test_to_dict(self) -> None:
        items = [
            PolicyItem(
                title="USTR modifies Section 301",
                url="https://ustr.gov/x",
                published=__import__("datetime").datetime.now(__import__("datetime").UTC),
                source="ustr",
                summary="modifies",
            ),
        ]
        d = to_dict(items)
        assert d[0]["title"] == "USTR modifies Section 301"
        assert d[0]["source"] == "ustr"

    def test_parse_ustr_listing(self) -> None:
        html = """
        <div class="views-row">
          <time datetime="2026-08-07T12:00:00Z">2026-08-07</time>
          <a href="/about/press-office/press-releases/2026/example">Trade update</a>
        </div>
        """
        items = _parse_ustr_page(html, base_url="https://ustr.gov/news", limit=10)

        assert len(items) == 1
        assert items[0].source == "ustr"
        assert items[0].url == "https://ustr.gov/about/press-office/press-releases/2026/example"

    def test_parse_mofcom_listing(self) -> None:
        html = """
        <ul><li>
          <em>【对外贸易】</em>
          <a href="/zcfb/zc/art/2026/example.html" title="出口政策更新">政策</a>
          <span>2026-08-05</span>
        </li></ul>
        """
        items = _parse_mofcom_page(
            html,
            base_url="https://www.mofcom.gov.cn/zcfb/index.html",
            limit=10,
        )

        assert len(items) == 1
        assert items[0].source == "mofcom"
        assert items[0].title == "出口政策更新"
        assert items[0].url == "https://www.mofcom.gov.cn/zcfb/zc/art/2026/example.html"


@pytest.mark.network
class TestNetwork:
    """真实网络测试, 手动跑: pytest -m network."""

    def test_ustr(self) -> None:
        from wto_policy.agent.policy_fetcher import fetch_ustr_press
        items = fetch_ustr_press(limit=3)
        # 不强制有结果 (USTR 偶发维护), 但若有, schema 应正确
        for it in items:
            assert it.url.startswith("https://")

    def test_federal_register(self) -> None:
        from wto_policy.agent.policy_fetcher import fetch_federal_register
        items = fetch_federal_register(query="section 301", limit=3)
        for it in items:
            assert "federalregister.gov" in it.url

    def test_search(self) -> None:
        items = search_policy("section 301", limit_per_source=3)
        assert isinstance(items, list)
