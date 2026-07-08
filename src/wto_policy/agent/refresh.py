"""Agent 启动时自动拉新政策 — 「实时」的实现.

行为:
- Agent 第一次 run() 之前, 自动调一次 update
- 若缓存里 < 5 条或最近抓取 > 24h, 触发实时拉取
- 拉取在后台线程跑, 不阻塞 Agent 启动
- 拉取结果写 SQLite, 后续 query 都用新数据
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta

from wto_policy.agent.policy_cache import init_schema, stats
from wto_policy.agent.update import run_update

log = logging.getLogger(__name__)

_REFRESH_INTERVAL = timedelta(hours=24)
_MIN_ITEMS_TO_SKIP_REFRESH = 5
_bg_thread: threading.Thread | None = None
_bg_lock = threading.Lock()
# 测试时可注入 (monkeypatch)
_db_path = None


def set_db_path(path) -> None:  # type: ignore[no-untyped-def]
    """测试 hook: 切换数据库路径."""
    global _db_path
    _db_path = path  # type: ignore[assignment]


def _db() -> None:  # placeholder for compat
    pass


def _should_refresh() -> bool:
    """判断是否需要刷新:
    - 缓存 < 5 条 → 必刷
    - 任一源最近抓取 > 24h → 刷
    - 否则不刷 (避免每次都打 API)
    """
    init_schema(_db_path)
    s = stats(db_path=_db_path)
    if s["total"] < _MIN_ITEMS_TO_SKIP_REFRESH:
        return True
    last = s.get("last_crawl_per_source", {})
    if not last:
        return True
    threshold = datetime.now(UTC) - _REFRESH_INTERVAL
    for _src, t in last.items():
        if not t:
            return True
        try:
            when = datetime.fromisoformat(t)
            if when < threshold:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _background_refresh() -> None:
    """后台线程执行 update, 失败不抛."""
    try:
        with _bg_lock:
            run_update()
    except Exception as e:
        log.warning("background refresh failed: %s", e)


def ensure_fresh(*, force: bool = False, blocking: bool = False) -> bool:
    """确保缓存是新鲜的. 返回 True=已刷新, False=缓存够新.

    Args:
        force: 强制刷新 (不管缓存状态)
        blocking: 同步等待 (默认后台跑, 不阻塞)
    """
    if not force and not _should_refresh():
        return False
    if blocking:
        _background_refresh()
    else:
        global _bg_thread
        if _bg_thread is None or not _bg_thread.is_alive():
            _bg_thread = threading.Thread(target=_background_refresh, daemon=True)
            _bg_thread.start()
    return True


def freshness_report() -> dict:
    """返回缓存新鲜度报告 — Agent 启动时给用户看."""
    init_schema(_db_path)  # 兜底, 首次跑自动建表
    s = stats(db_path=_db_path)
    last = s.get("last_crawl_per_source", {})
    now = datetime.now(UTC)
    last_ago: dict[str, str] = {}
    for src, t in last.items():
        if not t:
            last_ago[src] = "never"
            continue
        try:
            when = datetime.fromisoformat(t)
            delta = now - when
            hours = delta.total_seconds() / 3600
            if hours < 1:
                last_ago[src] = f"{int(delta.total_seconds() / 60)} 分钟前"
            elif hours < 24:
                last_ago[src] = f"{hours:.1f} 小时前"
            else:
                last_ago[src] = f"{hours / 24:.1f} 天前"
        except (TypeError, ValueError):
            last_ago[src] = "?"
    return {
        "total_items": s["total"],
        "per_source": s["per_source"],
        "last_ago": last_ago,
        "is_fresh": not _should_refresh(),
    }


__all__ = ["ensure_fresh", "freshness_report"]
