"""Agent 核心 — function-calling 循环 + 多轮反问 + 决策卡生成.

设计:
- 轻量手写循环, 不依赖 LangGraph
- 每次循环: LLM 看消息历史 -> 要么直接回答, 要么调工具
- 调工具后把结果塞回消息历史, 继续循环
- 最多 5 轮防无限循环
- 信息不全时主动反问
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from wto_policy.agent.llm_client import LlmClient, LlmMessage
from wto_policy.agent.tools import call_tool, get_tool_schemas

SYSTEM_PROMPT = """你是 **WTO 跨境政策决策助手**, 服务于中国制造业出口企业.

你的能力:
1. 理解用户用自然语言描述的产品 (例: "我家灯具厂要出货到美国, 一单大概 5 万美金")
2. 主动调工具查 HS 编码 / 关税 / 决策卡
3. 基于工具结果, 用中文给出 **具体可执行的建议**

工具使用规则:
- 不知道 HS 码 → 先调 `search_hs_codes` 让候选浮现
- 知道 HS 码 + 货值 → 调 `lookup_tariff` 看明细
- 完整场景 (HS + CIF + 数量 + 企业类型) → 调 `generate_decision_card`

反问规则:
- 缺 HS 码时, 调 `search_hs_codes` 后让用户从候选中确认
- 缺 CIF 货值或数量时, 主动问 (例: "CIF 大概多少美金? 多少件?")
- 缺目的国时, 默认 US, 但要在回答中说明

输出风格:
- 中文, 简洁, 数字精确
- 涉及法规必带依据 (例 "Section 301 List 4A 7.5%")
- 不确定时明确说 "建议核实", 不编造
- 末尾附免责声明: "本工具仅供参考, 不构成法律/税务意见"
"""


@dataclass
class AgentTurn:
    """一轮 agent 输出的事件."""

    role: str  # "assistant_text" | "tool_call" | "tool_result" | "final"
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None


@dataclass
class AgentRun:
    """一次完整 agent 运行的结果."""

    final_message: str
    turns: list[AgentTurn] = field(default_factory=list)
    tool_calls_made: list[str] = field(default_factory=list)


class Agent:
    """WTO 政策 Agent."""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        max_steps: int = 5,
        auto_refresh: bool = True,
    ) -> None:
        self.llm = llm or LlmClient()
        self.tools = get_tool_schemas()
        self.max_steps = max_steps
        self._auto_refresh = auto_refresh
        # 启动时触发一次后台拉新 (不阻塞)
        if auto_refresh:
            from contextlib import suppress

            from wto_policy.agent.refresh import ensure_fresh

            with suppress(Exception):
                ensure_fresh(force=False, blocking=False)

    def run(self, user_message: str, history: list[LlmMessage] | None = None) -> AgentRun:
        """运行一次 agent."""
        messages: list[LlmMessage] = list(history or [])
        if not any(m.role == "system" for m in messages):
            messages.insert(0, LlmMessage(role="system", content=SYSTEM_PROMPT))
        messages.append(LlmMessage(role="user", content=user_message))

        turns: list[AgentTurn] = []
        tool_calls: list[str] = []
        final = ""

        for _step in range(self.max_steps):
            resp = self.llm.chat(messages, tools=self.tools, tool_choice="auto")
            choice = resp["choices"][0]
            msg = choice["message"]

            # assistant 消息 (可能有 tool_calls)
            asst_kwargs: dict = {"role": "assistant", "content": msg.get("content") or ""}
            if msg.get("tool_calls"):
                asst_kwargs["tool_calls"] = msg["tool_calls"]
            messages.append(LlmMessage(**asst_kwargs))

            if msg.get("content"):
                turns.append(AgentTurn(role="assistant_text", content=msg["content"]))

            # 调工具
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    name = fn["name"]
                    try:
                        args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                    except json.JSONDecodeError:
                        args = {}
                    turns.append(AgentTurn(
                        role="tool_call", content="",
                        tool_name=name, tool_args=args,
                    ))
                    result_str = call_tool(name, args)
                    tool_calls.append(name)
                    turns.append(AgentTurn(
                        role="tool_result", content=result_str[:200] + ("..." if len(result_str) > 200 else ""),
                        tool_name=name,
                    ))
                    messages.append(LlmMessage(
                        role="tool", content=result_str, tool_call_id=tc["id"],
                    ))
                # 继续循环让 LLM 用工具结果回答
                continue

            # 没有 tool_calls, 收尾
            final = msg.get("content", "") or ""
            turns.append(AgentTurn(role="final", content=final))
            break
        else:
            # 超过 max_steps
            if not final:
                final = "抱歉, 这个问题我需要更多信息才能回答. 请告诉我 HS 编码、CIF 货值、目的国."
                turns.append(AgentTurn(role="final", content=final))

        return AgentRun(final_message=final, turns=turns, tool_calls_made=tool_calls)


__all__ = ["Agent", "AgentRun", "AgentTurn"]
