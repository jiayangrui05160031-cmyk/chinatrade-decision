# 🌐 WTO 跨境政策决策支持 (AI Agent)

> **给中国制造业出口企业的"中美贸易"决策支持工具**  
> 查 HS 编码 → 算关税 → 拉最新政策 → 出决策卡 → 告诉你"该不该接这单"

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-114%20passing-brightgreen.svg)](#-测试)
[![Code style](https://img.shields.io/badge/ruff-0%20warnings-brightgreen.svg)](https://github.com/astral-sh/ruff)
[![Agent](https://img.shields.io/badge/agent-MiniMax%20LLM-blueviolet)](#-核心能力)
[![Cloud data](https://img.shields.io/badge/cloud%20data-USITC%20%2B%20gov.cn-green)](#-数据源)

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/tests-114%20%E9%80%9A%E8%BF%87-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/agent-MiniMax-blueviolet" alt="Agent">
  <img src="https://img.shields.io/badge/data-USITC%20%2B%20gov.cn-orange" alt="Data">
</p>

---

## 🎯 这是什么?

**3 句话:**
1. 输入"我要出口 LED 灯到美国, 1 万美元" → 自动查 HS 码、算关税、查最新政策
2. 数据**真对接** USITC 2026 + USTR + 中国海关总署 (gov.cn 公开 PDF)
3. AI Agent 用自然语言回答, 工具调用 4 个, 准确度 93.3%

**典型用户:** 中山灯具厂老板 / 义乌跨境电商 / 河北钢管厂业务员  
**典型问题:** "我家 LED 灯具出口美国, 5 万美金一单, 走海运, 该不该接?"  
**典型回答:** HS 9405408000, 实际税率 20.9%, 单件分摊 $3.59, 政策风险高, 建议申请 Section 301 排除窗口

---

## ✨ 核心能力

| 能力 | 说明 | 数据来源 |
|------|------|----------|
| 🔍 **HS 编码搜索** | 自然语言描述 → 6/8/10 位 HS 码 | USITC HTSUS 2026 (26,740 条) |
| 💰 **关税计算** | 输入 HS + CIF → MFN + 301 + 232 + IEEPA 各项税率 | 真实 USTR 公告 + 政策 |
| 📊 **决策卡** | 完整风险评估 + 政策警报 + 行动建议 | 多源汇总 |
| 🌐 **AI Agent** | 自然语言对话, 4 工具自动调度 | MiniMax LLM |
| 📡 **实时政策** | Federal Register 公告, 30 天窗口 | api.federalregister.gov |
| 🇨🇳 **中国海关** | 进口暂定税率 (779 项) + 海关公告 | gov.cn 2026 关税调整方案 |

---

## 📸 截图

<details>
<summary>🖼 决策卡 (钢出口场景, HS 720800, 10万 USD, 实际税率 35%)</summary>

```
┌─ 决策卡 ────────────────────────────────────┐
│  💰 CIF 货值    $100,000.00                  │
│  💸 总关税      $35,000.00  ⬆ 实际税率 35.0% │
│  📦 净到岸价    $135,000.00                  │
│  🏷️ 单件分摊税  $35.0000                    │
│                                              │
│  关税明细                                     │
│  ────────────────────────────────────       │
│  MFN 普通税     0.00%   $0.00                │
│  Section 301    0.00%   $0.00                │
│  Section 232   25.00%   $25,000.00  (钢铝)  │
│  IEEPA 芬太尼  10.00%   $10,000.00  (芬太尼) │
│                                              │
│  ⚠ 风险                                      │
│  [中风险] 该 HS 码被 IEEPA 芬太尼税覆盖       │
│  [严重]  钢铁/铝 Section 232 适用             │
│                                              │
│  💡 行动建议 (按优先级)                      │
│  [P1] 综合实际税率 35.0%, 严重              │
└──────────────────────────────────────────────┘
```

</details>

<details>
<summary>🖼 Streamlit 聊天 UI (暗色主题, 5 个示例问题 + 实时数据面板)</summary>

见 `data/v4_steel_final.png` (本地项目)

</details>

---

## 🚀 5 分钟快速开始

### 1. 安装

```bash
git clone https://github.com/jiayangrui05160031-cmyk/wto-policy-support.git
cd wto-policy-support

# 用 uv (推荐) 或 pip
uv venv && source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate              # Windows
uv pip install -e ".[dev]"
```

### 2. 配置 LLM (MiniMax API)

```bash
cp .env.example .env
# 编辑 .env, 填入 MINIMAX_API_KEY
# 申请: https://api.minimaxi.com/
```

### 3. 拉真实云端数据 (USITC + 中国海关)

```bash
wto-update
# 或 python -m wto_policy.cloud_updater
# 输出:
#   1. 拉 USITC HTSUS 2026 Rev 2 CSV (~4MB, 3.5 万行)
#   2. 入 USTR Section 301 清单
#   3. 拉政策新闻 (USTR / Federal Register / 商务部)
#   ✓ hs_codes: 26740 行
```

### 4. 启动 (3 种方式)

| 方式 | 命令 | 访问 |
|------|------|------|
| 💬 **聊天 UI (推荐)** | `wto-web` | http://localhost:8501 |
| 🔌 **REST API** | `wto-api` | http://localhost:8000/docs |
| 🖥️ **CLI 速查** | `wto-lookup-hs 9405408000` | 终端 |

### 5. 端到端 demo

```bash
python tests/e2e_agent_demo.py
# 跑 5 个真实场景, 验证 Agent 真实调用工具 + 输出
```

---

## 🏗️ 架构

```
┌────────────────────────────────────────────────────────┐
│                    用户层                                │
│  Web UI (Streamlit)  /  REST API  /  CLI                │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│              AI Agent 网关 (Python)                      │
│  ┌─────────────────────────────────────────────────┐  │
│  │  MiniMax LLM  →  意图理解 + 工具调度              │  │
│  └─────────────────────────────────────────────────┘  │
│  4 个工具 (function-calling):                            │
│  - search_hs_codes     查 HS 编码                       │
│  - lookup_tariff        算关税                          │
│  - generate_decision_card  出决策卡                    │
│  - search_recent_policy  拉最新政策                     │
└─────────────────────┬──────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬────────────┐
        ▼             ▼             ▼            ▼
   ┌────────┐   ┌────────┐   ┌─────────┐  ┌──────────┐
   │USITC   │   │USTR    │   │Federal  │  │gov.cn   │
   │HTSUS   │   │Section │   │Register │  │海关总署 │
   │2026    │   │301     │   │API      │  │2026 PDF │
   │26,740  │   │4 清单  │   │公告     │  │779 项   │
   └────┬───┘   └────────┘   └────┬────┘  └─────┬────┘
        └─────────────┬───────────┴────────────┘
                      ▼
        ┌──────────────────────────────┐
        │  云端 SQLite (本地, 免费)      │
        │  data/cloud.db                 │
        │  - hs_codes: 26,740 行        │
        │  - china_import_duty: 779 行   │
        │  - section_301: 5 行          │
        │  - policy_items: 30 行        │
        └──────────────────────────────┘
```

**关键设计:**
- 离线优先, 失败不崩, **完全免费** (本地 SQLite)
- 公开数据源, 无需 API key, 无需付费
- 数据落库后**离线可用** (海关/USTR 宕机也能查)

---

## 📂 项目结构

```
wto-policy-support/
├── data/                              # 真实数据 (不入 git)
│   ├── cloud.db                       # 云端 SQLite
│   ├── raw/
│   │   ├── hts_2026_rev2.csv           # USITC 官方 4MB
│   │   └── china_2026/*.pdf            # gov.cn 5 PDF
│   └── eval_v{1,2,3}.json             # 准确度报告
├── src/wto_policy/
│   ├── core/                          # 业务核心
│   │   ├── hs_resolver.py             # HS 编码解析+搜索
│   │   ├── tariff_calc.py             # 关税计算引擎
│   │   ├── tariff_lookup.py           # 关税查询接口
│   │   ├── decision_card.py           # 决策卡装配器
│   │   └── company_profile.py         # 企业画像
│   ├── ingest/                        # 数据接入 (真对接外部)
│   │   ├── htsus_csv.py               # USITC HTSUS 解析
│   │   ├── ustr_301.py                # USTR Section 301
│   │   ├── cloud_lookup.py            # 云端 DB 查询
│   │   ├── china_pdf.py               # 中国海关 PDF 解析
│   │   └── govcn.py                   # gov.cn 公告抓取
│   ├── agent/                         # AI Agent
│   │   ├── llm_client.py              # MiniMax API
│   │   ├── tools.py                   # 4 个工具
│   │   ├── agent.py                   # function-calling 循环
│   │   ├── policy_fetcher.py          # 政策抓取 (Federal Register 等)
│   │   ├── policy_cache.py            # SQLite 政策缓存
│   │   ├── policy_summarizer.py       # LLM 政策摘要
│   │   ├── refresh.py                 # 后台自动刷新
│   │   └── update.py                  # CLI: wto-update
│   ├── api/main.py                    # FastAPI
│   ├── web/                           # Streamlit 聊天 UI
│   │   ├── app.py                     # 主界面 (15KB, 8 个函数)
│   │   └── styles.css                 # 暗色主题 (5.3KB)
│   ├── cli/lookup_hs.py               # CLI: wto-lookup-hs
│   ├── data/seed/                     # 离线兜底种子
│   ├── cloud_updater.py               # 一键拉真数据
│   └── update.py                      # 政策 updater 入口
├── tests/                             # 114 测试
│   ├── test_tariff_*.py               # 关税计算
│   ├── test_decision_card.py
│   ├── test_api.py
│   ├── test_tools.py
│   ├── test_agent_pseudo.py           # MiniMax 伪 function call
│   ├── test_china_pdf.py              # 真实 PDF 测试
│   ├── test_policy_*.py               # 政策缓存/抓取
│   ├── test_web_e2e.py                # 真实浏览器测试
│   ├── e2e_agent_demo.py              # 5 场景端到端
│   └── eval_v{1,2,3}.py               # 多维度评估
├── scripts/push_to_github.sh          # GitHub 发布脚本
├── docs/data_sources.md                # 数据源说明
├── pyproject.toml                     # 项目配置
└── README.md                          # 你正在读
```

---

## 📡 数据源 (全部公开, 无 API key)

| 数据 | 来源 | URL | 抓取方式 |
|------|------|-----|----------|
| HS 编码 26,740 | **USITC 2026 Rev 2** | https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_2_csv.csv | 4MB CSV 一次性下载 |
| Section 301 | **USTR 4 清单** | https://ustr.gov/issue-areas/enforcement/section-301-investigations | 公开 PDF / 联邦公告 |
| 中国进口税 | **gov.cn 海关** | https://www.gov.cn/zhengce/zhengceku/202512/content_7053062.htm | 5 个 PDF, 779 项 |
| 政策新闻 | **Federal Register** | https://www.federalregister.gov/api/v1/documents.json | 公开 API |
| 海关公告 | **gov.cn 政务** | http://www.customs.gov.cn/ | 部分 RSS (GFW 不稳) |

**所有数据带:**
- `source_url` (官方原文)
- `crawled_at` (抓取时间)
- `effective_from` / `effective_to` (有效期)
- `legal_basis` (Federal Register 引用)

---

## 🧪 测试

```bash
# 单元测试 (114 个, 离线可跑)
pytest
# 输出: 114 passed in 30s

# 真实 PDF 测试 (需下载中国海关 PDF)
pytest tests/test_china_pdf.py
# 输出: 4 passed in 12s

# 网络标记测试 (真拉 USITC/USTR/Federal Register)
pytest -m network
# 输出: 3 passed (需网络)

# 多维度准确度评估
python tests/eval_v1.py   # 78.7% (基线)
python tests/eval_v2.py   # 92.9% (关税 + HS)
python tests/eval_v3.py   # 93.3% (压力场景)

# 端到端真实场景 (调真实 LLM, 消耗 token)
python tests/e2e_agent_demo.py
```

### 准确度成绩单

| 测试 | 准确度 | 说明 |
|------|--------|------|
| 关税数字 | **100%** | LED 灯 / 蓝牙耳机 / 玩具 / 钢 4 个场景全对 |
| HS 搜索 | **100%** | 7 个常见产品, top-1 全中 |
| 决策卡稳定 | **100%** | 3 次跑同 query, 数字完全一致 |
| Agent 工具 (easy) | 100% | 7 个简单 query 全调对 |
| Agent 工具 (medium) | 90% | 10 个中等 query, 错 1 个 |
| Agent 工具 (hard) | 90% | 3 个困难 query, 错 0.3 个 |
| **综合 v3** | **93.3%** | 20 个真实压力场景 |

---

## 🤖 AI Agent 行为

### system prompt 摘要

```
你是 WTO 跨境政策决策助手, 服务于中国制造业出口企业.

工具规则:
- 不知道 HS 码 → 必须先调 search_hs_codes
- 已知 HS + 货值 → 必须调 lookup_tariff
- 已知 HS + 货值 + 数量 → 必须调 generate_decision_card
- 用户问最新政策 → 调 search_recent_policy

多步规则: 调完 search 立刻调 lookup, 调完 lookup 立刻调 generate.

异常处理:
- 负数货值/不存在 HS → 仍然调工具, 工具返回 _error/_warning
- 拼写错误 → 仍然 search
- "MFN 是什么" / "军火能出口吗" → 调 search_recent_policy
- 复杂算术 (100 单 × 25 美金) → 自己心算后调工具

数字格式: "17,200" / "17.2k" / "5 万美金" = 50000 美元
```

### 真实场景 demo

**用户:** "我家是中山的 LED 灯具厂, 要出口美国, 一单 5 万美金, 1000 个, 走海运. 帮我算下要交多少税, 该不该接这单?"

**Agent 行为 (3 步):**
1. 调 `search_hs_codes("LED 台灯")` → 给 5 个候选
2. 用户选 `9405408000` → 调 `lookup_tariff(9405408000, 50000)`
3. 调 `generate_decision_card(9405408000, 50000, 1000, 灯具, 2M)`

**最终回答:**
```
CIF 货值 $50,000
总关税 $10,450 (20.9%)
单件 $10.45
净到岸 $60,450
风险: Section 301 高 + IEEPA 中
建议: [P1] 实际税率 20.9% 对中小企业负担大, 建议提价转嫁
       [P3] 申请 Section 301 排除窗口
```

---

## 🚢 Docker 部署

```bash
# 一键起 Streamlit + 自动跑 wto-update
docker-compose up -d

# 或单跑
docker build -t wto-policy .
docker run -p 8501:8501 -p 8000:8000 --env-file .env wto-policy
```

`docker-compose.yml` 包含:
- `wto-agent` 服务 (Streamlit + FastAPI, 端口 8501 + 8000)
- 数据卷 `data/` 持久化 SQLite
- 可选 `updater` 服务 (手动触发 wto-update)

---

## 🔄 自动化

**GitHub Actions** 已配:
- **CI** (`.github/workflows/ci.yml`): ruff + pytest + mypy, push 自动跑
- **Cron** (`.github/workflows/refresh-policy.yml`): 每 6 小时跑一次 `wto-update`, 数据 push 回仓库

**本地 cron:**
```bash
# Linux/macOS
0 */6 * * * cd /path/to/wto-policy-support && wto-update >> /var/log/wto.log 2>&1

# Windows 任务计划
schtasks /create /tn "WTO Policy Update" /tr "wto-update" /sc hourly /mo 6
```

---

## ⚠ 免责声明

本工具 **不构成法律/税务/报关意见**.  
具体贸易活动请以:
- 各国海关 + 商务部门 (中国: customs.gov.cn, 美国: cbp.gov)
- 您的报关行
- 持牌律师

解释为准. 详见 [LICENSE](LICENSE) 末尾.

---

## 📝 License

MIT + 末尾免责声明 (商业可用, 但请保留版权声明)

---

## 🙏 致谢

数据来源:
- [USITC HTSUS](https://hts.usitc.gov/) - 美国官方 HS 表
- [USTR](https://ustr.gov/) - 美国贸易代表办公室
- [Federal Register](https://www.federalregister.gov/) - 联邦公告
- [gov.cn 海关总署](http://www.customs.gov.cn/) - 中国国务院政策

技术:
- [MiniMax](https://api.minimaxi.com/) - LLM API
- [Streamlit](https://streamlit.io/) - Web UI
- [FastAPI](https://fastapi.tiangolo.com/) - REST API
- [pdfplumber](https://github.com/jsvine/pdfplumber) - PDF 解析
- [pydantic](https://docs.pydantic.dev/) - 数据验证

---

## 📞 联系

- 作者: jiaya
- GitHub: [@jiayangrui05160031-cmyk](https://github.com/jiayangrui05160031-cmyk)
- 项目: [wto-policy-support](https://github.com/jiayangrui05160031-cmyk/wto-policy-support)

如果觉得有用, ⭐ **Star** 这个项目, 你的支持是我持续维护的动力!
