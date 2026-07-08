"""Agent 能力.

- llm_client       MiniMax 客户端
- tools            Agent 可调用的工具(HS 搜索/关税查询/政策搜索/决策卡)
- intent           意图理解: 自然语言 -> HS 候选 + 提取目的国/货值
- policy_fetcher   实时政策抓取(USTR / Federal Register / 商务部 RSS)
- policy_summarizer LLM 总结公告
- agent            核心: function-calling 循环, 多轮反问, 决策卡生成
"""

from __future__ import annotations

__all__ = [
    "agent",
    "intent",
    "llm_client",
    "policy_fetcher",
    "policy_summarizer",
    "tools",
]
