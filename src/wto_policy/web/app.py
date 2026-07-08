"""Streamlit 聊天式 UI — Agent 对话.

启动: wto-web
访问: http://localhost:8501

特点:
- 中文聊天界面
- 显示 agent 的工具调用过程(可展开)
- 显示决策卡(有工具调用结果时)
- 实时多轮对话
"""

from __future__ import annotations

import streamlit as st

from wto_policy.agent.agent import Agent, AgentRun


def _init_state() -> None:
    """初始化 session state."""
    if "agent" not in st.session_state:
        # 启动 agent 时会自动调一次 ensure_fresh (后台拉新)
        st.session_state.agent = Agent(auto_refresh=True)
    if "messages" not in st.session_state:
        st.session_state.messages = []  # list[dict(role, content, ...)]
    if "last_run" not in st.session_state:
        st.session_state.last_run = None
    if "freshness" not in st.session_state:
        from wto_policy.agent.refresh import freshness_report
        st.session_state.freshness = freshness_report()


def _render_turn(turn) -> None:  # type: ignore[no-untyped-def]
    """渲染一轮 agent 事件."""
    if turn.role == "assistant_text":
        with st.chat_message("assistant"):
            st.markdown(turn.content)
    elif turn.role == "tool_call":
        with st.chat_message("assistant"), st.status(
            f"🔧 调用 {turn.tool_name}", expanded=False
        ) as s:
            st.json(turn.tool_args or {})
            s.update(label=f"🔧 {turn.tool_name} 完成")
    elif turn.role == "tool_result":
        # 不单独显示 (在 status 里)
        pass
    elif turn.role == "final":
        with st.chat_message("assistant"):
            st.markdown(turn.content)
            st.caption("⚠ 本工具仅供参考, 不构成法律/税务意见")


def _render_run(run: AgentRun) -> None:
    """渲染一次完整 agent 运行."""
    for t in run.turns:
        _render_turn(t)


def _example_buttons() -> None:
    """侧栏示例问题."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💡 试试这些问题")
    examples = [
        "我家是中山的 LED 灯具厂, 要出口一批 LED 台灯到美国, 一单大概 5 万美金, 1000 个, 走海运一般贸易. 帮我算下要交多少税, 该不该接这单?",
        "HS 9405408000, 货值 17200 美元, 出口美国, 这批货要交多少关税?",
        "我要发货到美国, 多少钱?",
        "我是义乌小电商, 出口蓝牙耳机 (HS 8518302000) 到美国, 一单 25 美金一个, 100 个, 走国际快递. 这单要不要接?",
        "最近 Section 301 有什么新动作?",
    ]
    for ex in examples:
        if st.sidebar.button(ex[:40] + "...", key=ex, use_container_width=True):
            st.session_state.pending_input = ex


def main() -> None:
    st.set_page_config(
        page_title="WTO 政策 Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🤖 WTO 跨境政策 Agent")
    st.markdown(
        "**给中国制造业出口企业** — 用自然语言问, Agent 自动查 HS / 算税 / 找最新政策. "
        "底层 MiniMax + 4 个工具 (HS 搜索 / 关税查询 / 决策卡 / 政策实时搜索)."
    )

    _init_state()
    _example_buttons()

    # 实时性面板
    with st.sidebar:
        st.markdown("### 📡 实时数据")
        f = st.session_state.freshness
        st.metric("缓存条数", f["total_items"])
        is_fresh = f["is_fresh"]
        st.markdown(
            f"**状态:** {'🟢 新鲜' if is_fresh else '🟡 即将拉新'}"
        )
        for src, when in f["last_ago"].items():
            st.caption(f"  {src}: {when}")
        if st.button("🔄 立即拉新政策", use_container_width=True):
            with st.spinner("拉新中..."):
                from wto_policy.agent.refresh import ensure_fresh
                ensure_fresh(force=True, blocking=True)
                from wto_policy.agent.refresh import freshness_report
                st.session_state.freshness = freshness_report()
                st.success(f"已拉新! 当前缓存 {st.session_state.freshness['total_items']} 条")
                st.rerun()

    # 显示历史
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 输入
    prompt = st.chat_input("例: 我是中山灯具厂, 1000 个 LED 台灯出口美国, 5 万美金, 帮我看看")
    if st.session_state.get("pending_input"):
        prompt = st.session_state.pop("pending_input")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"), st.spinner("Agent 思考中..."):
            run = st.session_state.agent.run(prompt)
            st.session_state.last_run = run
            # 渲染过程
            for t in run.turns:
                _render_turn(t)
        st.session_state.messages.append({
            "role": "assistant", "content": run.final_message,
        })


if __name__ == "__main__":
    main()
