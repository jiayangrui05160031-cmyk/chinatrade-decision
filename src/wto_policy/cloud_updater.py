"""云端 updater — 拉真实数据入云端 DB.

执行:
1. 拉 USITC HTSUS 2026 Rev 2 CSV (4MB, 3.5 万行)
2. 解析为 HsCode (10 位统计位 + 8 位 fallback)
3. 拉 USTR Section 301 真数据
4. 拉 Federal Register 最新政策
5. 拉中国海关 12360 公告
6. 全部入云端 SQLite (本地即可,云端用 Supabase/Neon)
"""

from __future__ import annotations

import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from wto_policy.agent.policy_cache import (
    init_schema,
    upsert_items,
)
from wto_policy.agent.policy_fetcher import (
    fetch_federal_register,
    fetch_mofcom_rss,
    fetch_ustr_press,
    to_dict,
)
from wto_policy.ingest.htsus_csv import (
    parse_htsus_csv,
)
from wto_policy.ingest.ustr_301 import SECTION_301_LISTS

# ============== HTSUS ==============
HTSUS_URL = "https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_2_csv.csv"
HTSUS_LOCAL = ROOT / "data" / "raw" / "hts_2026_rev2.csv"
HTSUS_PROCESSED = ROOT / "data" / "processed" / "htsus.parquet"

# ============== 中国海关公告 ==============
# 12360 是电话, 但有公开网页: 海关总署 公告 http://www.customs.gov.cn/customs/302249/302413/302414/index.html
CHINA_CUSTOMS_URL = "http://www.customs.gov.cn/customs/302249/302413/302414/index.html"

# ============== 云端 DB (本地 SQLite, 可换 Supabase/Neon) ==============
# ROOT = src/wto_policy/  →  ../../ 是项目根
CLOUD_DB = ROOT.parent.parent / "data" / "cloud.db"


def download_htsus() -> Path:
    """从 USITC 拉 HTSUS CSV."""
    HTSUS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    if HTSUS_LOCAL.exists() and (
        datetime.now(UTC).timestamp() - HTSUS_LOCAL.stat().st_mtime
    ) < 86400 * 30:  # 30 天内不重复拉
        print(f"  [skip] HTSUS 30 天内已下载: {HTSUS_LOCAL}")
        return HTSUS_LOCAL
    print(f"  [down] {HTSUS_URL}")
    import httpx
    with httpx.stream("GET", HTSUS_URL, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with open(HTSUS_LOCAL, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    print(f"  [done] {HTSUS_LOCAL.stat().st_size} bytes")
    return HTSUS_LOCAL


def ingest_htsus_to_db() -> int:
    """HTSUS → cloud.db.hs_codes 表."""
    rows = parse_htsus_csv(HTSUS_LOCAL)
    print(f"  [parsed] {len(rows)} HTSUS rows")

    init_schema(CLOUD_DB)  # 复用 policy_cache schema (但放不同表)
    conn = sqlite3.connect(CLOUD_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hs_codes (
            code TEXT PRIMARY KEY,
            level INTEGER NOT NULL,
            parent_code TEXT,
            chapter TEXT NOT NULL,
            description TEXT NOT NULL,
            description_en TEXT NOT NULL,
            source TEXT NOT NULL,
            general_rate TEXT,
            unit TEXT,
            crawled_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter ON hs_codes(chapter)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_desc ON hs_codes(description)")

    inserted = 0
    for r in rows:
        if not r.is_statistical or len(r.hts_number_norm) < 8:
            continue
        try:
            conn.execute(
                """INSERT OR REPLACE INTO hs_codes
                   (code, level, parent_code, chapter, description, description_en,
                    source, general_rate, unit, crawled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.hts_number_norm, len(r.hts_number_norm),
                    r.hts_number_norm[:-2] if len(r.hts_number_norm) == 10 else None,
                    r.chapter, r.description, r.description,
                    "usitc-htsus-2026-real", r.general_rate, r.unit,
                    datetime.now(UTC).isoformat(),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    print(f"  [inserted] {inserted} HS codes (10 位统计位优先)")
    return inserted


def ingest_ustr_301_to_db() -> int:
    """USTR 301 清单 → cloud.db.section_301 表."""
    conn = sqlite3.connect(CLOUD_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS section_301 (
            list_id TEXT PRIMARY KEY,
            list_name TEXT NOT NULL,
            rate REAL NOT NULL,
            effective_from TEXT NOT NULL,
            fr_citation TEXT,
            url TEXT,
            suspended INTEGER DEFAULT 0,
            sample_codes TEXT,
            crawled_at TEXT NOT NULL
        )
    """)
    inserted = 0
    for lst in SECTION_301_LISTS:
        conn.execute(
            """INSERT OR REPLACE INTO section_301
               (list_id, list_name, rate, effective_from, fr_citation, url, suspended, sample_codes, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lst["id"], lst["name"], lst["rate"],
                lst["effective_from"].isoformat(),
                lst["fr_citation"], lst["url"],
                1 if lst.get("suspended") else 0,
                ",".join(lst["sample_codes"]),
                datetime.now(UTC).isoformat(),
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    print(f"  [inserted] {inserted} Section 301 清单")
    return inserted


def ingest_policy_news() -> int:
    """拉 USTR / Federal Register / 商务部 公告 → 复用 policy_cache."""
    print("  [down] USTR press releases")
    ustr = fetch_ustr_press(limit=20)
    print("  [down] Federal Register (Section 301 + 232 + IEEPA)")
    fr = fetch_federal_register(query="section 301 china tariff", limit=20)
    print("  [down] 商务部 RSS")
    mofcom = fetch_mofcom_rss(limit=20)

    all_items = to_dict(ustr) + to_dict(fr) + to_dict(mofcom)
    n_new = upsert_items(all_items)
    print(f"  [inserted] {n_new} new policy items (of {len(all_items)} fetched)")
    return n_new


def main() -> None:
    print("=" * 70)
    print("云端 updater: 拉真实 USITC HTSUS + USTR 301 + 政策新闻")
    print("=" * 70)
    t0 = time.time()

    print()
    print("1. 拉 USITC HTSUS 2026 Rev 2 CSV (~4MB, 3.5 万行)")
    download_htsus()
    ingest_htsus_to_db()

    print()
    print("2. 入 USTR Section 301 清单")
    ingest_ustr_301_to_db()

    print()
    print("3. 拉政策新闻 (USTR / Federal Register / 商务部)")
    ingest_policy_news()

    elapsed = time.time() - t0

    # 报告
    conn = sqlite3.connect(CLOUD_DB)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print()
    print("=" * 70)
    print(f"云端 DB: {CLOUD_DB}")
    print(f"  表: {[t[0] for t in tables]}")
    for t in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"  {t[0]}: {n} 行")
    conn.close()
    print()
    print(f"总耗时: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
