"""决策卡 PDF 导出器.

生成带品牌色 + 风险层级色彩的 PDF 报告, 给报关行/客户传.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from wto_policy.core.company_profile import CompanyProfile
from wto_policy.core.decision_card import DecisionCard

# 颜色
RISK_COLORS = {
    "low": colors.HexColor("#34d399"),
    "medium": colors.HexColor("#fbbf24"),
    "high": colors.HexColor("#f87171"),
    "critical": colors.HexColor("#ef4444"),
}
ACCENT_BLUE = colors.HexColor("#4f8cff")
ACCENT_PURPLE = colors.HexColor("#8b5cf6")
ACCENT_GREEN = colors.HexColor("#10b981")
GRAY_BG = colors.HexColor("#f1f5f9")
GRAY_TEXT = colors.HexColor("#64748b")


def _risk_color(level: str) -> colors.Color:
    return RISK_COLORS.get(level, GRAY_TEXT)


def _money(value: float) -> str:
    """$1,234.56 格式."""
    return f"${value:,.2f}"


def _register_cn_font() -> bool:
    """尝试注册中文字体. 失败回退 Helvetica (不显示中文)."""
    # 常见 Windows / macOS / Linux 中文字体路径
    candidates = [
        ("MicrosoftYaHei", ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf"]),
        ("SimHei", ["C:/Windows/Fonts/simhei.ttf"]),
        ("PingFang", ["/System/Library/Fonts/PingFang.ttc"]),
        ("NotoSansCJK", ["/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]),
    ]
    for name, paths in candidates:
        for p in paths:
            if Path(p).exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    return True
                except Exception:
                    continue
    return False


def _rate_pct(x: float) -> str:
    return f"{x * 100:.2f}%" if x else "—"


def generate_decision_card_pdf(
    card: DecisionCard,
    profile: CompanyProfile | None = None,
    output_path: str | Path | None = None,
) -> bytes | str:
    """生成 PDF 字节 (output_path 给则写文件并返回路径)."""
    cn_font = _register_cn_font()
    cn_font_name = "MicrosoftYaHei" if cn_font else "Helvetica"

    # 注册 cn bold
    if cn_font:
        for name, paths in [
            ("MicrosoftYaHei-Bold", [
                "C:/Windows/Fonts/msyhbd.ttc",
                "C:/Windows/Fonts/msyhbd.ttf",
            ]),
        ]:
            for p in paths:
                if Path(p).exists():
                    try:
                        pdfmetrics.registerFont(TTFont(name, p))
                        break
                    except Exception:
                        pass

    if output_path:
        doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                                leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)
    else:
        from io import BytesIO
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)
        output_path = None

    # styles
    base = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "H1", parent=base["Heading1"], fontName=cn_font_name,
        fontSize=22, textColor=ACCENT_BLUE, spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName=cn_font_name,
        fontSize=14, textColor=ACCENT_PURPLE, spaceBefore=12, spaceAfter=6,
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName=cn_font_name,
        fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "Small", parent=body, fontSize=8, textColor=GRAY_TEXT,
    )

    story: list = []
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # 标题
    story.append(Paragraph("🌐 WTO 跨境政策决策支持 · 决策卡报告", h1))
    story.append(Paragraph(
        f"<font color='#64748b'>生成时间: {now} · "
        f"基于 HTSUS 2026 Rev 2 + USTR + Federal Register 真数据</font>",
        small,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # 公司信息
    if profile:
        story.append(Paragraph("📋 企业信息", h2))
        info_data = [
            ["企业名", profile.name],
            ["行业", profile.sector],
            ["年出口额", _money(profile.annual_export_usd)],
            ["目的国", ", ".join(profile.main_destinations)],
            ["贸易方式", profile.trade_mode.value if hasattr(profile.trade_mode, "value") else str(profile.trade_mode)],
        ]
        info_table = Table(info_data, colWidths=[3 * cm, 12 * cm])
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), GRAY_BG),
            ("TEXTCOLOR", (0, 0), (0, -1), GRAY_TEXT),
            ("FONT", (0, 0), (-1, -1), cn_font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.5 * cm))

    # 核心指标
    story.append(Paragraph("📊 核心指标", h2))
    metrics_data = [[
        Paragraph("<b>CIF 货值</b><br/><font size='14' color='#4f8cff'>" + _money(card.cif_value_usd) + "</font>", body),
        Paragraph("<b>总关税</b><br/><font size='14' color='#ef4444'>" + _money(card.total_tax) + "</font><br/>" +
                  f"<font size='8' color='#64748b'>实际 {card.effective_rate:.1%}</font>", body),
        Paragraph("<b>净到岸价</b><br/><font size='14' color='#10b981'>" + _money(card.net_landed_cost) + "</font>", body),
        Paragraph("<b>单件分摊</b><br/><font size='14'>" +
                  (f"${card.per_unit_tax:.4f}" if card.per_unit_tax else "—") + "</font>", body),
    ]]
    metrics_table = Table(metrics_data, colWidths=[4.25 * cm] * 4)
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRAY_BG),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.5 * cm))

    # 数据时效 (如果有)
    if card.data_freshness:
        story.append(Paragraph(
            f"📡 <b>数据时效</b>: 来自 {card.data_freshness.get('source', '—')}, "
            f"截至 {card.data_freshness.get('crawled_at', '—')} "
            f"<font color='#10b981'>({card.data_freshness.get('age_human', '—')})</font>",
            body
        ))
        story.append(Spacer(1, 0.3 * cm))

    # HS + 货量
    story.append(Paragraph("📦 商品信息", h2))
    story.append(Paragraph(
        f"<b>HS 编码</b>: <font face='Courier'>{card.hs_code}</font> &nbsp;&nbsp; "
        f"<b>数量</b>: {card.quantity} &nbsp;&nbsp; "
        f"<b>原产</b>: {card.origin} → <b>目的</b>: {card.destination}",
        body,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # 关税明细表
    story.append(Paragraph("💰 关税明细", h2))
    bd = card.breakdown
    rate_pct = _rate_pct
    detail_rows = [
        ["项目", "税率", "金额", "法规依据"],
        [
            "MFN 普通税",
            rate_pct(bd.mfn / card.cif_value_usd if card.cif_value_usd else 0),
            _money(bd.mfn),
            "HTSUS General Rate",
        ],
        [
            "Section 301 加征",
            rate_pct(bd.section_301 / card.cif_value_usd if card.cif_value_usd else 0),
            _money(bd.section_301),
            next((line.legal_basis for line in bd.lines if line.measure_type.value == "section_301"), ""),
        ],
        [
            "Section 232 钢铝",
            rate_pct(bd.section_232 / card.cif_value_usd if card.cif_value_usd else 0),
            _money(bd.section_232),
            next((line.legal_basis for line in bd.lines if line.measure_type.value == "section_232"), ""),
        ],
        [
            "IEEPA 芬太尼",
            rate_pct(bd.ieepa / card.cif_value_usd if card.cif_value_usd else 0),
            _money(bd.ieepa),
            next((line.legal_basis for line in bd.lines if line.measure_type.value == "ieepa"), ""),
        ],
        [
            "<b>合计</b>",
            f"<b>{card.effective_rate * 100:.2f}%</b>",
            f"<b>{_money(card.total_tax)}</b>",
            "",
        ],
    ]
    detail_table = Table(detail_rows, colWidths=[3 * cm, 3 * cm, 3 * cm, 8 * cm])
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), cn_font_name),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, -1), (-1, -1), ACCENT_PURPLE),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONT", (0, 1), (-1, -1), cn_font_name),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.5 * cm))

    # 风险
    if card.risks:
        story.append(Paragraph("⚠ 风险", h2))
        risk_rows = [["等级", "说明"]]
        for r in card.risks:
            level_emoji = {
                "low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"
            }.get(r.level.value, "•")
            risk_rows.append([
                Paragraph(
                    f"<font color='{_risk_color(r.level.value).hexval()}'>"
                    f"<b>{level_emoji} {r.level.value.upper()}</b></font>",
                    body
                ),
                Paragraph(r.message_zh, body),
            ])
        risk_table = Table(risk_rows, colWidths=[3 * cm, 14 * cm])
        risk_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), cn_font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), GRAY_BG),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 0.5 * cm))

    # 政策警报
    if card.policy_alerts:
        story.append(Paragraph("📢 政策警报", h2))
        for a in card.policy_alerts:
            story.append(Paragraph(
                f"<b>[{a.code}]</b> {a.message_zh}", body
            ))
            if a.source_url:
                story.append(Paragraph(
                    f"<font color='#4f8cff'><u>{a.source_url}</u></font>", small
                ))
            story.append(Spacer(1, 0.2 * cm))

    # 建议
    if card.suggestions:
        story.append(Paragraph("💡 行动建议", h2))
        for s in sorted(card.suggestions, key=lambda x: x.priority):
            story.append(Paragraph(
                f"<b>[P{s.priority}]</b> {s.message_zh}", body
            ))
            if s.action_url:
                story.append(Paragraph(
                    f"<font color='#4f8cff'><u>{s.action_url}</u></font>", small
                ))
            story.append(Spacer(1, 0.2 * cm))

    # 数据来源
    if card.sources:
        story.append(Paragraph("🔗 数据来源", h2))
        for src in card.sources:
            story.append(Paragraph(f"• <font color='#64748b'>{src}</font>", small))

    # 免责声明
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        "⚠ <i>免责声明: 本报告由 WTO Policy Support 自动生成, 仅供研究/学习/决策参考. "
        "不构成法律/税务/报关意见. 具体贸易活动请以各国海关 + 报关行 + 律师官方解释为准.</i>",
        small
    ))

    doc.build(story)

    if output_path:
        return str(output_path)
    else:
        return buf.getvalue()


__all__ = ["generate_decision_card_pdf"]
