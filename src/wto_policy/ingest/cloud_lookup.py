"""云端 HS 查询器 — 从 cloud.db 查 HS 码, 替代手填种子."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

CLOUD_DB = Path(__file__).parent.parent.parent.parent / "data" / "cloud.db"


class CloudHsLookup:
    """从云端 SQLite 查 HS (替代之前的 HsResolver + 种子)."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or CLOUD_DB
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Cloud DB not found: {self.db_path}. 跑 wto-update --cloud 先建表"
            )
        self._conn: sqlite3.Connection | None = None

    def _conn_get(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def normalize(self, raw: str) -> str:
        return re.sub(r"\D", "", raw)

    def lookup(self, code: str) -> dict | None:
        """精确查 HS 码."""
        norm = self.normalize(code)
        if len(norm) < 6:
            return None
        # 先查 10 位
        conn = self._conn_get()
        row = conn.execute(
            "SELECT * FROM hs_codes WHERE code = ? OR code = ? ORDER BY level DESC LIMIT 1",
            (norm, norm.ljust(10, "0")[:10]),
        ).fetchone()
        return dict(row) if row else None

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        """模糊搜索.

        策略:
        - 中文: 用整 query (去除空格) 精确子串, OR 拆 query 成 2-3 字符子串
        - 英文: 拆词 AND 匹配
        """
        q = query.strip()
        if not q:
            return []
        conn = self._conn_get()
        q_lower = q.lower()

        # 决定搜索策略
        is_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in q)

        if is_chinese:
            # 中文: 用 query 精确子串 + 拆成 2 字组合
            clauses = ["description LIKE ?"]
            params: list = [f"%{q}%"]
            # 拆 2 字组合 (例 "LED台灯" -> "LED", "台灯", "LE", "ED台", "台灯")
            cleaned = q.replace(" ", "")
            for i in range(len(cleaned) - 1):
                clauses.append("description LIKE ?")
                params.append(f"%{cleaned[i:i+2]}%")
            where = " OR ".join(clauses)
        else:
            # 英文: 拆 word AND
            words = q_lower.split()
            if not words:
                return []
            clauses = []
            params = []
            for w in words:
                clauses.append("(description LIKE ? OR description_en LIKE ?)")
                params.extend([f"%{w}%", f"%{w}%"])
            where = " AND ".join(clauses)

        sql = f"""
            SELECT * FROM hs_codes
            WHERE {where}
            ORDER BY level DESC, code ASC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        conn = self._conn_get()
        return conn.execute("SELECT COUNT(*) AS c FROM hs_codes").fetchone()["c"]

    def stats(self) -> dict:
        conn = self._conn_get()
        total = conn.execute("SELECT COUNT(*) AS c FROM hs_codes").fetchone()["c"]
        chapters = conn.execute(
            "SELECT chapter, COUNT(*) AS c FROM hs_codes GROUP BY chapter ORDER BY chapter"
        ).fetchall()
        s301 = conn.execute("SELECT COUNT(*) AS c FROM section_301").fetchone()["c"]
        return {
            "total_hs_codes": total,
            "chapters": len(chapters),
            "section_301_lists": s301,
        }


__all__ = ["CLOUD_DB", "CloudHsLookup"]
