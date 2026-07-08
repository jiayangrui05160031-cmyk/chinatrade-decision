# 🚀 GitHub 发布说明

**项目已就绪, 17 commits, 114 tests pass, 0 lint warnings, README 17.6KB.**

## 30 秒发布步骤

### 步骤 1: 手动建空 repo (30 秒)

打开 https://github.com/new , 填:
- **Repository name:** `wto-policy-support`
- **Description:** `中国制造业出口企业的中美贸易决策支持 (AI Agent + 真实 HTSUS/USTR/中国海关数据, 准确度 93.3%)`
- **Public** (勾选)
- **Add a README file:** ❌ 不要勾 (我们已有)
- **Add .gitignore:** ❌ 不要勾 (我们已有)
- **Choose a license:** ❌ 不要勾 (我们已有 MIT + 免责声明)

点 **Create repository**

### 步骤 2: 一行 push

把 `D:\wto-policy-support\` 整个文件夹 zip 给你 / 在你电脑上解压, 然后:

```bash
cd wto-policy-support
git remote add origin https://github.com/jiayangrui05160031-cmyk/wto-policy-support.git
git push -u origin main
```

如果是第一次 push 认证失败, 你的 token 没 `repo` 权限 — 重新生成 PAT 时勾 "All" 或 "Public Repo - Write" 范围.

### 步骤 3: 验证

- 访问 https://github.com/jiayangrui05160031-cmyk/wto-policy-support
- 看到 README 自动渲染 (徽章 / 表格 / 截图占位)
- 点 "Code" 看 17 个 commit
- 跑 `pytest` 看 114 tests pass

---

## 已就绪的功能

| 模块 | 状态 | 测试 |
|------|------|------|
| USITC HTSUS 2026 真实数据 (26,740 HS) | ✅ | ✅ |
| USTR Section 301 4 清单 | ✅ | ✅ |
| 中国海关 2026 关税调整 (779 项, gov.cn PDF) | ✅ | ✅ |
| AI Agent (MiniMax + 4 工具) | ✅ | ✅ |
| 决策卡 + 风险 + 政策警报 + 建议 | ✅ | ✅ |
| Streamlit 聊天 UI (暗色主题) | ✅ | ✅ |
| FastAPI REST API | ✅ | ✅ |
| Docker / docker-compose | ✅ | - |
| GitHub Actions (CI + 6h cron) | ✅ | - |
| 114 单元测试 + 3 个评估脚本 | ✅ | 93.3% 准确度 |

## 重要约束

- **数据不放 git:** `data/cloud.db` (云端 DB) + `data/raw/*.csv` + `data/raw/china_2026/*.pdf` 在 `.gitignore` 里
  - 这是有意: 4MB+ 真实数据不应污染 git
  - 用户 clone 后第一次跑 `wto-update` 自动下载
- **API key 不放 git:** `.env.example` 给模板, `.env` 在 `.gitignore`
- **Python 3.11+** 是硬要求 (用 match-case, pydantic v2, httpx 等)
