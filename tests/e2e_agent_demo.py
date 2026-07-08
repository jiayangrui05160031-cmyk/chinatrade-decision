"""端到端 Agent 真实场景测试 — 模拟用户对话.

跑: python -m tests.e2e_agent_demo
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from wto_policy.agent.agent import Agent


SCENARIOS = [
    (
        "场景 1: 模糊描述 (无 HS 码, 无具体货值)",
        "我家是中山的 LED 灯具厂, 要出货到美国, 一单大概 5 万美金, 1000 个, 走海运. 帮我看看?",
    ),
    (
        "场景 2: 给定 HS 码, 问税率",
        "HS 9405408000, 货值 17200 美元, 出口美国, 这批货要交多少关税?",
    ),
    (
        "场景 3: 信息严重不足, 期望主动反问",
        "我要发货到美国, 多少钱?",
    ),
    (
        "场景 4: 完整场景, 期望调 generate_decision_card",
        "我是义乌小电商, 出口蓝牙耳机 (HS 8518302000) 到美国, 一单 25 美金一个, 100 个, 走国际快递. 这单要不要接?",
    ),
    (
        "场景 5: 询问最新政策",
        "最近 Section 301 有什么新动作?",
    ),
]


def main() -> None:
    print("=" * 70)
    print("WTO 政策 Agent — 端到端真实场景测试")
    print("=" * 70)

    agent = Agent(max_steps=5)

    for i, (title, user_msg) in enumerate(SCENARIOS, 1):
        print(f"\n{'─' * 70}")
        print(f"{title}")
        print(f"  用户: {user_msg}")
        print(f"{'─' * 70}")

        run = agent.run(user_msg)

        # 工具调用轨迹
        if run.tool_calls_made:
            print(f"  Agent 调了: {', '.join(run.tool_calls_made)}")
        else:
            print("  Agent 没调工具 (纯回答)")

        print()
        print("  Agent 最终回答:")
        for line in run.final_message.split("\n"):
            print(f"  │ {line}")

    print(f"\n{'=' * 70}")
    print("✓ 端到端测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
