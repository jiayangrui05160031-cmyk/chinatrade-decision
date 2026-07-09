"""HTSUS CSV 关税字段入云端.

HTSUS CSV 每行有 4 个税率字段:
- General Rate of Duty        基础 MFN (对所有国家)
- Special Rate of Duty        优惠 (FTA 等)
- Column 2 Rate of Duty       古巴/朝鲜等禁运国家
- Additional Duties           Section 301 (中国), IEEPA, etc

我们把 General Rate + Special Rate 入 hs_codes 表, 实时算 MFN.
USTR 301 / 232 / IEEPA 用现成的 section_301 表 (人类核对过).

查询路径:
lookup_tariff(hs_code)
  → hs_codes 表拿到 general_rate (MFN)
  → section_301 表拿 301 rate (按 HS 段判断)
  → 硬编码 232 (钢/铝) / IEEPA (所有原产中国)
  → 算 total
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
HTSUS_LOCAL = ROOT / "data" / "raw" / "hts_2026_rev2.csv"
CLOUD_DB = ROOT / "data" / "cloud.db"


def parse_general_rate(rate_str: str) -> float | None:
    """解析 General Rate.

    Returns: 从价税率 (0.034 = 3.4%), None 表示不可解析.
    """
    if not rate_str:
        return 0.0
    s = rate_str.strip()
    if s.lower() in ("free", "free.", ""):
        return 0.0
    # 含 ¢ (美分) 或 ¥ (人民币) → 从量, 暂不处理
    if "¢" in s or "/kg" in s or "/unit" in s:
        return None
    m = re.search(r"([\d.]+)\s*%", s)
    if m:
        return float(m.group(1)) / 100
    # "No change" / "The duty provided..." → 复杂, None
    return None


def _ensure_htsus_table(conn: sqlite3.Connection) -> None:
    """hs_codes 表加 general_rate 列 (如果还没)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(hs_codes)").fetchall()}
    if "general_rate" not in cols:
        conn.execute("ALTER TABLE hs_codes ADD COLUMN general_rate TEXT")
    if "special_rate" not in cols:
        conn.execute("ALTER TABLE hs_codes ADD COLUMN special_rate TEXT")
    if "column2_rate" not in cols:
        conn.execute("ALTER TABLE hs_codes ADD COLUMN column2_rate TEXT")


def ingest_htsus_tariff_to_db() -> int:
    """从 HTSUS CSV 抽 General Rate / Special Rate / Column 2 写到 hs_codes 表."""
    if not HTSUS_LOCAL.exists():
        print(f"  ! HTSUS CSV 不存在: {HTSUS_LOCAL}")
        return 0

    from wto_policy.ingest.htsus_csv import parse_htsus_csv

    rows = parse_htsus_csv(HTSUS_LOCAL)
    rows = [r for r in rows if r.indent == 0 and len(r.hts_number_norm) >= 8]
    # 父子目关系: 优先 10 位, 没有就 8 位
    # 同一个 8 位可能有多个 10 位, 暂取第一个
    by_prefix: dict[str, any] = {}
    for r in rows:
        # 8 位和 10 位都写一条
        for length in (10, 8):
            if len(r.hts_number_norm) >= length:
                key = r.hts_number_norm[:length].ljust(length, "0")
                if key not in by_prefix or len(r.hts_number_norm) > len(by_prefix[key].hts_number_norm):
                    by_prefix[key] = r

    conn = sqlite3.connect(CLOUD_DB)
    _ensure_htsus_table(conn)
    now = datetime.now(UTC).isoformat()

    updated = 0
    for code, r in by_prefix.items():
        conn.execute(
            """UPDATE hs_codes
               SET general_rate = ?, special_rate = ?, column2_rate = ?, crawled_at = ?
               WHERE code = ?""",
            (r.general_rate, r.special_rate, r.column2_rate, now, code),
        )
        if conn.execute("SELECT changes()").fetchone()[0]:
            updated += 1
    conn.commit()
    conn.close()
    return updated


def get_real_mfn_rate(hs_code: str, *, db_path: Path | None = None) -> float | None:
    """从云端 DB 读该 HS 码的 MFN (General Rate).

    Returns: 从价税率 (0.034 = 3.4%), None 表示查不到 / 复杂.
    """
    db = db_path or CLOUD_DB
    conn = sqlite3.connect(str(db), timeout=10.0)
    try:
        code = re.sub(r"\D", "", hs_code).ljust(10, "0")[:10]
        # 先查 10 位, 没有再查 8 位
        for length in (10, 8):
            search_code = code[:length].ljust(length, "0")
            row = conn.execute(
                "SELECT general_rate FROM hs_codes WHERE code = ?",
                (search_code,),
            ).fetchone()
            if row:
                rate_str = row[0] if row[0] else ""
                if rate_str:
                    rate = parse_general_rate(rate_str)
                    if rate is not None:
                        return rate
        return None
    finally:
        conn.close()


# ============ Self-test ============
if __name__ == "__main__":
    print("=== ingest HTSUS 关税字段 ===")
    n = ingest_htsus_tariff_to_db()
    print(f"  updated {n} rows")
    print()
    print("=== 测试 get_real_mfn_rate ===")
    for hs in ["8518302000", "9405408000", "9503000000", "7208000000"]:
        rate = get_real_mfn_rate(hs)
        print(f"  {hs} -> MFN {rate}")

    print()
    print("=== 看 8518302000 的 DB 详情 ===")
    conn = sqlite3.connect(CLOUD_DB)
    row = conn.execute(
        "SELECT code, description_en, general_rate, special_rate, column2_rate "
        "FROM hs_codes WHERE code = '8518302000'"
    ).fetchone()
    if row:
        keys = ("code", "description_en", "general_rate", "special_rate", "column2_rate")
        for k, v in zip(keys, row, strict=True):
            print(f"  {k}: {v}")
    conn.close()


__all__ = ["get_real_mfn_rate", "ingest_htsus_tariff_to_db", "parse_general_rate"]
