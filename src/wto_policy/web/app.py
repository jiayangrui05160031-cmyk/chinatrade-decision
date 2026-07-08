"""Streamlit 主界面 — 中美贸易决策支持 dashboard.

启动: wto-web
访问: http://localhost:8501

特点:
- 中文界面, 暗色主题 (自定义 CSS)
- 顶部品牌区 + 实时数据状态
- 主面板: 商品输入 + 即时决策卡
- 侧栏: 实时数据 + 聊天入口 + 示例
- 聊天面板: AI Agent 自然语言对话
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# 启动时加载 .env (AppTest 也需要)
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

import streamlit as st

from wto_policy.agent.agent import Agent
from wto_policy.core.company_profile import CompanyProfile, TradeMode
from wto_policy.core.decision_card import DecisionCard
from wto_policy.core.tariff_lookup import TariffLookup
from wto_policy.data.seed import load_sample, load_us_tariff_seed

_LOOKUP = TariffLookup(load_us_tariff_seed())
_RESOLVER = None


def _resolver():  # type: ignore[no-untyped-def]
    global _RESOLVER
    if _RESOLVER is None:
        from wto_policy.core.hs_resolver import HsResolver
        _RESOLVER = HsResolver.from_list(load_sample())
    return _RESOLVER


def _load_css() -> None:
    """加载自定义 CSS."""
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>",
                    unsafe_allow_html=True)


def _init_state() -> None:
    if "agent" not in st.session_state:
        st.session_state.agent = Agent(auto_refresh=True)
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_card" not in st.session_state:
        st.session_state.last_card = None
    if "last_input" not in st.session_state:
        st.session_state.last_input = None
    if "freshness" not in st.session_state:
        from wto_policy.agent.refresh import freshness_report
        st.session_state.freshness = freshness_report()


def _render_risk_tag(level: str) -> str:
    """渲染风险等级标签 (HTML)."""
    label_map = {"low": "🟢 低", "medium": "🟡 中", "high": "🟠 高", "critical": "🔴 严重"}
    return f'<span class="risk-tag risk-{level}">{label_map.get(level, level)}</span>'


def _render_brand_header() -> None:
    """顶部品牌区."""
    st.markdown(
        """
        <div class="main-header">
            <h1>🌐 WTO 跨境政策决策支持</h1>
            <p>给中国制造业出口企业的"中美贸易"决策支持 · AI Agent · 实时政策数据</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_query_panel() -> DecisionCard | None:
    """主面板: 输入 + 即时决策卡."""
    st.markdown("### 🔍 查商品 & 算关税")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### 1️⃣ 产品信息")
        c1, c2 = st.columns(2)
        with c1:
            product_query = st.text_input(
                "产品名称 / HS 编码",
                value="LED 台灯",
                placeholder="例: LED 台灯 / HS 9405408000",
                key="product_query",
            )
        with c2:
            destination = st.selectbox(
                "目的国", ["US", "DE", "FR", "UK", "MX", "VN"],
                index=0, key="destination",
            )
    with col2:
        st.markdown("#### 2️⃣ 货值 & 数量")
        cif_value = st.number_input(
            "CIF 货值 (USD)", min_value=0.0, value=17200.0,
            step=100.0, key="cif_value",
        )
        quantity = st.number_input(
            "数量 (件)", min_value=1, value=1000, step=100, key="quantity",
        )

    # HS 码解析
    hs_code: str | None = None
    if product_query:
        if product_query.replace(".", "").replace(" ", "").isdigit():
            # 用户直接给了 HS 码
            hs_code = product_query.replace(".", "").replace(" ", "")
        else:
            # 自然语言描述, 搜候选
            resolver = _resolver()
            lang = "en" if product_query.isascii() and " " in product_query else "zh"
            results = resolver.search(product_query, lang=lang, limit=5)
            if results:
                options = [f"{h.code} — {h.description_zh}" for h in results]
                idx = st.selectbox(
                    f"识别到 {len(results)} 个 HS 编码候选, 请选择:",
                    range(len(options)),
                    format_func=lambda i: options[i],
                    key="hs_select",
                )
                hs_code = results[idx].code
                st.caption(f"📌 已选: {hs_code} ({results[idx].description_zh})")

    st.markdown("#### 3️⃣ 企业画像")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        company_name = st.text_input("企业名", value="中山 LED 灯具厂", key="company_name")
    with c2:
        sector = st.text_input("行业", value="灯具", key="sector")
    with c3:
        annual = st.number_input("年出口额 (USD)", min_value=0, value=2_000_000,
                                 step=100_000, key="annual")
    with c4:
        trade_mode = st.selectbox(
            "贸易方式", [m.value for m in TradeMode],
            format_func=lambda x: {
                "general_trade": "一般贸易",
                "express": "国际快递",
                "small_parcel": "小包直邮",
                "overseas_warehouse": "海外仓",
            }[x],
            index=0, key="trade_mode",
        )

    # 按钮
    col_btn1, col_btn2, _col_btn3 = st.columns([1, 1, 3])
    with col_btn1:
        calculate = st.button("🚀 算关税 + 出决策卡", type="primary",
                              use_container_width=True, key="btn_calc")
    with col_btn2:
        ask_agent = st.button("🤖 问 AI Agent", use_container_width=True, key="btn_agent")

    if calculate and hs_code:
        profile = CompanyProfile(
            name=company_name, sector=sector, annual_export_usd=annual,
            main_destinations=[destination], trade_mode=TradeMode(trade_mode),
        )
        try:
            card = DecisionCard.build(
                hs_code=hs_code, cif_value_usd=cif_value, quantity=quantity,
                destination=destination, profile=profile, lookup=_LOOKUP,
            )
            st.session_state.last_card = card
            st.session_state.last_input = {
                "product_query": product_query,
                "hs_code": hs_code,
                "destination": destination,
                "cif_value": cif_value,
                "quantity": quantity,
                "company": company_name,
                "sector": sector,
            }
        except Exception as e:
            st.error(f"决策卡生成失败: {e}")
            return None

    if ask_agent and hs_code:
        prompt = (
            f"我是{company_name}({sector}行业), 要出口{product_query} "
            f"(HS {hs_code}) 到{destination}, CIF {cif_value} 美元, 数量 {quantity} 件, "
            f"走{trade_mode}. 帮我算下要交多少税, 该不该接这单?"
        )
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"), st.spinner("Agent 思考中..."):
            run = st.session_state.agent.run(prompt)
            for t in run.turns:
                if t.role == "assistant_text":
                    st.markdown(t.content)
                elif t.role == "tool_call":
                    with st.status(f"🔧 调用 {t.tool_name}", expanded=False) as s:
                        st.json(t.tool_args or {})
                        s.update(label=f"🔧 {t.tool_name} 完成")
        st.session_state.messages.append({"role": "assistant", "content": run.final_message})

    return st.session_state.last_card


