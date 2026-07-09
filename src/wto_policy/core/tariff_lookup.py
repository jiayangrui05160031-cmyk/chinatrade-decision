"""关税查询匹配引擎.

输入: (hs_code, origin, destination, on_date)
输出: 适用该情景的所有 TariffMeasure 列表

匹配规则:
- HS 码必须前缀匹配 (例 9405408000 也匹配 940540 的措施)
- origin: 精确匹配 CN; MFN 用 'XX' 表示"所有原产", 实际查询时应视为匹配任何 origin
- destination: 精确匹配
- on_date: 在 effective_from..effective_to 窗口内

新增 (v0.2):
- extra_mfn: dict[hs_prefix, rate]  真库来的 MFN (覆盖种子里的 MFN)
- get_mfn():  按 HS 前缀查 MFN
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from wto_policy.core.tariff_model import MeasureType, TariffMeasure


class TariffLookup:
    """内存版 Tariff 查询 (含 MFN 来源扩展)."""

    def __init__(
        self,
        measures: Iterable[TariffMeasure],
        extra_mfn: dict[str, float] | None = None,
    ) -> None:
        self._measures: list[TariffMeasure] = list(measures)
        # MFN 来源: HS 前缀 -> 从价税率 (例 "85183020": 0.0)
        self._extra_mfn: dict[str, float] = extra_mfn or {}

    def add_mfn(self, hs_prefix: str, rate: float) -> None:
        """加一条 MFN 来源 (云端真实数据, 比种子准)."""
        self._extra_mfn[hs_prefix] = rate

    def get_mfn(self, hs_code: str) -> float | None:
        """从 extra_mfn 查 MFN, 优先 longest prefix match."""
        norm = hs_code.replace(".", "").replace(" ", "")
        # 从最长 (10) 到最短 (6) 找
        for length in (10, 8, 6):
            if len(norm) < length:
                continue
            key = norm[:length].ljust(length, "0")
            if key in self._extra_mfn:
                return self._extra_mfn[key]
        return None

    def find(
        self,
        *,
        hs_code: str,
        origin: str = "CN",
        destination: str = "US",
        on: date | None = None,
    ) -> list[TariffMeasure]:
        """返回所有适用措施."""
        target = on or date.today()
        target_hs = hs_code.replace(".", "").replace(" ", "")
        origin_up = origin.upper()
        dest_up = destination.upper()

        results: list[TariffMeasure] = []
        for m in self._measures:
            # 1. HS 前缀匹配
            if not (m.hs_code == "000000" or target_hs.startswith(m.hs_code)):
                continue
            # 2. origin 匹配
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
