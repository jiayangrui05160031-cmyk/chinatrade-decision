"""HTSUS CSV 解析器 — 拉 USITC 真实数据, 取代 8 条手填种子.

数据源: https://www.usitc.gov/2026_hts_revision_2
格式: HTS Number / Indent / Description / Unit / General / Special / Column 2 / Quota / Additional Duties
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from wto_policy.core.tariff_model import HsCode


@dataclass
class HtsusRow:
    """原始 HTSUS CSV 一行."""

    hts_number: str  # "0101.21.00" 含点
    hts_number_norm: str  # "01012100" 归一化 (无点)
    indent: int  # 0-9 层级 (0 = 统计位 8/10 位)
    description: str
    unit: str
    general_rate: str
    special_rate: str
    column2_rate: str
    additional_duties: str

    @property
    def is_statistical(self) -> bool:
        """统计位 = 8/10 位 (HTSUS 里 10 位是 statistical breakout, indent 通常 0+).

        不强制 indent==0, 因为有些 10 位是子子目 (indent=2/3).
        """
        return len(self.hts_number_norm) >= 8

    @property
    def chapter(self) -> str:
        return self.hts_number_norm[:2] if self.hts_number_norm else ""

    @property
    def hs_code(self) -> str:
        """提取纯数字 6-10 位."""
        return self.hts_number_norm


def parse_htsus_csv(csv_path: str | Path) -> list[HtsusRow]:
    """解析 HTSUS CSV 文件."""
    rows: list[HtsusRow] = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            hts_raw = (raw.get("HTS Number") or "").strip().strip('"')
            if not hts_raw:
                continue
            indent_str = (raw.get("Indent") or "0").strip()
            try:
                indent = int(indent_str) if indent_str else 0
            except ValueError:
                indent = 0
            # 归一化: 去点
            hts_norm = re.sub(r"\D", "", hts_raw)
            rows.append(HtsusRow(
                hts_number=hts_raw,
                hts_number_norm=hts_norm,
                indent=indent,
                description=(raw.get("Description") or "").strip().strip('"'),
                unit=(raw.get("Unit of Quantity") or "").strip().strip('"'),
                general_rate=(raw.get("General Rate of Duty") or "").strip().strip('"'),
                special_rate=(raw.get("Special Rate of Duty") or "").strip().strip('"'),
                column2_rate=(raw.get("Column 2 Rate of Duty") or "").strip().strip('"'),
                additional_duties=(raw.get("Additional Duties") or "").strip().strip('"'),
            ))
    return rows


def rows_to_hs_codes(rows: list[HtsusRow]) -> list[HsCode]:
    """HTSUS 行 → HsCode 模型 (10 位统计位优先)."""
    # 优先 10 位 > 8 位 (按长度倒序去重, 保留最具体的)
    ten_digit: list[HsCode] = []

    for r in rows:
        if not r.is_statistical:
            continue
        if len(r.hts_number_norm) == 10:
            ten_digit.append(HsCode(
                code=r.hts_number_norm,
                level=10,
                parent_code=r.hts_number_norm[:8] if len(r.hts_number_norm) >= 8 else None,
                chapter=r.chapter,
                description_zh=r.description,  # HTSUS 是英文, 我们用英文描述填中文字段
                description_en=r.description,
                source="usitc-htsus-2026-real",
            ))

    # 8 位 fallback (从 10 位截断)
    eight_codes: dict[str, HsCode] = {}
    for r in rows:
        if r.indent == 0 and len(r.hts_number_norm) == 8:
            eight_codes.setdefault(r.hts_number_norm, HsCode(
                code=r.hts_number_norm,
                level=8,
                parent_code=r.hts_number_norm[:6] if len(r.hts_number_norm) >= 6 else None,
                chapter=r.chapter,
                description_zh=r.description,
                description_en=r.description,
                source="usitc-htsus-2026-real",
            ))

    return ten_digit + list(eight_codes.values())


def save_parsed(rows: list[HtsusRow], out_path: str | Path) -> int:
    """存为 Parquet (高效读取)."""
    import pandas as pd
    df = pd.DataFrame([vars(r) for r in rows])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return len(rows)


def parse_general_rate(rate_str: str) -> float | None:
    """解析 HTSUS 'General Rate' 字符串.

    格式: "Free", "0.5%", "2.7¢/kg + 1.3%", "5¢/kg", ""
    Returns: 从价税率 (0-1), None 表示不可解析.
    """
    if not rate_str or rate_str.lower() in ("free", "free.", ""):
        return 0.0
    # 含 ¢ (美分) 或 ¥ (人民币) → 含从量, 复杂, 暂不处理
    if "¢" in rate_str or "/kg" in rate_str or "/unit" in rate_str:
        return None
    # "0.5%" → 0.005
    m = re.search(r"([\d.]+)\s*%", rate_str)
    if m:
        return float(m.group(1)) / 100
    return None


__all__ = [
    "HtsusRow",
    "parse_general_rate",
    "parse_htsus_csv",
    "rows_to_hs_codes",
    "save_parsed",
]
