"""Tests for agent/policy_fetcher.py — 离线 + 网络标记.

网络测试默认 skip, CI 跑时不打真实 API.
"""

from __future__ import annotations

import pytest

from wto_policy.agent.policy_fetcher import (
    PolicyItem,
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
                source="ustr.gov",
                summary="modifies",
            ),
        ]
        d = to_dict(items)
        assert d[0]["title"] == "USTR modifies Section 301"
        assert d[0]["source"] == "ustr.gov"


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
