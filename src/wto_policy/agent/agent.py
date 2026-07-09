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
from contextlib import suppress
from dataclasses import dataclass, field

from wto_policy.agent.llm_client import LlmClient, LlmMessage
from wto_policy.agent.memory import SessionMemory, memory_to_system_msg
from wto_policy.agent.tools import call_tool, get_tool_schemas

SYSTEM_PROMPT = """你是 **WTO 跨境政策决策助手**, 服务于中国制造业出口企业.

你的能力:
1. 理解用户用自然语言描述的产品 (例: "我家灯具厂要出货到美国, 一单大概 5 万美金")
2. 主动调工具查 HS 编码 / 关税 / 决策卡
3. 基于工具结果, 用中文给出 **具体可执行的建议**

工具使用规则 (重要! 必读):
- **不知道 HS 码 → 必须先调 `search_hs_codes`**, 不要直接反问. 给候选让用户确认.
- **已有 HS 码 + 货值 → 必须调 `lookup_tariff`**, 给出数字.
- **已有 HS 码 + 货值 + 数量 → 必须调 `generate_decision_card`**, 出完整卡.
- **用户问最新政策 / 动态 / 新闻 → 调 `search_recent_policy`**, query 用 "section 301" / "section 232" / "ieepa fentanyl" 这种英文关键词.

【多步调用规则 - 关键】:
- 一次回答中可以**调多个工具**, 不要停在第一步.
- 调完 search 拿到 HS 码, **立刻继续调** lookup_tariff 算税 (如果有货值).
- 调完 lookup 看到数字, **立刻继续调** generate_decision_card (如果有数量和行业).
- 完整链路: search → lookup → generate (3 步连调, 中间不停止).

判断信息是否齐全的规则:
- HS 码 + CIF 货值 → 够调 `lookup_tariff`
- HS 码 + CIF + 数量 + 行业 → 够调 `generate_decision_card` (公司名/行业可默认 "LED 灯具厂"/"消费电子")
- 缺 HS 码 + 缺货值 → 才反问. 缺一个时优先调工具补全, 不要反复问.

反问规则 (仅当真正信息缺失时):
- 缺 HS 码时, 调 `search_hs_codes` 后让用户从候选中确认 (不要直接文字问)
- 缺 CIF 货值或数量时, 可以反问, 但也接受用户说"大概 5 万美金"这种模糊数字
- 缺目的国时, 默认 US, 在回答中说明

【异常输入处理】:
- 负数货值 / 不存在的 HS 码 → **仍然调 lookup_tariff**, 工具会返回 _error / _warning 字段, 不要文字反问
- 拼写错误 (bluethooth / led台灯) → 仍然 search, 让工具兜底
- 隐含知识问题 ("MFN 是什么" / "301 政策变化") → 调 `search_recent_policy` 查政策
- 违规话题 (军火等) → 调 `search_recent_policy` 查出口管制, 不要文字拒绝
- 复杂算术 (100 单 × 25 美元) → 自己心算 (2500), 然后调 lookup_tariff

【数字格式识别】:
- "17,200" / "17200" / "17.2k" / "5 万美金" = 50000 美元
- 逗号分隔, 小写 k/m, 中文万/千 都要识别

【few-shot 示例 - 必须模仿】:
- 用户: "HS 9405408000 货值 -100 美元" → 你: 调 lookup_tariff, 然后告诉用户 _error "CIF 不能为负"
- 用户: "HS 9999999999 出口美国 关税多少" → 你: 调 lookup_tariff, 然后告诉用户 _warning "HS 码在 HTSUS 2026 中未找到"
- 用户: "我是义乌小电商, 100 单货每单 25 美元" → 你: 心算 2500, 调 lookup_tariff(cif=2500), 然后 generate_decision_card
- 用户: "HS 8518302000 关税多少, 还有最近 301 新政" → 你: 调 lookup_tariff, 调 search_recent_policy("section 301"), 然后综合回答

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


def _extract_pseudo_tool_call(content: str) -> tuple[str, dict] | None:
    """解析 LLM 文本中的伪 function call.

    MiniMax 兼容性问题: 有时 LLM 在 content 里写
        `functions.lookup_tariff({...})`  或  `<tool_call>{...}</tool_call>`
    而不走标准的 tool_calls 字段. 这里做兜底解析.

    Returns: (tool_name, arguments_dict) 或 None
    """
    import re
    if not content:
        return None

    # 模式 1: <tool_call>...</tool_call> (Qwen/Llama 风格)
    m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", content, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            name = data.get("name", "")
            args = data.get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            return name, args
        except (json.JSONDecodeError, KeyError):
            pass

    # 模式 2: functions.NAME({...}) 或 tools.NAME({...})
    m = re.search(r"(?:functions|tools)\.(\w+)\s*\(\s*(\{.*?\})\s*\)", content, re.DOTALL)
    if m:
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
            return name, args
        except json.JSONDecodeError:
            return None

    return None


class Agent:
    """WTO 政策 Agent."""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        max_steps: int = 4,
        auto_refresh: bool = True,
        memory: SessionMemory | None = None,
    ) -> None:
        self.llm = llm or LlmClient()
        self.tools = get_tool_schemas()
        self.max_steps = max_steps
        self._auto_refresh = auto_refresh
        self.memory = memory or SessionMemory()
        # 启动时触发一次后台拉新 (不阻塞)
        if auto_refresh:
            from contextlib import suppress

            from wto_policy.agent.refresh import ensure_fresh

            with suppress(Exception):
                ensure_fresh(force=False, blocking=False)

    @staticmethod
    def _sanitize_input(text: str, max_len: int = 2000) -> str:
        """清洗用户输入:
        - 截断超长 (max 2000 字符)
        - 保留 emoji, 去掉控制字符
        - 防止 SQL 注入相关字符 (虽然 SQLite 是参数化, 但多一层防护)
        """
        if not text:
            return ""
        # 截断
        if len(text) > max_len:
            text = text[:max_len] + "..."
        # 去掉控制字符 (保留 emoji 和中文)
        # \x00-\x08 \x0b \x0c \x0e-\x1f \x7f 是控制字符
        # emoji 在 \U0001F000+
        import re
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text.strip()

    def run(self, user_message: str, history: list[LlmMessage] | None = None) -> AgentRun:
        """运行一次 agent. 支持多轮 (memory 自动复用)."""
        # 输入清洗: 截断超长输入, 防止 DoS / 注入
        user_message = self._sanitize_input(user_message)
        if not user_message:
            return AgentRun(
                final_message="我没收到有效输入, 请重新描述你的产品 (例 '蓝牙耳机出口美国')?",
                turns=[AgentTurn(role="final", content="我没收到有效输入")],
            )

        # 多轮记忆: 从消息里提取 HS/货值/数量 + 注入上下文
        self.memory.update_from_user(user_message)
        memory_prompt = memory_to_system_msg(self.memory)

        messages: list[LlmMessage] = list(history or [])
        if not any(m.role == "system" for m in messages):
            base_system = SYSTEM_PROMPT
            if memory_prompt:
                base_system = base_system + "\n\n" + memory_prompt
            messages.insert(0, LlmMessage(role="system", content=base_system))
        messages.append(LlmMessage(role="user", content=user_message))

        turns: list[AgentTurn] = []
        tool_calls: list[str] = []
        final = ""

        for _step in range(self.max_steps):
            resp = self.llm.chat(messages, tools=self.tools, tool_choice="auto")
            choice = resp["choices"][0]
            msg = choice["message"]

            # 调试: 看 LLM 到底返回了什么
            if not msg.get("tool_calls"):
                content = msg.get("content", "")
                # 检测 LLM 是否在文本中输出了伪 function call (MiniMax 兼容性问题)
                pseudo = _extract_pseudo_tool_call(content)
                if pseudo is not None:
                    name, args = pseudo
                    # 把它包装成标准 tool_call
                    import uuid
                    msg = {
                        **msg,
                        "tool_calls": [{
                            "id": f"pseudo_{uuid.uuid4().hex[:8]}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args, ensure_ascii=False),
                            },
                        }],
                    }

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
            # 多轮记忆: 把最后那次工具结果存到 memory + 记 assistant 响应
            if tool_calls:
                for t in reversed(turns):
                    if t.role == "tool_result":
                        with suppress(json.JSONDecodeError, TypeError):
                            self.memory.last_tool_result = json.loads(t.content)
                        break
            self.memory.update_from_assistant(final)
            break
        else:
            # 超过 max_steps
            if not final:
                final = "抱歉, 这个问题我需要更多信息才能回答. 请告诉我 HS 编码、CIF 货值、目的国."
                turns.append(AgentTurn(role="final", content=final))

        return AgentRun(final_message=final, turns=turns, tool_calls_made=tool_calls)


__all__ = ["Agent", "AgentRun", "AgentTurn"]
