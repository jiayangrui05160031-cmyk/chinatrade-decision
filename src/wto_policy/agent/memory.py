"""Agent 多轮会话记忆.

策略:
- SessionMemory: 单次会话 (.run() 调用间共享)
- 跨 session 持久化到 data/cache/sessions.json
- 从记忆中提取: HS 码 / CIF / 数量 / 企业画像
- LLM 看到 history 后能直接引用
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SESSION_DIR = Path("data/cache/sessions")


def _extract_context(msg: str) -> dict:
    """从单条用户消息里提取关键参数.

    Returns: {hs_code, cif_value_usd, quantity, destination, hs_description}
    """
    ctx: dict = {}

    # HS 码 (6-10 位数字)
    hs = re.search(r"\b(\d{6,10})\b", msg)
    if hs:
        ctx["hs_code"] = hs.group(1)

    # CIF/货值/金额: 数字(可能跟 k/M/万/USD/$/美元 等)
    # 用两个 regex: "$数字" 或 "数字 + 货币"
    m = re.search(r"\$\s*(\d+(?:[,.\d]*))", msg)
    val_str = None
    if m:
        val_str = m.group(1)
    else:
        # 数字 + 货币单位
        m2 = re.search(
            r"(\d+(?:\.\d+)?)\s*(美元|USD|美金|k|K|M|万)",
            msg, re.I,
        )
        if m2:
            val_str = m2.group(1)
    if val_str:
        val = val_str.replace(",", "")
        try:
            v = float(val)
            # 单位处理 (看整体匹配)
            full = (m.group(0) if m else m2.group(0)).lower() if (m or m2) else ""
            if "万" in full:
                v *= 10000
            elif "k" in full:
                v *= 1000
            elif "m" in full and re.search(r"\d\s*m\b", full, re.I):
                v *= 1_000_000
            ctx["cif_value_usd"] = v
        except ValueError:
            pass

    # 数量 (N 件/N 个/1000 个)
    qty = re.search(r"(\d+)\s*(?:件|个|台|箱)", msg)
    if qty:
        ctx["quantity"] = int(qty.group(1))

    # 目的国
    dest = re.search(r"(?:发往|出口到|到|卖往)\s*(美国|德国|法国|UK|英国|MX|墨西哥|VN|越南|DE|FR|GB)", msg)
    if dest:
        ctx["destination"] = dest.group(1)

    return ctx


@dataclass
class SessionMemory:
    """单次会话记忆.

    字段:
    - hs_codes: 用户提过的 HS 码列表 (按时间)
    - cif_value_usd: 最后一次货值
    - quantity: 最后一次数量
    - destination: 目的国
    - company: 企业名
    - turns: 历史对话摘要 [{role, content}]
    - last_tool_result: 上次工具结果 (dict)
    """

    hs_codes: list[str] = field(default_factory=list)
    cif_value_usd: float | None = None
    quantity: int | None = None
    destination: str = "US"
    company: str | None = None
    turns: list[dict] = field(default_factory=list)
    last_tool_result: dict | None = None

    def update_from_user(self, msg: str) -> None:
        """从用户消息里提取关键参数."""
        ctx = _extract_context(msg)
        if "hs_code" in ctx and ctx["hs_code"] not in self.hs_codes:
            self.hs_codes.append(ctx["hs_code"])
        if "cif_value_usd" in ctx:
            self.cif_value_usd = ctx["cif_value_usd"]
        if "quantity" in ctx:
            self.quantity = ctx["quantity"]
        if "destination" in ctx:
            d = ctx["destination"]
            # 标准化
            m = {"美国": "US", "DE": "DE", "德国": "DE", "法国": "FR", "FR": "FR",
                 "英国": "GB", "UK": "GB", "GB": "GB", "墨西哥": "MX", "MX": "MX",
                 "越南": "VN", "VN": "VN"}
            self.destination = m.get(d, self.destination)

        self.turns.append({"role": "user", "content": msg, "ts": datetime.now(UTC).isoformat()})

    def update_from_assistant(self, msg: str) -> None:
        self.turns.append({"role": "assistant", "content": msg, "ts": datetime.now(UTC).isoformat()})

    def context_str(self) -> str:
        """生成给 LLM 看的"上次上下文"提示."""
        has_anything = any([
            self.hs_codes,
            self.cif_value_usd is not None,
            self.quantity is not None,
            self.last_tool_result is not None,
            self.company,
        ])
        if not has_anything:
            return ""
        parts = ["[SessionMemory 上文已提取:]"]  # type: ignore[list-item]
        if self.hs_codes:
            parts.append(f"HS 码: {', '.join(self.hs_codes[-3:])}")
        if self.cif_value_usd is not None:
            parts.append(f"CIF 货值: ${self.cif_value_usd}")
        if self.quantity is not None:
            parts.append(f"数量: {self.quantity}")
        if self.destination:
            parts.append(f"目的国: {self.destination}")
        if self.company:
            parts.append(f"企业: {self.company}")
        if self.last_tool_result:
            amt = self.last_tool_result.get("amount_usd", {}).get("total")
            rate = self.last_tool_result.get("effective_rate")
            if amt is not None and rate is not None:
                parts.append(f"上次算税: ${amt} ({rate:.1%})")
        return "\n".join(parts)


def memory_to_system_msg(mem: SessionMemory) -> str:
    """生成 system 提示的 'memory context' 段."""
    ctx = mem.context_str()
    if not ctx:
        return ""
    return (
        "你有会话记忆, 跨多轮对话:"
        + ctx
        + "\n\n回复时, 如果用户在当前消息没指定 HS/货值/数量, 用上面的记忆补充.\n"
        "如果记忆跟当前消息矛盾, 用当前消息的."
    )


# ============ 持久化到磁盘 (可选) ============

def save_memory(mem: SessionMemory, session_id: str = "default") -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    p = SESSION_DIR / f"{session_id}.json"
    p.write_text(json.dumps(asdict(mem), ensure_ascii=False, indent=2))
    return p


def load_memory(session_id: str = "default") -> SessionMemory:
    p = SESSION_DIR / f"{session_id}.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return SessionMemory(**data)
        except (json.JSONDecodeError, TypeError):
            pass
    return SessionMemory()


# ============ Self-test ============
if __name__ == "__main__":
    m = SessionMemory()
    m.update_from_user("我家 LED 灯具厂, HS 9405408000, 1 万美金, 1000 件, 到美国")
    m.update_from_user("如果改成 2000 件, 多少税?")
    print("=== 提取结果 ===")
    print("HS:", m.hs_codes)
    print("CIF:", m.cif_value_usd)
    print("Qty:", m.quantity)
    print("Dest:", m.destination)
    print()
    print("=== 给 LLM 的上下文 ===")
    print(memory_to_system_msg(m))


__all__ = ["SessionMemory", "load_memory", "memory_to_system_msg", "save_memory"]
