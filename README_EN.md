<p align="right"><a href="README.md">Chinese</a> | <strong>English</strong></p>

# WTO Cross-border Trade Policy Decision Support

> A decision-support tool for Chinese manufacturers exporting to the United States.
> Search HS codes → calculate tariffs → retrieve policy updates → generate a decision card → decide whether an order is commercially viable.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style](https://img.shields.io/badge/ruff-clean-brightgreen.svg)](https://github.com/astral-sh/ruff)

## What it does

In three lines:

1. Describe a product and order, such as “export USD 10,000 of LED lamps to the US.”
2. The system finds likely HS codes, calculates applicable duties, and retrieves current public policy information.
3. An AI agent returns a structured, source-aware decision card with risks and recommended actions.

Typical users include export manufacturers, cross-border sellers, and trade operations teams. The tool is designed to turn fragmented tariff and policy inputs into one auditable workflow.

## Core capabilities

| Capability | Description | Main source |
| --- | --- | --- |
| HS search | Natural-language product descriptions to 6/8/10-digit codes | USITC HTSUS |
| Tariff calculation | MFN, Section 301, Section 232, IEEPA, and landed-cost components | USTR and official notices |
| Decision cards | Risk assessment, alerts, cost breakdown, and recommended actions | Combined sources |
| AI agent | Natural-language orchestration across four tools | OpenAI-compatible LLMs |
| Recent policy | Federal Register notices within a configurable time window | Federal Register API |
| China customs | Temporary import-duty schedules and customs notices | gov.cn public documents |

## Quick start

### 1. Install

```bash
git clone https://github.com/jiayangrui05160031-cmyk/chinatrade-decision.git
cd chinatrade-decision

# uv is recommended; pip also works
uv venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows
uv pip install -e ".[dev]"
```

### 2. Configure an optional LLM provider

```bash
cp .env.example .env
```

The project supports OpenAI-compatible providers such as MiniMax, OpenAI, DeepSeek, Qwen, Zhipu, Ollama, and custom enterprise endpoints.

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-key

# Local example
# LLM_PROVIDER=ollama
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_MODEL=llama3.1:8b
```

Keep real credentials in `.env` or a secret manager and never commit them.

### 3. Refresh public trade data

```bash
wto-update
# or
python -m wto_policy.cloud_updater
```

The updater downloads and normalizes USITC tariff data, Section 301 material, Federal Register notices, and supported Chinese customs sources into local SQLite databases.

### 4. Choose an interface

| Interface | Command | Address/output |
| --- | --- | --- |
| Streamlit chat | `wto-web` | `http://localhost:8501` |
| REST API | `wto-api` | `http://localhost:8000/docs` |
| CLI lookup | `wto-lookup-hs 9405408000` | Terminal |

### 5. End-to-end demo

```bash
python tests/e2e_agent_demo.py
```

This exercises realistic export scenarios and verifies that the agent selects and chains the expected tools.

## Architecture

```text
Streamlit UI / REST API / CLI
              │
              ▼
        AI agent gateway
              │
     ┌────────┼────────┬─────────────────┐
     ▼        ▼        ▼                 ▼
search_hs  tariff  decision_card  recent_policy
     │        │        │                 │
     └────────┴────────┴─────────────────┘
              │
              ▼
USITC + USTR + Federal Register + gov.cn
              │
              ▼
       local SQLite cache
```

The main design goals are:

- offline-first reads after an initial refresh;
- graceful handling of source outages and malformed records;
- public and traceable data sources;
- deterministic tariff arithmetic outside the LLM;
- explicit source URL, crawl time, effective dates, and legal basis where available.

## Agent tools

| Tool | Responsibility |
| --- | --- |
| `search_hs_codes` | Rank likely HS codes from a product description |
| `lookup_tariff` | Calculate the tariff stack for an HS code and CIF value |
| `generate_decision_card` | Produce landed-cost, risk, and action outputs |
| `search_recent_policy` | Retrieve recent policy material and citations |

The agent follows multi-step rules: unknown products are searched before calculation, and complete order inputs lead to a decision card. Invalid values are returned as structured warnings/errors instead of being silently invented.

## Public data sources

| Data | Source | Access |
| --- | --- | --- |
| US tariff schedule | [USITC HTSUS](https://hts.usitc.gov/) | Published CSV and official tables |
| Section 301 | [USTR](https://ustr.gov/issue-areas/enforcement/section-301-investigations) | Public notices and lists |
| Chinese tariff material | [gov.cn](https://www.gov.cn/) and customs publications | Public HTML/PDF documents |
| US policy notices | [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1) | Public API |

Normalized records retain provenance fields such as `source_url`, `crawled_at`, `effective_from`, `effective_to`, and `legal_basis` when the source provides them.

## Example decision

For a USD 50,000 order of 1,000 LED lamps, a result can include:

```text
CIF value:        $50,000
Total tariff:     $10,450 (20.9%)
Tariff per unit:  $10.45
Landed value:     $60,450
Risk:             Section 301 high; IEEPA medium
Action:           review pricing and applicable exclusion procedures
```

Values depend on the selected HS code, effective policy dates, origin, and the latest normalized data.

## Testing

```bash
# Offline automated suite
pytest

# Chinese customs PDF parsing
pytest tests/test_china_pdf.py

# Explicit live-source tests
pytest -m network

# Accuracy evaluations
python tests/eval_v1.py
python tests/eval_v2.py
python tests/eval_v3.py

# Real LLM scenarios; consumes provider quota
python tests/e2e_agent_demo.py
```

CI checks formatting/lint, Python 3.11 and 3.12 tests, and package builds. The scheduled `refresh-policy` workflow runs the updater, commits a changed `data/cache/policies.db`, and safely exits when there is nothing new.

## Docker

```bash
# Streamlit, API, persistent data, and optional updater
docker compose up -d

# Standalone image
docker build -t wto-policy .
docker run -p 8501:8501 -p 8000:8000 --env-file .env wto-policy
```

## Automation

- `.github/workflows/ci.yml`: lint, tests, and build validation.
- `.github/workflows/refresh-policy.yml`: scheduled and manually triggered public-policy refresh.
- Local schedulers can run `wto-update` every six hours when GitHub Actions is not used.

## Project layout

| Path | Purpose |
| --- | --- |
| `src/wto_policy/` | Data ingestion, normalization, tariff logic, tools, agent, and interfaces |
| `tests/` | Unit, network, parser, evaluation, and end-to-end coverage |
| `data/` | Local normalized databases and generated cache |
| `.github/workflows/` | CI and policy refresh automation |
| `pyproject.toml` | Packaging, dependencies, commands, and tool configuration |

## Disclaimer

This project does **not** provide legal, tax, customs-brokerage, or investment advice. Confirm actual transactions with the relevant customs and commerce authorities, a qualified customs broker, and licensed counsel. Policies and tariff treatment can change after data is retrieved.

## License and acknowledgements

Released under the [MIT License](LICENSE), subject to the disclaimer included with the project.

Thanks to USITC, USTR, the Federal Register, Chinese public customs sources, and the open-source Streamlit, FastAPI, pdfplumber, Pydantic, and Python communities.
