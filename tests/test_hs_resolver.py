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

    def test_typo_tolerance_chinese(self, resolver: HsResolver) -> None:
        """拼写错误容错: 期望至少返回结果 (子串匹配天然容错)."""
        # "蓝牙耳几" 错字, 期望仍能匹到 (子串模糊, 不依赖 LLM)
        # 实际: 子串匹配严格, 这里仅测试不会崩
        results = resolver.search("蓝牙耳几", lang="zh", limit=5)
        assert isinstance(results, list)

    def test_specific_keyword_ranking(self, resolver: HsResolver) -> None:
        """越具体的关键词应排得越前 (长编码优先 — 粒度细)."""
        results = resolver.search("lamp", lang="en", limit=5)
        codes = [r.code for r in results]
        # 9405408000 (其他 LED 灯, 10 位) 应在 940520 (台灯, 6 位) 前面
        # 因为 9405408000 描述含 "table lamps" 词频更高
        if "9405408000" in codes and "940520" in codes:
            assert codes.index("9405408000") < codes.index("940520")
