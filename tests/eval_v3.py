"""准确度测试 v3 - 真实用户场景压力测试.

新增测试类别:
- 数字格式混乱 ("17,200 美元" / "17.2k USD" / "一单 5 万美金")
- 拼写错误 ("led台灯" / "bluethooth")
- 多产品对比 ("A 跟 B 哪个贵?")
- 反事实 ("如果不出口, 我会?")
- 隐含知识 ("美国对中国铝加多少税?") - 没具体 HS
- 政策时间线 ("2024 年 1 月到现在 301 变了什么?")
- 退税问题 ("IEEPA 退税怎么申请?")
- 计算 "最惠国" 含义
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

from wto_policy.agent.agent import Agent

# 20 个真实用户 query
EDGE_CASES = [
    # 数字格式
    ("我是中山灯具厂, 一单 17,200 美元, HS 9405408000 出口美国 关税多少", ["lookup_tariff"], "easy"),
    ("17.2k USD 的蓝牙耳机出口美国 关税多少 HS 8518302000", ["lookup_tariff"], "easy"),
    ("一单 5万美金 出口美国 LED 台灯 1000 个, 走海运", ["search_hs_codes", "lookup_tariff"], "medium"),
    # 拼写错误 (宽容度测试)
    ("bluethooth headphones 出口美国", ["search_hs_codes"], "medium"),
    ("led台灯 HS code", ["search_hs_codes"], "medium"),
    # 隐含知识 (用户不知道 HS)
    ("我家是深圳的, 卖消费电子, 主要出口美国, 现在什么政策最影响我?", ["search_recent_policy"], "hard"),
    # 比较型
    ("A 跟 B 哪个贵? A 是 HS 9405408000 CIF 17200, B 是 HS 8518302000 CIF 2500", ["lookup_tariff"], "medium"),
    # 政策时间线
    ("2024 年到现在 Section 301 税率有什么变化?", ["search_recent_policy"], "hard"),
    # 退税问题
    ("IEEPA 芬太尼税如果被法院推翻, 已缴的税能退吗?", ["search_recent_policy"], "hard"),
    # 极简
    ("MFN 是什么?", ["search_recent_policy"], "easy"),
    # 复杂场景
    ("我是义乌小电商, 100 单货每单 25 美元, 蓝牙耳机走国际快递到美国, 整体关税多少, 怎么申报最省", ["lookup_tariff", "generate_decision_card"], "hard"),
    # 隐含拒绝
    ("我家做军火, 能出口到美国吗?", ["search_recent_policy"], "hard"),
    # 多意图
    ("HS 8518302000 蓝牙耳机 出口美国 关税多少, 还有最近 301 有什么新政", ["lookup_tariff", "search_recent_policy"], "medium"),
    # 故意错 HS
    ("HS 9999999999 出口美国 关税多少", ["lookup_tariff"], "easy"),
    # 数字矛盾
    ("HS 9405408000 货值 -100 美元", ["lookup_tariff"], "easy"),
]


def test_agent_accuracy_v3() -> dict:
    """20 个真实场景 + 边界压力测试."""
    agent = Agent(max_steps=5)
    details = []
    for q, expected, difficulty in EDGE_CASES:
        t0 = time.time()
        try:
            run = agent.run(q)
            actual = run.tool_calls_made
            error = None
        except Exception as e:
            actual = []
            error = str(e)
        elapsed = time.time() - t0

        if not expected:
            score = 1.0 if not actual else 0.5
        else:
            score = sum(1 for e in expected if e in actual) / len(expected)
        details.append({
            "q": q[:50],
            "difficulty": difficulty,
            "expected": expected,
            "actual": actual,
            "score": score,
            "elapsed": round(elapsed, 1),
            "error": error,
        })

    by_diff = {}
    for d in details:
        by_diff.setdefault(d["difficulty"], []).append(d["score"])
    avg_by_diff = {k: round(statistics.mean(v), 3) for k, v in by_diff.items()}
    overall = round(statistics.mean(d["score"] for d in details), 3)

    # 错误率
    n_crash = sum(1 for d in details if d["error"])
    avg_latency = round(statistics.mean(d["elapsed"] for d in details), 1)

    return {
        "name": "agent_accuracy_v3",
        "overall": overall,
        "by_difficulty": avg_by_diff,
        "avg_latency_s": avg_latency,
        "crash_count": n_crash,
        "details": details,
    }


def main() -> None:
    print("=" * 70)
    print("准确度测试 v3 (20 个真实压力场景, 含边界 + 拼写 + 数字格式 + 隐含)")
    print("=" * 70)

    r = test_agent_accuracy_v3()
    print()
    print(f"整体: {r['overall']*100:.1f}%")
    print(f"按难度: {r['by_difficulty']}")
    print(f"平均延迟: {r['avg_latency_s']}s")
    print(f"崩溃数: {r['crash_count']}")
    print()
    print("失败案例 (score < 1.0):")
    for d in r["details"]:
        if d["score"] < 1.0:
            print(f"  [{d['difficulty']:6}] {d['score']*100:>3.0f}%  {d['q']}")
            print(f"    exp={d['expected']}  got={d['actual']}  err={d['error']}")

    out = ROOT / "data" / "eval_v3.json"
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2))
    print(f"\n报告: {out}")


if __name__ == "__main__":
    main()
