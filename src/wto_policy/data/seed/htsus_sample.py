"""内嵌的 HTSUS 样例数据(MVP 离线用).

数据来源: USITC HTSUS (2026 Rev 3), 真实编码.
仅包含 chapter 85/94 少量代表性子目, 用于:
- CLI 默认查询 (wto-lookup-hs)
- 测试 fixtures
- API demo 场景

真实业务场景请用 `wto-update` 拉取完整 HTSUS 表.
"""

from __future__ import annotations

from wto_policy.core.tariff_model import HsCode

SAMPLE_HTSUS: list[HsCode] = [
    # Chapter 94 — Lamps and lighting fittings
    HsCode(
        code="940510",
        level=6,
        chapter="94",
        description_zh="枝形吊灯及天花板或墙壁上的其他电气照明装置(住宅用)",
        description_en="Chandeliers and other electric ceiling or wall lighting fittings",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="940520",
        level=6,
        chapter="94",
        description_zh="电气的台灯、书桌灯、床头灯或落地灯",
        description_en="Electric table, desk, bedside or floor-standing lamps",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="940530",
        level=6,
        chapter="94",
        description_zh="圣诞树用的灯具组",
        description_en="Lighting sets for Christmas trees",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="940540",
        level=6,
        chapter="94",
        description_zh="其他电灯及照明装置",
        description_en="Other electric lamps and lighting fittings",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="9405404000",
        level=10,
        parent_code="940540",
        chapter="94",
        description_zh="LED 灯条/灯带",
        description_en="LED strip lights",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="9405408000",
        level=10,
        parent_code="940540",
        chapter="94",
        description_zh="其他 LED 灯具(包括台灯、聚光灯)",
        description_en="Other LED lighting fixtures (incl. table lamps, spotlights)",
        source="usitc-htsus-2026",
    ),
    # 8518 — 音频设备
    HsCode(
        code="851830",
        level=6,
        chapter="85",
        description_zh="耳机(earphones)和耳塞(headphones)及其组合件",
        description_en="Headphones and earphones, whether or not combined with a microphone",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="8518302000",
        level=10,
        parent_code="851830",
        chapter="85",
        description_zh="蓝牙耳机",
        description_en="Bluetooth headphones",
        source="usitc-htsus-2026",
    ),

    # ====== Chapter 95 玩具 (Section 301 List 3, 25%) ======
    HsCode(
        code="950300",
        level=6,
        chapter="95",
        description_zh="玩具(塑料填充玩具/娃娃/拼图等)",
        description_en="Toys (plastic stuffed toys, dolls, puzzles, etc.)",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="9503000000",
        level=10,
        parent_code="950300",
        chapter="95",
        description_zh="塑料玩具",
        description_en="Plastic toys",
        source="usitc-htsus-2026",
    ),

    # ====== Chapter 72 钢铁 (Section 232, 25%) ======
    HsCode(
        code="720800",
        level=6,
        chapter="72",
        description_zh="铁或非合金钢的平板轧材,经热轧,未包层/未涂层",
        description_en="Flat-rolled products of iron or non-alloy steel, hot-rolled, not clad/coated",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="721049",
        level=6,
        chapter="72",
        description_zh="铁或非合金钢平板轧材,经镀层,宽度≥600mm",
        description_en="Flat-rolled iron/non-alloy steel, plated, width ≥ 600mm",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="722519",
        level=6,
        chapter="72",
        description_zh="其他合金钢平板轧材,经冷轧,宽度≥600mm",
        description_en="Other alloy steel flat-rolled, cold-rolled, width ≥ 600mm",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="730890",
        level=6,
        chapter="73",
        description_zh="其他钢铁结构件",
        description_en="Other structures of iron or steel",
        source="usitc-htsus-2026",
    ),

    # ====== Chapter 39 塑料 ======
    HsCode(
        code="392690",
        level=6,
        chapter="39",
        description_zh="其他塑料制品",
        description_en="Other articles of plastics",
        source="usitc-htsus-2026",
    ),

    # ====== Chapter 64 鞋类 (Section 301 List 3, 25%) ======
    HsCode(
        code="640419",
        level=6,
        chapter="64",
        description_zh="其他鞋类(橡胶/塑料外底,纺织鞋面)",
        description_en="Other footwear (rubber/plastic soles, textile uppers)",
        source="usitc-htsus-2026",
    ),
    HsCode(
        code="6404199000",
        level=10,
        parent_code="640419",
        chapter="64",
        description_zh="其他纺织鞋面运动鞋",
        description_en="Other textile-uppered athletic shoes",
        source="usitc-htsus-2026",
    ),
]


def load_sample() -> list[HsCode]:
    return list(SAMPLE_HTSUS)
