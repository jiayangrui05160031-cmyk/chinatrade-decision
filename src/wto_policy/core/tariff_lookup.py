"""关税查询匹配引擎.

输入: (hs_code, origin, destination, on_date)
输出: 适用该情景的所有 TariffMeasure 列表

匹配规则:
- HS 码必须前缀匹配 (例 9405408000 也匹配 940540 的措施)
- origin: 精确匹配 CN; MFN 用 'XX' 表示"所有原产", 实际查询时应视为匹配任何 origin
- destination: 精确匹配
- on_date: 在 effective_from..effective_to 窗口内
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from wto_policy.core.tariff_model import MeasureType, TariffMeasure


class TariffLookup:
    """内存版 Tariff 查询.

    数据量小 (MVP 几百条) 时直接 list scan;
    数据量大了再上 SQLite 索引.
    """

    def __init__(self, measures: Iterable[TariffMeasure]) -> None:
        self._measures: list[TariffMeasure] = list(measures)

    def find(
        self,
        *,
        hs_code: str,
        origin: str = "CN",
        destination: str = "US",
        on: date | None = None,
    ) -> list[TariffMeasure]:
        """返回所有适用措施.

        Args:
            hs_code: 6/8/10 位 (10 位优先)
            origin: ISO 2-letter
            destination: ISO 2-letter
            on: 生效日期, 默认今天
        """
        target = on or date.today()
        target_hs = hs_code.replace(".", "").replace(" ", "")
        origin_up = origin.upper()
        dest_up = destination.upper()

        results: list[TariffMeasure] = []
        for m in self._measures:
            # 1. HS 前缀匹配
            #    特殊: hs_code == "000000" 表示"全 HS 通配" (IEEPA 等)
            hs_match = m.hs_code == "000000" or target_hs.startswith(m.hs_code)
            if not hs_match:
                continue
            # 2. origin 匹配: MFN 视为通配, 其他要精确
            if m.origin == "XX":  # MFN 通配
                pass
            elif m.origin.upper() != origin_up:
                continue
            # 3. destination 匹配
            if m.destination.upper() != dest_up:
                continue
            # 4. 日期窗口
            if m.effective_from > target:
                continue
            if m.effective_to is not None and m.effective_to < target:
                continue
            results.append(m)
        return results

    def group_by_type(
        self, measures: list[TariffMeasure]
    ) -> dict[MeasureType, list[TariffMeasure]]:
        """按措施类型分组, 同一类型多条时全部返回(例 Section 301 多清单叠加)."""
        groups: dict[MeasureType, list[TariffMeasure]] = {}
        for m in measures:
            groups.setdefault(m.measure_type, []).append(m)
        return groups


__all__ = ["TariffLookup"]
