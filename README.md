# WTO Policy Support / 跨境政策决策支持

> 给中国制造业出口企业的"按 HS 编码 × 目的国"决策支持工具。
> 把 **WTO 条文 + 各国海关税则 + 中国/进口国政策态度** 串成一张可查询的决策卡。

[![CI](https://github.com/jiayangrui05160031-cmyk/wto-policy-support/actions/workflows/ci.yml/badge.svg)](https://github.com/jiayangrui05160031-cmyk/wto-policy-support/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 这是什么?

一个 **开源** 的 Python 工具,回答这类问题:

> 我是义乌的小跨境电商,要把 25 欧元的蓝牙耳机寄到德国,2026-07-01 之后要交多少税?
> 欧盟 7 月新规到底是怎么收的?我应该走小包直邮还是转海外仓?CBAM 会不会影响我?

**输入:** `HS 编码` + `目的国` + `单价` + `贸易方式`  
**输出:** 决策卡 — 总税负、净到岸价、风险提示、政策警报、行动建议

## 当前状态

🚧 **MVP 开发中 (v0.1.0)**,完成度 0/26 tasks.

**典型场景支持范围:**

| 贸易方式 | 状态 | 备注 |
|---------|------|------|
| EU 小包直邮 (≤150€) | 🔄 规划中 | 7/1 新规覆盖 |
| 一般贸易 (海运/空运) | 🔄 规划中 | |
| 海外仓 (B2B 整柜) | 🔄 规划中 | |
| 美线 301 关税 | 🔄 规划中 | |

**支持的目的国(目标):** EU 27 国 + US + UK,二期扩展 APEC。

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
    name="义乌小李",
    sector="消费电子",
    main_destinations=["DE", "FR"],
    trade_mode="small_parcel",
    has_ioss=False,
)

card = build_decision_card(
    hs_code="851830",
    destination="DE",
    unit_value_eur=25.0,
    profile=profile,
)

print(f"总税负: €{card.total_tax:.2f}")
print(f"净到岸价: €{card.net_landed_cost:.2f}")
for alert in card.policy_alerts:
    print(f"⚠ {alert}")
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

跨境小电商 2026 年面对三重政策冲击:

1. **欧盟 2026-07-01** 取消 150€ 免税,小包统一征 3€ 固定关税
2. **CBAM 2026-01-01** 正式实施,180 种下游产品被覆盖
3. **美国 301 关税** 持续叠加

**目标:** 让一个不懂 WTO 条文的小企业主也能在 30 秒内看清自己的真实成本。

## ⚠ 免责声明

本工具 **不构成法律/税务/报关意见**。
具体贸易活动请以各国海关、商务部门及您的报关行官方解释为准。
详见 [LICENSE](LICENSE) 末尾免责声明。

## 路线图

- [x] 项目规划
- [ ] Task 1-3: 项目骨架 + CI
- [ ] Task 4-7: HS 编码库
- [ ] Task 8-11: 关税计算引擎
- [ ] Task 12-13: 小包/海外仓路径
- [ ] Task 14-16: 政策态度
- [ ] Task 17-20: 决策卡 + API
- [ ] Task 21-23: Streamlit UI
- [ ] Task 24-26: 文档 + 发布

## 贡献

欢迎 PR!请先看 [CONTRIBUTING.md](CONTRIBUTING.md) (TODO)。

## 许可证

[MIT](LICENSE) + 末尾免责声明
