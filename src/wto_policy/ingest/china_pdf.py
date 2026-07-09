"""中国海关 PDF 解析器 — 拉 gov.cn 真实公告 PDF.

数据源: https://www.gov.cn/zhengce/zhengceku/202512/content_7053062.htm
文件:
- 进口商品暂定税率表 (P020251229817547633702.pdf, 935 项)
- 出口商品税率表 (P020251229817547918245.pdf, 107 项)
- 关税配额商品税目税率表
- 进出口税则税目调整表
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent  # ingest -> wto_policy -> src -> project
PDF_DIR = ROOT / "data" / "raw" / "china_2026"
CLOUD_DB = ROOT / "data" / "cloud.db"

# 2026 关税调整方案公告 URL (PDF 在同目录)
GOVCN_BASE = "https://www.gov.cn/zhengce/zhengceku/202512"
GOVCN_ANNOUNCEMENT = f"{GOVCN_BASE}/content_7053062.htm"

# 5 个 PDF (含目录页 PDF)
PDF_URLS = {
    "main": f"{GOVCN_BASE}/P020251229817547511264.pdf",  # 主方案
    "import_duty": f"{GOVCN_BASE}/P020251229817547633702.pdf",  # 进口暂定税率
    "quota": f"{GOVCN_BASE}/P020251229817547826335.pdf",  # 关税配额
    "export_duty": f"{GOVCN_BASE}/P020251229817547918245.pdf",  # 出口税率
    "tariff_adjustment": f"{GOVCN_BASE}/P020251229817548018648.pdf",  # 税则调整
}


def download_china_pdfs() -> list[Path]:
    """下载 2026 中国关税调整方案全部 PDF."""
    import httpx
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, url in PDF_URLS.items():
        out = PDF_DIR / f"{name}.pdf"
        if out.exists() and out.stat().st_size > 1000:
            print(f"  [skip] {out.name} ({out.stat().st_size} bytes)")
            paths.append(out)
            continue
        print(f"  [down] {out.name} from {url}")
        r = httpx.get(url, timeout=60, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            out.write_bytes(r.content)
            paths.append(out)
            print(f"    -> {out.stat().st_size} bytes")
    return paths


@dataclass
class ChinaDutyRow:
    """中国海关 PDF 解析的一行: HS + 描述 + 最惠国 + 暂定."""

    hs_code: str  # 8/10 位
    description_zh: str
    mfn_rate: float  # 最惠国税率 (基础)
    provisional_rate: float  # 暂定税率 (低于 MFN)
    is_ex: bool = False  # 是否 "ex" (子目范围, 不全适用)


def parse_china_import_duty_pdf(pdf_path: Path) -> list[ChinaDutyRow]:
    """解析《进口商品暂定税率表》PDF.

    PDF 文本格式 (示例):
        1 02011000 整头及半头鲜、冷牛肉 12 8
        2 ex 02012000 鲜、冷带骨牛肉 12 4
        ...
    """
    import pdfplumber
    rows: list[ChinaDutyRow] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # 匹配: [序号] [ex] HS编号 描述 MFN 暂定
                m = re.match(
                    r"^(\d+)\s+(ex\s+)?(\d{8,10})\s+(.+?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$",
                    line,
                )
                if not m:
                    continue
                _, ex_flag, hs, desc, mfn, prov = m.groups()
                rows.append(ChinaDutyRow(
                    hs_code=hs,
                    description_zh=desc.strip(),
                    mfn_rate=float(mfn),
                    provisional_rate=float(prov),
                    is_ex=bool(ex_flag),
                ))
    return rows


def ingest_china_to_db(rows: list[ChinaDutyRow], *, table: str = "china_import_duty") -> int:
    """中国海关税率入 cloud.db."""
    if not rows:
        return 0
    conn = sqlite3.connect(CLOUD_DB)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            hs_code TEXT NOT NULL,
            description_zh TEXT NOT NULL,
            mfn_rate REAL NOT NULL,
            provisional_rate REAL NOT NULL,
            is_ex INTEGER DEFAULT 0,
            source TEXT DEFAULT 'gov.cn-2026',
            crawled_at TEXT NOT NULL
        )
    """)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_hs ON {table}(hs_code)")
    inserted = 0
    for r in rows:
        conn.execute(
            f"""INSERT OR REPLACE INTO {table}
               (hs_code, description_zh, mfn_rate, provisional_rate, is_ex, source, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                r.hs_code, r.description_zh, r.mfn_rate, r.provisional_rate,
                1 if r.is_ex else 0, "gov.cn-2026",
                datetime.now(UTC).isoformat(),
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def main() -> None:
    print("=" * 70)
    print("中国海关 2026 关税调整方案 (gov.cn 真实数据)")
    print("=" * 70)

    print()
    print("1. 下载 PDF (gov.cn)")
    paths = download_china_pdfs()
    print(f"  共 {len(paths)} 个 PDF")

    print()
    print("2. 解析进口商品暂定税率表")
    import_path = PDF_DIR / "import_duty.pdf"
    if not import_path.exists():
        print(f"  ! 缺 {import_path}")
        return
    rows = parse_china_import_duty_pdf(import_path)
    print(f"  解析 {len(rows)} 行")

    print()
    print("3. 入云端 DB")
    n = ingest_china_to_db(rows)
    print(f"  入 {n} 行 (cloud.db.china_import_duty)")

    conn = sqlite3.connect(CLOUD_DB)
    print()
    print("=" * 70)
    print("云端 DB 新增表:")
    print(f"  china_import_duty: {conn.execute('SELECT COUNT(*) FROM china_import_duty').fetchone()[0]} 行")
    conn.close()


if __name__ == "__main__":
    main()
