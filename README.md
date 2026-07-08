# WTO Policy Support / 跨境政策决策支持 (AI Agent)

> 🤖 **AI Agent** 实时给中国制造业出口企业做"中美贸易"决策支持.
> 输入 HS 编码 × 目的国 × 货值, Agent 自动查 HS / 算税 / **拉最新政策** / 出建议.

[![CI](https://github.com/jiayangrui05160031-cmyk/wto-policy-support/actions/workflows/ci.yml/badge.svg)](https://github.com/jiayangrui05160031-cmyk/wto-policy-support/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Agent](https://img.shields.io/badge/agent-MiniMax%20LLM-blueviolet)](#-核心能力)

## 这是什么?

一个 **AI Agent** 回答这类问题:

> "我家是中山的 LED 灯具厂, 要出货到美国, 一单大概 5 万美金, 1000 个, 走海运. 帮我算下要交多少税, 该不该接这单?"

> "最近 Section 301 有什么新动作?"

Agent 会自动:
1. 调 `search_hs_codes` 找 HS 候选 → 让用户选
2. 调 `lookup_tariff` 算关税 (Section 301 + IEEPA + 232 + MFN)
3. 调 `search_recent_policy` **实时查 Federal Register** 拉最新政策
4. 调 `generate_decision_card` 出完整决策卡 (含风险/政策警报/建议)

## 📡 实时性

**Agent 的政策数据是实时的,不是写死的:**

- **缓存层** — SQLite 存已抓的公告 (`data/cache/policies.db`)
- **实时抓取** — Federal Register API / USTR RSS / 商务部 RSS
- **自动刷新** — Agent 启动时**后台线程**自动拉新 (24h 内不重复抓)
- **手动触发** — `wto-update` 命令 / Streamlit "立即拉新" 按钮
- **GitHub Actions cron** — 每 6 小时自动跑, 数据推回仓库

| 场景 | 速度 | 来源 |
|------|------|------|
| 缓存命中 | < 50ms | SQLite |
| 缓存 miss | 1-3 秒 | 实时 HTTP |
| 启动后第一次 query | 1-3 秒 | 实时 HTTP (后台拉) |
| 后续 query | < 50ms | 缓存 |

## 🎯 典型场景 (v0.1.0)

| 方向 | 状态 | 覆盖政策 |
|------|------|----------|
| **🇺🇸 美国(主)** | ✅ | USTR 301、Section 232 钢铝/汽车、IEEPA 芬太尼税、Section 201/421 |
| **🇨🇳 美国→中国反制** | ✅ | 商务部对美加征关税清单 |
| 🇪🇺 欧盟 | ⏸ v0.2 | 150€ 免税取消、CBAM |
| 🇬🇧 UK | ⏸ v0.2 | UK Global Tariff |

## 🚀 快速开始

### 1. 安装
```bash
git clone https://github.com/jiayangrui05160031-cmyk/wto-policy-support.git
cd wto-policy-support
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux
pip install -e ".[dev]"
```

### 2. 配置 LLM
```bash
cp .env.example .env
# 编辑 .env, 填入 MiniMax API key
```

### 3. 拉一次最新政策 (首次)
```bash
wto-update
# 或指定源:
wto-update --source federal_register --query "section 301"
```

### 4. 启动 (3 种方式)

#### 方式 A: 聊天 UI (推荐)
```bash
wto-web
# 浏览器打开 http://localhost:8501
```

#### 方式 B: REST API
```bash
wto-api
# 浏览器打开 http://localhost:8000/docs
```

#### 方式 C: CLI 速查
```bash
wto-lookup-hs 9405408000
wto-lookup-hs "bluetooth" --lang en
```

#### 方式 D: 端到端 demo (5 个真实场景)
```bash
python tests/e2e_agent_demo.py
```

## 💡 核心能力

| 能力 | 工具 | 说明 |
|------|------|------|
| HS 编码搜索 | `search_hs_codes` | 自然语言 → HS 候选 |
| 关税计算 | `lookup_tariff` | HS + CIF → 关税明细 (MFN/301/232/IEEPA) |
| 决策卡 | `generate_decision_card` | 风险/政策/建议 + 来源 |
| 实时政策 | `search_recent_policy` | 拉 Federal Register / USTR / 商务部 |

## 📊 真实场景示例

**用户:** "我家是中山的 LED 灯具厂, 要出货到美国, 一单大概 5 万美金, 1000 个, 走海运. 帮我看看?"

**Agent 行为:**
1. 调 `search_hs_codes` (中文 1 次 + 英文 1 次) → 给 4 个 HS 候选让用户确认
2. 用户: "用 9405408000"
3. 调 `lookup_tariff` → 算 MFN 3.4% + 301 List 4A 7.5% + IEEPA 10% = 20.9%
4. 调 `generate_decision_card` → 出完整卡

**用户:** "最近 Section 301 有什么新动作?"

**Agent 行为:**
1. 调 `search_recent_policy` (query="section 301")
2. 实时拉 Federal Register (2026-06-24 德国调查, 2026-06-03 越南 IP 调查, 2026-03-17 制造业产能)
3. 总结成 3 条带链接的要点

## 🏗️ 架构

```
src/wto_policy/
├── core/                  # 业务核心 (HS 解析, 关税计算, 决策卡)
│   ├── hs_resolver.py
│   ├── tariff_calc.py
│   └── decision_card.py
├── agent/                 # AI Agent
│   ├── llm_client.py      # MiniMax API 封装
│   ├── tools.py           # 4 个工具
│   ├── agent.py           # function-calling 循环
│   ├── policy_fetcher.py  # 实时抓 RSS/API
│   ├── policy_cache.py    # SQLite 缓存
│   ├── policy_summarizer.py  # LLM 摘要
│   ├── refresh.py         # 后台拉新
│   └── update.py          # CLI: wto-update
├── api/                   # FastAPI
├── web/                   # Streamlit 聊天 UI
├── cli/                   # CLI
└── data/seed/             # 内置种子数据
```

## 🧪 测试

```bash
pytest                  # 88 测试
pytest -m network       # 真实网络测试 (USTR/FR/商务部)
pytest -k agent         # 只跑 Agent 测试
```

## 📦 数据源

所有数据来自 **官方/半官方源**, 详见 [docs/data_sources.md](docs/data_sources.md):

- **HS 编码:** USITC HTSUS / 中国海关
- **海关税则:** Federal Register / USTR
- **政策动态:** USTR RSS / Federal Register API / 商务部 RSS

每条数据带 `source_url` + `crawled_at`, 永不入库不实数据.

## ⚠ 免责声明

本工具 **不构成法律/税务/报关意见**.
具体贸易活动请以各国海关 + 商务部门 + 报关行官方解释为准.
详见 [LICENSE](LICENSE) 末尾免责声明.

## 📝 License

MIT + 末尾免责声明
