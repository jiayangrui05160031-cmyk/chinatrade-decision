# WTO Policy Support / 跨境政策决策支持

> 给中国制造业出口企业的"**HS 编码 × 美国市场**"决策支持工具。
> 聚焦 **中美贸易**:301 关税、232 钢铝、IEEPA 芬太尼税、Section 201/421 反倾销反补贴 + 商务部反制 + WTO 争端。

[![CI](https://github.com/jiayangrui05160031-cmyk/wto-policy-support/actions/workflows/ci.yml/badge.svg)](https://github.com/jiayangrui05160031-cmyk/wto-policy-support/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 这是什么?

> 一个 **开源** 的 Python 工具,回答这类问题:

> 我是广东中山的 LED 灯具厂,要把 HS 9405.40 的台灯出口到美国,现在 301 关税到底要加多少?
> 有没有 Section 301 排除窗口可以申请?现在到岸价客户会嫌贵吗?
> 商务部有没有对应的反制清单在美方原产地商品上?

**输入:** `HS 编码 (8-10 位)` + `目的国 US` + `单价` + `数量` + `FOB/CIF`  
**输出:** 决策卡 — MFN 关税 + 301 加征清单轮次 + 232 钢铝(若适用) + 反制提醒 + 豁免窗口 + 行动建议

## 当前状态

🚧 **MVP 开发中 (v0.1.0)**,完成度 0/26 tasks.

## 典型场景支持范围 (v0.1.0)**

| 方向 | 状态 | 覆盖政策 |
|------|------|----------|
| **🇺🇸 美国(主)** | 🔄 规划中 | USTR 301、Section 232 钢铝/汽车、IEEPA 芬太尼税、Section 201/421、CHIPS |
| **🇨🇳 美国→中国反制** | 🔄 规划中 | 商务部对美加征关税清单(16 批) |
| 🇪🇺 欧盟 | ⏸ 二期 | 150€ 免税取消、CBAM |
| 🇬🇧 UK | ⏸ 二期 | UK Global Tariff |
| 🌏 APEC | ⏸ 二期 | 区域协定 |

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/jiayangrui05160031-cmyk/wto-policy-support.git
cd wto-policy-support

# 2. 安装
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# 3. 跑测试
pytest

# 4. 启动 API
wto-api                          # http://localhost:8000/docs

# 5. 启动 Web UI
wto-web                          # http://localhost:8501
```

## 使用示例

```python
from wto_policy.core.decision_card import build_decision_card
from wto_policy.core.company_profile import CompanyProfile

profile = CompanyProfile(
    name="中山灯具厂",
    sector="灯具",
    main_destinations=["US"],
    trade_mode="general_trade",   # 走海运一般贸易
)

card = build_decision_card(
    hs_code="940540",
    destination="US",
    unit_value_usd=15.0,
    quantity=1000,
    profile=profile,
)

print(f"MFN 关税: ${card.base_duty:.2f}")
print(f"301 加征 (list 4A): {card.additional_duty_rate:.1%}")
print(f"单件总税负: ${card.total_tax / card.quantity:.2f}")
for alert in card.policy_alerts:
    print(f"⚠ {alert}")
for sug in card.suggestions:
    print(f"💡 {sug}")
```

## 数据源

所有数据来自 **官方/半官方源**,详见 [docs/data_sources.md](docs/data_sources.md)。

核心源:
- **HS 编码:** 中国海关 / WCO HS Master
- **海关税则:** EU TARIC / US HTSUS / UK Global Tariff
- **WTO:** Documents Online / Tariff & Trade Data
- **政策动态:** 商务部 / 海关总署 / EU Council / USTR 官方 RSS

任何数据条目都带 `source_url` + `crawled_at` 时间戳。

## 架构

```
src/
├── ingest/      # 抓取层:HS 库 / TARIC / HTSUS / 政策 RSS
├── core/        # 业务核心:HS 解析 / 关税计算 / 决策卡
├── api/         # FastAPI
├── web/         # Streamlit
├── cli/         # 命令行
└── update.py    # 数据更新入口
```

## 项目背景

**聚焦中美贸易。** 中国制造业出口企业面对的核心关税/政策层:

1. **USTR 301 关税** — 4 轮清单(34 亿美元 → 3700 亿美元),HS 码 100% 覆盖到 8 位
2. **Section 232 钢铝/汽车** — 部分豁免、部分到期
3. **IEEPA 芬太尼税** — 2025 年新增,中港特定行业
4. **Section 201/421** — 光伏、洗衣机、家具等单类产品保护
5. **中国反制** — 商务部 16 批对美加征关税清单
6. **WTO 争端** — 中国诉美 DS437、DS544、DS554、DS558 等

**目标:** 让一个出口企业主输入 HS 编码,30 秒内看清"我现在要交多少税、有哪些豁免窗口、商务部对应反制是什么"。

**其他方向**(欧盟 CBAM、UK、APEC) 二期再做,MVP 先打穿中美线。

## ⚠ 免责声明

本工具 **不构成法律/税务/报关意见**。
具体贸易活动请以各国海关、商务部门及您的报关行官方解释为准。
详见 [LICENSE](LICENSE) 末尾免责声明。

## 路线图 (中美专题)

- [x] 项目规划
- [ ] Task 1-3: 项目骨架 + CI
- [ ] Task 4-7: HS 编码库 (HTSUS 主表 + 中国海关对照)
- [ ] Task 8-11: 关税计算引擎 (HTSUS + USTR 301 加征 + Section 232)
- [ ] Task 12-13: 豁免窗口 + Section 301 排除延期跟踪
- [ ] Task 14-16: 政策态度 (USTR 公告 + 商务部反制清单 + WTO 争端 DS 案件)
- [ ] Task 17-20: 决策卡 + API
- [ ] Task 21-23: Streamlit UI
- [ ] Task 24-26: 文档 + 发布 v0.1.0

## 贡献

欢迎 PR!请先看 [CONTRIBUTING.md](CONTRIBUTING.md) (TODO)。

## 许可证

[MIT](LICENSE) + 末尾免责声明
