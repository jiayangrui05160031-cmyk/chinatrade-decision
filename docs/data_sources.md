# 数据源说明

> 本文档列出项目用到的 **所有** 数据源、URL、抓取方式、可靠度、更新频率、授权要求。
> 任何"新数据"PR 必须在本文档登记后才合并。

## 数据源可靠度分级

| 级别 | 定义 | 例子 |
|------|------|------|
| ⭐⭐⭐ 一手官方 | 各国政府/国际组织原始数据 | USTR、商务部、USITC |
| ⭐⭐ 半官方 | 行业协会、研究机构、官方授权媒体 | Peterson Institute, China Daily(转载原文) |
| ⭐ 行业 | 律师事务所、咨询公司、贸易服务商 | Baker McKenzie, KPMG Trade |
| ❌ 不采用 | 自媒体、二手解读、营销文 | — |

**原则:** 一手 > 半官方 > 行业,二手解读一律不直接作为数据。

---

## 1. HS 编码库

### 1.1 美国 HTSUS (主表, MVP 必须)
- **URL:** https://hts.usitc.gov/
- **API:** 官方 HTSUS 数据下载 (Excel + 修订说明)
- **可靠度:** ⭐⭐⭐
- **更新频率:** USITC 持续更新(年度大版本 + 月度修订)
- **授权:** 公开
- **抓取方式:** 月度下载 + 解析
- **存储路径:** `data/raw/htsus_<year>.xlsx` → `data/processed/htsus.parquet`
- **重要:** 8 位和 10 位统计位的 HTSUS 编码带 `*` 修饰,需保留

### 1.2 中国海关 HS 表
- **URL:** http://www.customs.gov.cn/
- **可靠度:** ⭐⭐⭐
- **更新频率:** 年度
- **授权:** 公开
- **抓取方式:** 年度下载 Excel
- **用途:** HTSUS ↔ 中国 HS 对照

### 1.3 WCO HS Master (国际 6 位)
- **URL:** http://www.wcoomd.org/en/topics/nomenclature/instrument-and-tools/hs-nomenclature-2022-edition.aspx
- **可靠度:** ⭐⭐⭐
- **更新频率:** 每 5 年大版本
- **授权:** WCO 注册可下载 PDF;简表公开
- **用途:** 跨体系 6 位锚点

---

## 2. 海关税则与具体税率

### 2.1 USTR Section 301 加征清单
- **URL:** https://ustr.gov/issue-areas/enforcement/section-301-investigations/section-301-china
- **可靠度:** ⭐⭐⭐
- **更新频率:** 不定期修订、排除窗口
- **数据:** 4 轮清单(List 1/2/3/4A/4B),每个 HS 10 位对应加征 %
- **抓取方式:** 抓 USTR 公告 + 关联 Federal Register
- **存储:** `data/raw/ustr301/`

### 2.2 Section 232 钢铝 / 汽车
- **URL:** https://www.commerce.gov/232
- **可靠度:** ⭐⭐⭐
- **重要:** 部分国家/产品豁免,需跟踪当前状态
- **抓取方式:** 抓联邦公告

### 2.3 IEEPA 芬太尼关税 (2025+)
- **URL:** USTR / Federal Register
- **可靠度:** ⭐⭐⭐
- **覆盖范围:** 中港特定 HS 子集
- **抓取方式:** 抓 Federal Register + USTR 公告

### 2.4 Section 201 / 421 / 太阳能洗衣机等
- **可靠度:** ⭐⭐⭐
- **抓取方式:** USITC 案件库

### 2.5 商务部对美加征关税清单(中国反制)
- **URL:** http://www.mofcom.gov.cn/
- **可靠度:** ⭐⭐⭐
- **更新频率:** 16 批
- **抓取方式:** 抓商务部公告

---

## 3. WTO 数据

### 3.1 WTO Documents Online
- **URL:** https://docs.wto.org/
- **API:** 有官方 API(需注册 key)
- **可靠度:** ⭐⭐⭐
- **用途:** 条文、争端、通知文件全文

### 3.2 WTO Tariff & Trade Data (TTD)
- **URL:** https://ttd.wto.org/
- **API:** 有 API
- **可靠度:** ⭐⭐⭐
- **用途:** WTO 成员方承诺关税(bound duty)与实际 MFN applied

### 3.3 WTO Disputes
- **URL:** https://www.wto.org/english/tratop_e/dispu_e/dispu_status_e.htm
- **API:** 有
- **可靠度:** ⭐⭐⭐
- **用途:** 中美相关 DS 案件时间线(DS437、DS544、DS554、DS558、DS580 等)

---

## 4. 政策动态(新闻/公告)

### 4.1 USTR 公告 (RSS / 新闻稿)
- **URL:** https://ustr.gov/about-us/policy-offices/press-office
- **可靠度:** ⭐⭐⭐
- **抓取方式:** RSS + 关键词过滤("Section 301" / "China")

### 4.2 USITC 案件库
- **URL:** https://www.usitc.gov/
- **可靠度:** ⭐⭐⭐
- **用途:** 反倾销/反补贴案件状态

### 4.3 商务部新闻 (中国)
- **URL:** http://www.mofcom.gov.cn/
- **可靠度:** ⭐⭐⭐

### 4.4 海关总署 (中国)
- **URL:** http://www.customs.gov.cn/
- **可靠度:** ⭐⭐⭐

### 4.5 Federal Register
- **URL:** https://www.federalregister.gov/
- **API:** 有
- **可靠度:** ⭐⭐⭐
- **用途:** 美国所有行政命令、关税公告原始文件

---

## 5. 数据快照策略

每次 `wto-update` 运行:
1. 在 `data/snapshots/<UTC 时间戳>/` 下生成完整 dump
2. 写入 SQLite `data/cache/wto.db`
3. 自动保留最近 8 个 snapshot,旧的删除
4. snapshot 内含 `manifest.json`,记录本次抓取的源 URL 列表 + 抓取耗时

## 6. 数据使用许可与免责声明

- 所有数据仅供研究/学习/决策参考
- 具体贸易活动以 **官方海关 + 报关行 + 律师** 解释为准
- 项目不提供法律意见
