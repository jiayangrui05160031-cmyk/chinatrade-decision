"""多维度评估 + 调优报告生成器.

跑: python tests/eval_v1.py
产出: data/eval_v1.json (量化指标)
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from wto_policy.agent import policy_cache as cache
from wto_policy.agent.agent import Agent
from wto_policy.agent.tools import search_recent_policy
from wto_policy.core.hs_resolver import HsResolver
from wto_policy.data.seed import load_sample, load_us_tariff_seed


def main() -> None:
    results: dict = {}
    agent = Agent(max_steps=4)

    # ====== 维度 1: 工具调用准确率 ======
    print("=" * 70)
    print("维度 1: 工具调用准确率")
    print("=" * 70)

    test_queries = [
        ("HS 9405408000, 货值 17200 美元, 出口美国, 关税多少?", ["lookup_tariff"]),
        ("蓝牙耳机出口美国多少钱", ["search_hs_codes"]),
        ("我是 LED 灯具厂, 1000 个出口美国, 5 万美金, 接不接?", ["generate_decision_card"]),
        ("我出口到美国, 一单多少钱", []),
        ("最近 301 有什么新动作", ["search_recent_policy"]),
        ("HS 8518302000 蓝牙耳机, 单价 25 美元, 100 个", ["lookup_tariff", "generate_decision_card"]),
        ("我想知道中国出口到美国的玩具关税", ["search_hs_codes", "lookup_tariff"]),
        ("Section 232 钢铝现在多少", ["search_recent_policy"]),
        ("我要走小包直邮到美国", []),
        ("HS 940540, 货值 1 万美元, 出口美国", ["lookup_tariff"]),
    ]

    details = []
    for q, expected in test_queries:
        t0 = time.time()
        run = agent.run(q)
        elapsed = time.time() - t0
        actual = run.tool_calls_made
        if not expected:
            score = 1.0 if not actual else 0.5
        else:
            score = sum(1 for e in expected if e in actual) / len(expected)
        details.append({"q": q, "expected": expected, "actual": actual,
                        "score": score, "elapsed_s": round(elapsed, 1)})
        print(f"  {score*100:>3.0f}分  {q[:35]:35}  exp={expected} got={actual} ({elapsed:.1f}s)")

    avg = statistics.mean(d["score"] for d in details)
    results["tool_call_accuracy"] = round(avg, 3)
    results["tool_call_details"] = details
    print(f"\n  📊 工具调用准确率: {avg*100:.1f}%")

    # ====== 维度 2: 延迟 ======
    print()
    print("=" * 70)
    print("维度 2: 延迟")
    print("=" * 70)
    elapsed_list = [d["elapsed_s"] for d in details]
    results["latency"] = {
        "min_s": min(elapsed_list),
        "max_s": max(elapsed_list),
        "mean_s": round(statistics.mean(elapsed_list), 1),
        "p95_s": sorted(elapsed_list)[int(len(elapsed_list)*0.95)-1],
    }
    print(f"  min={min(elapsed_list):.1f}s max={max(elapsed_list):.1f}s "
          f"mean={statistics.mean(elapsed_list):.1f}s "
          f"p95={sorted(elapsed_list)[int(len(elapsed_list)*0.95)-1]:.1f}s")

    # ====== 维度 3: 缓存效果 ======
    print()
    print("=" * 70)
    print("维度 3: 缓存效果")
    print("=" * 70)
    cache.init_schema()
    for i in range(20):
        cache.upsert_items([{
            "source": "federal_register",
            "url": f"https://fr.gov/{i}",
            "title": f"Section 301 update {i}",
            "summary": "details",
            "published": "2026-07-01T00:00:00+00:00",
        }])
    t0 = time.time()
    cached_result = search_recent_policy("section 301", use_cache=True, limit_per_source=5)
    t_cached = time.time() - t0
    t0 = time.time()
    real_result = search_recent_policy("section 301", use_cache=False, limit_per_source=5)
    t_real = time.time() - t0

    if t_cached == 0:
        # 缓存空, 用 1ms 保底
        t_cached = 0.001
    results["cache"] = {
        "cached_ms": round(t_cached * 1000, 1),
        "real_ms": round(t_real * 1000, 1),
        "speedup": f"{t_real/t_cached:.0f}x",
    }
    print(f"  缓存: {t_cached*1000:.0f}ms ({len(cached_result)} 条)")
    print(f"  实时: {t_real*1000:.0f}ms ({len(real_result)} 条)")
    print(f"  加速: {t_real/t_cached:.0f}x")

    # ====== 维度 4: HS 搜索质量 ======
    print()
    print("=" * 70)
    print("维度 4: HS 搜索质量")
    print("=" * 70)
    resolver = HsResolver.from_list(load_sample())
    search_tests = [
        ("蓝牙耳机", "8518302000"),  # 10 位最具体
        ("led lamp", "9405408000"),  # 10 位最具体
        ("圣诞树灯", "940530"),
        ("台灯", "940520"),
        ("耳机", "851830"),
        ("蓝牙", "8518302000"),
        ("wireless earphone", "851830"),
        ("照明灯", "940540"),
        ("floor lamp", "940520"),
    ]
    hits = 0
    for q, expected in search_tests:
        lang = "en" if q.isascii() and " " in q else "zh"
        codes = [h.code for h in resolver.search(q, lang=lang, limit=5)]
        # 命中条件: 期望的 HS 码在返回列表里 (不一定是第 1)
        hit = expected in codes
        if hit:
            hits += 1
        print(f"  {'✓' if hit else '✗'} '{q}' -> {codes[:3]}  (期望 {expected} 在列表中)")
    results["hs_search"] = f"{hits}/{len(search_tests)}"
    print(f"\n  命中率: {hits/len(search_tests)*100:.0f}%")

    # ====== 维度 5: 种子数据覆盖 ======
    print()
    print("=" * 70)
    print("维度 5: 种子数据覆盖")
    print("=" * 70)
    hs = load_sample()
    tariffs = load_us_tariff_seed()
    results["seed"] = {
        "hs_codes": len(hs),
        "tariff_measures": len(tariffs),
        "hs_chapters": len({h.chapter for h in hs}),
    }
    print(f"  HS: {len(hs)} 条 (全 HTSUS ~18000)")
    print(f"  Tariff: {len(tariffs)} 条")
    print(f"  章节: {len({h.chapter for h in hs})} / 99")

    # ====== 维度 6: 异常路径 ======
    print()
    print("=" * 70)
    print("维度 6: 异常路径")
    print("=" * 70)
    edge = [
        ("空字符串", ""),
        ("emoji", "🎉🎊💥"),
        ("超长", "x" * 3000),
        ("注入", "'; DROP TABLE--"),
        ("数字", "12345"),
        ("None-ish", "   "),
    ]
    edge_results = []
    for name, q in edge:
        try:
            run = agent.run(q)
            s = f"OK ({len(run.final_message)} chars)"
        except Exception as e:
            s = f"CRASH: {type(e).__name__}: {e}"
        edge_results.append({"case": name, "status": s})
        print(f"  {name:15} -> {s}")
    results["edge_cases"] = edge_results

    # 保存
    out = ROOT / "data" / "eval_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print()
    print("=" * 70)
    print(f"报告: {out}")
    print(json.dumps({k: v for k, v in results.items()
                      if k not in ("tool_call_details", "edge_cases")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
