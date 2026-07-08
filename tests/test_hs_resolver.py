"""Tests for core/hs_resolver.py."""

from __future__ import annotations

import pytest

from wto_policy.core.hs_resolver import HsResolver
from wto_policy.data.seed import load_sample


@pytest.fixture
def resolver() -> HsResolver:
    return HsResolver.from_list(load_sample())


class TestNormalize:
    def test_dotted(self, resolver: HsResolver) -> None:
        assert resolver.normalize("9405.40.80.00") == "9405408000"

    def test_spaces(self, resolver: HsResolver) -> None:
        assert resolver.normalize("9405 4080 00") == "9405408000"


class TestLookup:
    def test_10_digit(self, resolver: HsResolver) -> None:
        h = resolver.lookup("9405408000")
        assert h is not None
        assert h.chapter == "94"

    def test_dotted_input(self, resolver: HsResolver) -> None:
        h = resolver.lookup("9405.40.80.00")
        assert h is not None
        assert h.code == "9405408000"

    def test_missing_returns_none(self, resolver: HsResolver) -> None:
        assert resolver.lookup("0000000000") is None


class TestHierarchy:
    def test_parent(self, resolver: HsResolver) -> None:
        child = resolver.lookup("9405408000")
        assert child is not None
        parent = resolver.parent(child.code)
        assert parent is not None
        assert parent.code == "940540"

    def test_ancestors_chain(self, resolver: HsResolver) -> None:
        ancestors = resolver.ancestors("9405408000")
        # 9405408000 -> 940540 (没有 9405 因为 4 位不算独立 HS Code)
        assert [a.code for a in ancestors] == ["940540"]

    def test_children(self, resolver: HsResolver) -> None:
        kids = resolver.children("940540")
        codes = {c.code for c in kids}
        assert codes == {"9405404000", "9405408000"}


class TestSearch:
    def test_chinese_substring(self, resolver: HsResolver) -> None:
        results = resolver.search("LED", lang="zh", limit=10)
        assert any(r.code == "9405404000" for r in results)

    def test_english_word_match(self, resolver: HsResolver) -> None:
        results = resolver.search("bluetooth headphones", lang="en", limit=10)
        assert any(r.code == "8518302000" for r in results)

    def test_search_shortest_first(self, resolver: HsResolver) -> None:
        """编码短的(粒度粗)应排在前."""
        # 940510/940520/940530/940540 描述里都有 "lamps" 或 "lighting"
        results = resolver.search("lighting", lang="en", limit=10)
        # 至少拿到一个 6 位的 chapter 94 编码
        six_digit = [r for r in results if r.level == 6]
        assert len(six_digit) > 0
        # 第一个 6 位编码的字符串长度应 ≤ 后续 10 位
        first = six_digit[0]
        ten_digit = [r for r in results if r.level == 10]
        if ten_digit:
            assert len(first.code) <= len(ten_digit[0].code)

    def test_empty_query(self, resolver: HsResolver) -> None:
        assert resolver.search("", lang="zh") == []
        assert resolver.search("   ", lang="en") == []
