"""SQLite 政策缓存.

存储:
- policy_items: USTR / Federal Register / 商务部 公告
- crawl_log: 每次抓取的时间/源/结果数

特点:
- 同一条 (source, url) 不重复入库 (UNIQUE)
- 按抓取时间索引, 方便查"最近 N 天"
- 线程安全 (同一连接串行使用, 进程级 lock)
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

# 默认数据库位置: data/cache/policies.db
DEFAULT_DB_PATH = Path("data/cache/policies.db")

_LOCK = threading.Lock()


def get_db_path() -> Path:
    """获取数据库路径, 首次调用时确保父目录存在."""
    p = DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect(db_path: Path | None = None):
    """获取 SQLite 连接 (with commit/close)."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema(db_path: Path | None = None) -> None:
    """初始化表结构 (幂等)."""
    with connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS policy_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                published TEXT NOT NULL,
                crawled_at TEXT NOT NULL,
                UNIQUE(source, url)
            );
            CREATE INDEX IF NOT EXISTS idx_published ON policy_items(published DESC);
            CREATE INDEX IF NOT EXISTS idx_source ON policy_items(source);
            CREATE INDEX IF NOT EXISTS idx_crawled ON policy_items(crawled_at DESC);

            CREATE TABLE IF NOT EXISTS crawl_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                source TEXT NOT NULL,
                query TEXT,
                new_items INTEGER DEFAULT 0,
                total_items INTEGER DEFAULT 0,
                status TEXT,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_log_started ON crawl_log(started_at DESC);
        """)


def upsert_items(
    items: list[dict],
    *,
    db_path: Path | None = None,
) -> int:
    """插入/忽略 (source, url) 重复. 返回新插入数."""
    if not items:
        return 0
    now = datetime.now(UTC).isoformat()
    new_count = 0
    with _LOCK, connect(db_path) as conn:
        for it in items:
            try:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO policy_items
                        (source, url, title, summary, published, crawled_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        it["source"],
                        it["url"],
                        it["title"],
                        it.get("summary"),
                        it["published"],
                        now,
                    ),
                )
                if cur.rowcount > 0:
                    new_count += 1
            except sqlite3.IntegrityError:
                pass
    return new_count


def query_recent(
    *,
    days: int = 7,
    source: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict]:
    """查最近 N 天政策. keyword 在 title/summary 模糊匹配."""
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    sql = "SELECT * FROM policy_items WHERE published >= ?"
    params: list = [since]
    if source:
        sql += " AND source = ?"
        params.append(source)
    if keyword:
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])
    sql += " ORDER BY published DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def last_crawl(source: str, *, db_path: Path | None = None) -> dict | None:
    """查某个源的最近一次抓取记录."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM crawl_log WHERE source = ? ORDER BY started_at DESC LIMIT 1",
            (source,),
        ).fetchone()
    return dict(row) if row else None


def record_crawl(
    *,
    source: str,
    query: str | None,
    new_items: int,
    total_items: int,
    status: str = "ok",
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    """记录一次抓取 (用于审计 + 实时性检查)."""
    now = datetime.now(UTC).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO crawl_log
                (started_at, finished_at, source, query, new_items, total_items, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, now, source, query, new_items, total_items, status, error),
        )


def stats(*, db_path: Path | None = None) -> dict:
    """缓存统计: 总条数 / 各源条数 / 最近抓取."""
    with connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM policy_items").fetchone()["c"]
        per_source = {
            r["source"]: r["c"]
            for r in conn.execute(
                "SELECT source, COUNT(*) AS c FROM policy_items GROUP BY source"
            ).fetchall()
        }
        last = conn.execute(
            "SELECT source, MAX(started_at) AS last FROM crawl_log GROUP BY source"
        ).fetchall()
        last_per_source = {r["source"]: r["last"] for r in last}
    return {
        "total": total,
        "per_source": per_source,
        "last_crawl_per_source": last_per_source,
    }


__all__ = [
    "get_db_path",
    "init_schema",
    "last_crawl",
    "query_recent",
    "record_crawl",
    "stats",
    "upsert_items",
]
