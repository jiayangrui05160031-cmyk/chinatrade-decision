"""Tests for agent/policy_cache.py — 离线 SQLite 测试."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wto_policy.agent.policy_cache import (
    init_schema,
    last_crawl,
    query_recent,
    record_crawl,
    stats,
    upsert_items,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    init_schema(p)
    return p


def _make_item(source: str, url: str, title: str, days_ago: int = 0) -> dict:
    return {
        "source": source,
        "url": url,
        "title": title,
        "summary": None,
        "published": (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(),
    }


class TestUpsert:
    def test_new_item(self, db: Path) -> None:
        n = upsert_items(
            [_make_item("ustr", "https://a/1", "USTR modifies 301")],
            db_path=db,
        )
        assert n == 1

    def test_duplicate_ignored(self, db: Path) -> None:
        item = _make_item("ustr", "https://a/1", "USTR")
        upsert_items([item], db_path=db)
        n = upsert_items([item], db_path=db)
        assert n == 0

    def test_multiple_sources(self, db: Path) -> None:
        items = [
            _make_item("ustr", "https://a/1", "USTR"),
            _make_item("federal_register", "https://b/1", "Fed Reg"),
        ]
        n = upsert_items(items, db_path=db)
        assert n == 2


class TestQuery:
    def test_recent(self, db: Path) -> None:
        upsert_items(
            [
                _make_item("ustr", "https://a/recent", "Recent news", 0),
                _make_item("ustr", "https://a/old", "Old news", 30),
            ],
            db_path=db,
        )
        rows = query_recent(days=7, db_path=db)
        assert len(rows) == 1
        assert rows[0]["title"] == "Recent news"

    def test_filter_by_source(self, db: Path) -> None:
        upsert_items(
            [
                _make_item("ustr", "https://a/1", "USTR"),
                _make_item("mofcom", "https://b/1", "MOFCOM"),
            ],
            db_path=db,
        )
        rows = query_recent(days=7, source="ustr", db_path=db)
        assert len(rows) == 1
        assert rows[0]["source"] == "ustr"

    def test_keyword(self, db: Path) -> None:
        upsert_items(
            [
                _make_item("ustr", "https://a/1", "Section 301 modification"),
                _make_item("ustr", "https://a/2", "Trade deficit update"),
            ],
            db_path=db,
        )
        rows = query_recent(days=7, keyword="301", db_path=db)
        assert len(rows) == 1


class TestCrawlLog:
    def test_record_and_query(self, db: Path) -> None:
        record_crawl(
            source="ustr", query="section 301",
            new_items=3, total_items=10, db_path=db,
        )
        last = last_crawl("ustr", db_path=db)
        assert last is not None
        assert last["status"] == "ok"
        assert last["new_items"] == 3


class TestStats:
    def test_basic(self, db: Path) -> None:
        upsert_items(
            [_make_item("ustr", "https://a/1", "x")],
            db_path=db,
        )
        record_crawl(source="ustr", query=None, new_items=1, total_items=1, db_path=db)
        s = stats(db_path=db)
        assert s["total"] == 1
        assert s["per_source"]["ustr"] == 1
        assert "ustr" in s["last_crawl_per_source"]
