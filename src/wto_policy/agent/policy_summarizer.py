"""政策公告摘要 — 用 LLM 把英文公告/中文商务部通稿压成 50 字中文要点."""

from __future__ import annotations

from wto_policy.agent.llm_client import LlmClient, LlmMessage

SUMMARY_PROMPT = """你是中美贸易政策摘要员. 收到一条政策公告, 用中文写出不超过 80 字的要点.

要求:
- 保留法规/税率/HS 码/日期等具体数字
- 用"对华"或"对中"开头, 标明影响国
- 末尾不加任何解读, 不加免责声明 (上层会统一加)

公告:
---
{text}
---

80 字中文摘要:"""


def summarize(text: str, *, llm: LlmClient | None = None) -> str:
    """一段公告/政策文字 -> 80 字中文摘要."""
    if not text or not text.strip():
        return "(无摘要)"
    client = llm or LlmClient()
    prompt = SUMMARY_PROMPT.format(text=text[:3000])  # 截断
    return client.text(
        [LlmMessage(role="user", content=prompt)],
        temperature=0.2,
        max_tokens=200,
    ).strip()


__all__ = ["summarize"]