def _render_decision_card(card: DecisionCard) -> None:
    """渲染决策卡 (大区块)."""
    st.markdown("---")
    st.markdown("### 📊 决策卡")

    # 顶部 4 个核心指标
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("CIF 货值", f"${card.cif_value_usd:,.2f}")
    with c2:
        st.metric("总关税", f"${card.total_tax:,.2f}",
                  delta=f"实际税率 {card.effective_rate:.1%}")
    with c3:
        st.metric("净到岸价", f"${card.net_landed_cost:,.2f}")
    with c4:
        st.metric("单件分摊税", f"${card.per_unit_tax:.4f}")

    # 关税明细表
    st.markdown('<div class="section-header">💰 关税明细</div>', unsafe_allow_html=True)
    bd = card.breakdown
    detail_data = {
        "项目": ["MFN 普通税", "Section 301 加征", "Section 232 钢铝", "IEEPA 芬太尼", "其他"],
        "税率": [
            f"{bd.mfn / card.cif_value_usd:.2%}" if card.cif_value_usd else "0",
            f"{bd.section_301 / card.cif_value_usd:.2%}" if card.cif_value_usd else "0",
            f"{bd.section_232 / card.cif_value_usd:.2%}" if card.cif_value_usd else "0",
            f"{bd.ieepa / card.cif_value_usd:.2%}" if card.cif_value_usd else "0",
            f"{bd.other / card.cif_value_usd:.2%}" if card.cif_value_usd else "0",
        ],
        "金额 (USD)": [
            f"${bd.mfn:,.2f}",
            f"${bd.section_301:,.2f}",
            f"${bd.section_232:,.2f}",
            f"${bd.ieepa:,.2f}",
            f"${bd.other:,.2f}",
        ],
        "法规依据": [
            "HTSUS General Rate",
            next((line.legal_basis for line in bd.lines if line.measure_type.value == "section_301"), "—"),
            next((line.legal_basis for line in bd.lines if line.measure_type.value == "section_232"), "—"),
            next((line.legal_basis for line in bd.lines if line.measure_type.value == "ieepa"), "—"),
            "—",
        ],
    }
    st.table(detail_data)

    # 风险
    if card.risks:
        st.markdown('<div class="section-header">⚠ 风险</div>', unsafe_allow_html=True)
        for r in card.risks:
            st.markdown(
                f"{_render_risk_tag(r.level.value)} {r.message_zh}",
                unsafe_allow_html=True,
            )

    # 政策警报
    if card.policy_alerts:
        st.markdown('<div class="section-header">📢 政策警报</div>', unsafe_allow_html=True)
        for a in card.policy_alerts:
            st.warning(f"**[{a.code}]** {a.message_zh}")
            if a.source_url:
                st.caption(f"来源: {a.source_url}")

    # 建议
    if card.suggestions:
        st.markdown('<div class="section-header">💡 行动建议 (按优先级)</div>',
                    unsafe_allow_html=True)
        for s in sorted(card.suggestions, key=lambda x: x.priority):
            st.success(f"**[P{s.priority}]** {s.message_zh}")
            if s.action_url:
                st.caption(f"行动: {s.action_url}")

    # 来源
    with st.expander(f"🔗 数据来源 ({len(card.sources)} 条)"):
        for src in card.sources:
            st.markdown(f"- {src}")


