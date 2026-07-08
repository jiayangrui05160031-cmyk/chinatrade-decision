"""HS 编码解析、层级、模糊搜索.

设计目标:
- 离线优先(从本地 Parquet/SQLite 读,不强制在线)
- 6/8/10 位兼容
- 中文/英文描述模糊搜索
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from wto_policy.core.tariff_model import HsCode


class HsResolver:
    """HS 编码解析与查询.

    使用:
        resolver = HsResolver.from_parquet("data/processed/htsus.parquet")
        code = resolver.lookup("9405.40.80.00")
        results = resolver.search("LED lamp", lang="en", limit=10)
    """

    def __init__(self, codes: list[HsCode]) -> None:
        # 索引: code -> HsCode
        self._by_code: dict[str, HsCode] = {c.code: c for c in codes}
        # 索引: chapter -> codes
        self._by_chapter: dict[str, list[HsCode]] = {}
        for c in codes:
            self._by_chapter.setdefault(c.chapter, []).append(c)

    @classmethod
    def from_parquet(cls, path: str | Path) -> HsResolver:
        """从 Parquet 加载(留给 Task 5+)."""
        raise NotImplementedError("Task 5+")

    @classmethod
    def from_list(cls, codes: Iterable[HsCode]) -> HsResolver:
        return cls(list(codes))

    def normalize(self, raw: str) -> str:
        """归一化: 去点去空格. '9405.40.80.00' -> '9405408000'."""
        return raw.replace(".", "").replace(" ", "").strip()

    def lookup(self, code: str) -> HsCode | None:
        """精确查找(支持带点的输入)."""
        return self._by_code.get(self.normalize(code))

    def lookup_or_raise(self, code: str) -> HsCode:
        result = self.lookup(code)
        if result is None:
            msg = f"HS code not found: {code}"
            raise KeyError(msg)
        return result

    def parent(self, code: str) -> HsCode | None:
        """父级(10 -> 8 -> 6)."""
        h = self.lookup(code)
        if h is None or h.parent_code is None:
            return None
        return self._by_code.get(h.parent_code)

    def ancestors(self, code: str) -> list[HsCode]:
        """返回 [父, 祖父, ...]."""
        result: list[HsCode] = []
        current = self.lookup(code)
        while current is not None and current.parent_code is not None:
            parent = self._by_code.get(current.parent_code)
            if parent is None:
                break
            result.append(parent)
            current = parent
        return result

    def children(self, code: str) -> list[HsCode]:
        """子级(6 -> 8, 8 -> 10)."""
        target = self.normalize(code)
        return [c for c in self._by_code.values() if c.parent_code == target]

    def chapter(self, code: str) -> list[HsCode]:
        """同一章下所有编码."""
        h = self.lookup(code)
        if h is None:
            return []
        return list(self._by_chapter.get(h.chapter, []))

    def search(
        self,
        query: str,
        *,
        lang: str = "zh",
        limit: int = 10,
    ) -> list[HsCode]:
        """模糊搜索.

        排序逻辑 (重要!):
        1. 一级: 关键词在描述中出现的次数 (越多越相关)
        2. 二级: HS 编码长度 (越长越前 — 10 位先于 6 位, 粒度细 = 具体)

        这样搜 "蓝牙" 会优先返回 8518302000 (蓝牙耳机, 10 位) 而非 851830 (通用耳机, 6 位).
        搜 "耳机" 6 位 851830 应在前, 因为 6 位描述就含 "耳机".

        极简实现: 子串匹配, 不引入 jieba 之类依赖.
        - 中文: 拆 query 成单字/词, 任一字命中即可 (OR 匹配)
        - 英文: 拆分 word 后 AND 匹配 (所有 word 都必须在 desc 中)
        """
        query = query.strip().lower()
        if not query:
            return []

        candidates: list[tuple[HsCode, int, int, str]] = []
        if lang == "zh":
            # 中文 OR 匹配: query 中任一非空字符出现在 desc 中
            chars = [c for c in query if c.strip()]
            if not chars:
                return []
            for c_obj in self._by_code.values():
                desc = c_obj.description_zh.lower()
                count = sum(desc.count(ch) for ch in chars)
                if count > 0:
                    priority = (-count, -len(c_obj.code), c_obj.code)
                    candidates.append((c_obj, *priority))
        else:
            words = query.split()
            for c in self._by_code.values():
                desc = c.description_en.lower()
                if all(w in desc for w in words):
                    count = sum(desc.count(w) for w in words)
                    priority = (-count, -len(c.code), c.code)
                    candidates.append((c, *priority))
        candidates.sort(key=lambda x: (x[1], x[2], x[3]))
        return [c for c, *_ in candidates[:limit]]


@lru_cache(maxsize=1)
def default_resolver() -> HsResolver:
    """默认解析器(空). 真正数据从 update.py 加载后覆盖."""
    return HsResolver([])


__all__ = ["HsResolver", "default_resolver"]
