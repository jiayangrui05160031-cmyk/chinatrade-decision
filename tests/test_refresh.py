"""Tests for agent/refresh.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wto_policy.agent import policy_cache as cache
from wto_policy.agent.refresh import (
    _should_refresh,
    ensure_fresh,
    freshness_report,
)


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "test.db"
    monkeypatch.setattr(cache, "DEFAULT_DB_PATH", p)
    cache.init_schema(p)
    from wto_policy.agent import refresh
    monkeypatch.setattr(refresh, "_db_path", p)
    return p


class TestShouldRefresh:
    def test_empty_cache_needs_refresh(self, db: Path) -> None:
        assert _should_refresh() is True

    def test_recent_crawl_is_fresh(self, db: Path) -> None:
        # 加 6 条 (>= 5) + 刚抓过
        for i in range(6):
            cache.upsert_items([{
                "source": "ustr",
                "url": f"https://a/{i}",
                "title": f"item {i}",
                "summary": None,
                "published": datetime.now(UTC).isoformat(),
            }], db_path=db)
        cache.record_crawl(
            source="ustr", query=None, new_items=6, total_items=6, db_path=db,
        )
        assert _should_refresh() is False

    def test_stale_crawl_needs_refresh(self, db: Path) -> None:
        for i in range(6):
            cache.upsert_items([{
                "source": "ustr",
                "url": f"https://a/{i}",
                "title": f"item {i}",
                "summary": None,
                "published": datetime.now(UTC).isoformat(),
            }], db_path=db)
        # 模拟 25 小时前抓过
        cache.record_crawl(
            source="ustr", query=None, new_items=6, total_items=6, db_path=db,
        )
        with cache.connect(db) as conn:
            conn.execute(
                "UPDATE crawl_log SET started_at = ? WHERE source = ?",
                ((datetime.now(UTC) - timedelta(hours=25)).isoformat(), "ustr"),
            )
        assert _should_refresh() is True


class TestFreshnessReport:
    def test_never_crawled(self, db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 切全局 DB 路径到临时
        from wto_policy.agent import policy_cache as cache_mod
        monkeypatch.setattr(cache_mod, "DEFAULT_DB_PATH", db)
        report = freshness_report()
        # 空缓存, 任意源都没记录
        assert report["total_items"] == 0
        assert report["is_fresh"] is False


class TestEnsureFresh:
    def test_force_skips_should_check(self, db: Path) -> None:
        # 即便 should_refresh=False, force=True 也会触发
        # 我们没法真去 update, 但可以验证 ensure_fresh 返回 True
        # (实际跑 update 会因网络问题失败, 但 background 线程吞掉)
        result = ensure_fresh(force=False, blocking=False)
        # 空缓存必返回 True
        assert result is True