def _render_chat_panel() -> None:
    """聊天面板: Agent 自然语言对话."""
    st.markdown("---")
    st.markdown("### 💬 AI Agent 对话")

    # 历史
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 输入
    if prompt := st.chat_input("例: 我是中山灯具厂, 1000 个 LED 台灯出口美国, 5 万美金, 帮我看看"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"), st.spinner("Agent 思考中..."):
            run = st.session_state.agent.run(prompt)
            for t in run.turns:
                if t.role == "assistant_text":
                    st.markdown(t.content)
                elif t.role == "tool_call":
                    with st.status(f"🔧 调用 {t.tool_name}", expanded=False) as s:
                        st.json(t.tool_args or {})
                        s.update(label=f"🔧 {t.tool_name} 完成")
        st.session_state.messages.append({"role": "assistant", "content": run.final_message})


def _render_sidebar() -> None:
    """侧栏: 实时数据 + 工具."""
    with st.sidebar:
        st.markdown("### 📡 实时数据")
        f = st.session_state.freshness
        st.metric("缓存条数", f["total_items"])
        is_fresh = f["is_fresh"]
        st.markdown(
            f"**状态:** {'🟢 新鲜' if is_fresh else '🟡 即将拉新'}"
        )
        for src, when in f["last_ago"].items():
            st.markdown(
                f'<div class="freshness-card">'
                f'<div class="source-name">{src}</div>'
                f'<div class="source-time">{when}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if st.button("🔄 立即拉新政策", use_container_width=True, key="btn_refresh"):
            with st.spinner("拉新中..."):
                from wto_policy.agent.refresh import ensure_fresh, freshness_report
                ensure_fresh(force=True, blocking=True)
                st.session_state.freshness = freshness_report()
                st.success(f"已拉新! 当前缓存 {st.session_state.freshness['total_items']} 条")
                st.rerun()

        st.markdown("---")
        st.markdown("### 💡 试试这些问题")
        examples = [
            "我家是中山 LED 灯具厂, 要出口美国, 一单 5 万美金, 1000 个, 走海运. 帮我算下要交多少税?",
            "HS 9405408000, 货值 17200 美元, 出口美国, 关税多少?",
            "最近 Section 301 有什么新动作?",
            "我是义乌小电商, 蓝牙耳机 (HS 8518302000) 出口美国, 25 美金一个, 100 个, 走国际快递. 接不接?",
            "我想知道中国出口到美国的玩具关税",
        ]
        for ex in examples:
            if st.button(f"💬 {ex[:35]}...", key=f"ex_{ex[:20]}", use_container_width=True):
                st.session_state.pending_input = ex
                st.rerun()

        if st.session_state.get("pending_input"):
            st.session_state.messages.append({
                "role": "user", "content": st.session_state.pop("pending_input"),
            })
            st.rerun()

        st.markdown("---")
        st.caption("🤖 AI: MiniMax-Text-01")
        st.caption("📦 数据: USTR + Federal Register + 商务部")
        st.caption("⚖ 不构成法律/税务意见")


def main() -> None:
    st.set_page_config(
        page_title="WTO 政策决策支持",
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _load_css()
    _init_state()
    _render_brand_header()

    # 主面板 (左) + 聊天面板 (右, tabs 切换)
    _render_sidebar()

    tab1, tab2 = st.tabs(["🔍 决策卡生成", "💬 AI Agent 对话"])
    with tab1:
        card = _render_query_panel()
        if card:
            _render_decision_card(card)
    with tab2:
        _render_chat_panel()

    st.markdown(
        '<div class="disclaimer">'
        "⚠ 免责声明: 本工具仅供研究/学习/决策参考, 不构成法律/税务/报关意见. "
        "具体贸易活动请以各国海关 + 报关行 + 律师官方解释为准."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
