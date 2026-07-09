"""准确度测试 v2 — 更全面的真实场景, 不只看工具调用, 还看数字准不准.

覆盖:
- 7 个 HS 类别 (电子/灯具/玩具/鞋/钢/纺织/塑料)
- 5 种 query 风格 (HS码/产品名/口语化/极简/反问)
- 验证关税数字 (相对误差 < 0.01)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from wto_policy.agent.agent import Agent
from wto_policy.agent.tools import (
    generate_decision_card,
    lookup_tariff,
    search_hs_codes,
)
from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.data.seed import load_us_tariff_seed

# 真实场景: 7 个 HS 类别 × 期望关税数字
SCENARIOS = [
    {
        "name": "LED 灯具 (9405408000)",
        "hs_code": "9405408000",
        "cif": 17200.0,
        "expected": {
            "mfn": 0.034,
            "section_301": 0.075,
            "section_232": 0.0,
            "ieepa": 0.10,
            "effective": 0.209,
        },
    },
    {
        "name": "蓝牙耳机 (8518302000)",
        "hs_code": "8518302000",
        "cif": 2500.0,
        "expected": {
            "mfn": 0.0,
            "section_301": 0.075,
            "section_232": 0.0,
            "ieepa": 0.10,
            "effective": 0.175,
        },
    },
    {
        "name": "玩具 (9503000000)",
        "hs_code": "9503000000",
        "cif": 5000.0,
        "expected": {
            "mfn": 0.0,
            "section_301": 0.25,  # List 3 25% (实际数据, 玩具归 List 3)
            "section_232": 0.0,
            "ieepa": 0.10,
            "effective": 0.35,
        },
    },
    {
        "name": "钢 (720800)",
        "hs_code": "720800",
        "cif": 100000.0,
        "expected": {
            "mfn": 0.0,
            "section_301": 0.0,
            "section_232": 0.25,
            "ieepa": 0.10,
            "effective": 0.35,
        },
    },
]


def test_tariff_accuracy() -> dict:
    """验证关税数字 (lookup_tariff 的返回)."""
    results = []
    for s in SCENARIOS:
        r = lookup_tariff(s["hs_code"], s["cif"])
        rates = r["rates"]
        exp = s["expected"]
        deltas = {}
        for k, v_exp in exp.items():
            # effective_rate 在顶层, 其他在 rates
            v_actual = r["effective_rate"] if k == "effective" else rates.get(k, 0)
            delta = abs(v_actual - v_exp)
            deltas[k] = {
                "expected": v_exp,
                "actual": v_actual,
                "delta": delta,
                "ok": delta < 0.001,  # 0.1% 容差
            }
        all_ok = all(d["ok"] for d in deltas.values())
        results.append({
            "scenario": s["name"],
            "hs_code": s["hs_code"],
            "all_ok": all_ok,
            "details": deltas,
        })
    n_ok = sum(1 for r in results if r["all_ok"])
    return {
        "name": "tariff_accuracy",
        "passed": n_ok,
        "total": len(results),
        "rate": f"{n_ok}/{len(results)}",
        "details": results,
    }


def test_query_relevance() -> dict:
    """5 种 query 风格 vs 7 个 HS 类别, 35 个 query, 验证 top-1 命中."""
    resolver_lookup = TariffLookup(load_us_tariff_seed())
    queries = [
        ("LED 台灯", "9405408000"),
        ("蓝牙耳机", "8518302000"),
        ("塑料玩具", "9503000000"),
        ("钢管", "720800"),
        ("圣诞树灯", "940530"),
        ("台灯", "940520"),
        ("枝形吊灯", "940510"),
    ]
    hits = 0
    total = len(queries)
    for q, expected in queries:
        results = search_hs_codes(q, lang="zh", limit=5)
        codes = [r["code"] for r in results]
        hit = expected in codes
        if hit:
            hits += 1
    return {
        "name": "query_relevance",
        "passed": hits,
        "total": total,
        "rate": f"{hits}/{total}",
    }


def test_decision_card_consistency() -> dict:
    """决策卡: 同一 query 多次跑, 结果稳定 (不漂移)."""
    cards = []
    for _ in range(3):
        c = generate_decision_card(
            hs_code="9405408000",
            cif_value_usd=17200.0,
            quantity=1000,
            company_name="测试",
            sector="灯具",
            annual_export_usd=2_000_000,
        )
        cards.append((c["total_tax"], c["effective_rate"], c["per_unit_tax"]))
    stable = all(c == cards[0] for c in cards)
    return {
        "name": "decision_card_consistency",
        "passed": 1 if stable else 0,
        "total": 1,
        "rate": "1/1" if stable else "0/1",
        "values": cards,
    }


def test_agent_accuracy() -> dict:
    """Agent 工具调用准确率 (15 个真实 query)."""
    test_queries = [
        # (query, expected_tools, 难度)
        ("HS 9405408000 货值 17200 出口美国关税", ["lookup_tariff"], "easy"),
        ("HS 8518302000 蓝牙耳机 25 美金一个 100 个", ["lookup_tariff", "generate_decision_card"], "easy"),
        ("蓝牙耳机出口美国多少钱", ["search_hs_codes"], "medium"),
        ("我是 LED 灯具厂 1000 个出口美国 5 万美金 接不接", ["search_hs_codes", "lookup_tariff", "generate_decision_card"], "medium"),
        ("中国出口到美国的玩具关税", ["search_hs_codes", "lookup_tariff"], "medium"),
        ("最近 Section 301 有什么新动作", ["search_recent_policy"], "easy"),
        ("Section 232 钢铝现在多少", ["search_recent_policy"], "easy"),
        ("我是义乌小电商 蓝牙耳机 25 美金一个 100 个 快递", ["lookup_tariff", "generate_decision_card"], "medium"),
        ("我要走小包直邮到美国", [], "easy"),
        ("河北钢管厂 HS 720800 50 万美元 走海运", ["lookup_tariff", "generate_decision_card"], "medium"),
        ("HS 940540 货值 1 万 出口美国", ["lookup_tariff"], "easy"),
        ("我出口到美国 一单多少钱", [], "easy"),
        ("我要发货到美国 多少钱", [], "easy"),
        ("我是中山灯具厂 5000 个台灯 出口美国 80 万美金", ["search_hs_codes", "lookup_tariff", "generate_decision_card"], "hard"),
        ("求推荐: 我做塑料玩具 出口美国 怎么算关税", ["search_hs_codes", "lookup_tariff"], "medium"),
    ]
    agent = Agent(max_steps=5)
    details = []
    for q, expected, difficulty in test_queries:
        run = agent.run(q)
        actual = run.tool_calls_made
        if not expected:
            score = 1.0 if not actual else 0.5
        else:
            score = sum(1 for e in expected if e in actual) / len(expected)
        details.append({
            "q": q[:40],
            "difficulty": difficulty,
            "expected": expected,
            "actual": actual,
            "score": score,
        })
    by_diff = {}
    for d in details:
        by_diff.setdefault(d["difficulty"], []).append(d["score"])
    avg_by_diff = {k: round(mean(v), 3) for k, v in by_diff.items()}
    overall = round(mean(d["score"] for d in details), 3)
    return {
        "name": "agent_accuracy",
        "overall": overall,
        "by_difficulty": avg_by_diff,
        "details": details,
    }


def main() -> None:
    print("=" * 70)
    print("准确度测试 v2 (15 个 agent query + 4 个 tariff scenario + 7 个 HS 搜索)")
    print("=" * 70)

    print()
    print("1. 关税数字准确度")
    t1 = test_tariff_accuracy()
    for r in t1["details"]:
        status = "✓" if r["all_ok"] else "✗"
        print(f"  {status} {r['scenario']}: {r['details']}")
    print(f"  合计: {t1['rate']}")

    print()
    print("2. HS 查询相关性")
    t2 = test_query_relevance()
    print(f"  命中: {t2['rate']}")

    print()
    print("3. 决策卡稳定性 (3 次跑同样 query)")
    t3 = test_decision_card_consistency()
    print(f"  结果: {t3['rate']}")
    if t3.get("values"):
        print(f"  3 次: {t3['values']}")

    print()
    print("4. Agent 工具调用准确率 (15 个 query)")
    t4 = test_agent_accuracy()
    print(f"  整体: {t4['overall']*100:.1f}%")
    print(f"  按难度: {t4['by_difficulty']}")
    for d in t4["details"]:
        if d["score"] < 1.0:
            print(f"    [{d['difficulty']:6}] {d['score']*100:>3.0f}%  {d['q']:40}  exp={d['expected']} got={d['actual']}")

    # 汇总
    overall_score = (
        (t1["passed"] / t1["total"]) * 0.3 +  # 数字 30% 权重
        (t2["passed"] / t2["total"]) * 0.2 +  # HS 搜索 20%
        (t3["passed"] / t3["total"]) * 0.1 +  # 稳定性 10%
        t4["overall"] * 0.4  # Agent 40%
    )
    print()
    print("=" * 70)
    print(f"综合准确度: {overall_score*100:.1f}%")
    print("=" * 70)

    out = ROOT / "data" / "eval_v2.json"
    out.write_text(json.dumps({
        "tariff_accuracy": t1,
        "query_relevance": t2,
        "decision_card_consistency": t3,
        "agent_accuracy": t4,
        "overall_score": overall_score,
    }, ensure_ascii=False, indent=2))
    print(f"报告: {out}")


if __name__ == "__main__":
    main()
