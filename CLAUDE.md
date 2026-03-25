# CLAUDE.md — AAOP Navigation Index
> **Claude Code bu dosyayı HER PROMPT'TA okur. Asla büyütme — sadece pointer'lar burada.**
> Versiyon: 2.1 | Tarih: Mart 2026 | Yazar: Fatih Ayaz

---

## 1. PROJE KİMLİĞİ

| Alan | Değer |
|---|---|
| **Proje Adı** | AAOP — Captain logAR |
| **Proje Dizini** | `/Users/fatihayaz/Documents/Projects/AAOP` |
| **Python Venv** | `~/.venvs/aaop` (Python 3.12 — 3.14 YASAK) |
| **Ana Repo** | `github.com/fatihayaz78/aaop` |
| **Mock Data Repo** | `github.com/fatihayaz78/aaop-mock-data-gen` |

---

## 2. BAŞLATMA KOMUTLARI

```bash
# Venv aktive et
source ~/.venvs/aaop/bin/activate

# Backend (FastAPI — port 8000)
cd /Users/fatihayaz/Documents/Projects/AAOP
python -m uvicorn backend.main:app --reload --port 8000

# Frontend (Next.js — port 3000)
cd /Users/fatihayaz/Documents/Projects/AAOP/frontend
npm run dev

# Redis
redis-server

# Sağlık kontrolü
curl http://localhost:8000/health
```

---

## 3. DOKÜMAN HARİTASI

| Dosya | Ne zaman okunur | İçerik |
|---|---|---|
| `CLAUDE.md` | Her prompt | Navigation, başlatma, app listesi, klasör yapısı |
| `ARCHITECTURE.md` | Her prompt | Stack, ADR'ler, adaptor pattern, event bus |
| `docs/SPRINT_PLAN.md` | Her sprint | Aktif sprint adımları, bitti kriteri |
| `docs/DATA_FLOW.md` | Cross-app sprint'lerde | DuckDB şemaları, Event Bus, Redis TTL |
| `UI_SYSTEM.md` | UI sprint'lerinde | Design tokens, component kuralları |
| `API_CONTRACTS.md` | API yazarken | Tüm endpoint sözleşmeleri |
| `CHANGELOG.md` | Sprint bitince | Sürüm geçmişi |
| `apps/{app}/{app}.spec.md` | Sadece o app sprint'inde | Agent, tools, DB, cross-app |

---

## 4. 11 APP — TAM LİSTE

| # | Klasör | Spec Dosyası | Modüller | Öncelik |
|---|---|---|---|---|
| 1 | `apps/ops_center/` | `ops_center.spec.md` | M01 Incident + M06 RCA | P0 |
| 2 | `apps/log_analyzer/` | `log_analyzer.spec.md` | M07 + Akamai/Medianova sub-modules | P0 |
| 3 | `apps/alert_center/` | `alert_center.spec.md` | M13 Alert Router | P0 |
| 4 | `apps/viewer_experience/` | `viewer_experience.spec.md` | M02 QoE + M09 Complaint | P1 |
| 5 | `apps/live_intelligence/` | `live_intelligence.spec.md` | M05 Live Event + M11 External | P1 |
| 6 | `apps/growth_retention/` | `growth_retention.spec.md` | M18 Growth + M03 Data Analyst | P1 |
| 7 | `apps/capacity_cost/` | `capacity_cost.spec.md` | M16 Capacity + M04 Automation | P1 |
| 8 | `apps/admin_governance/` | `admin_governance.spec.md` | M12 Tenant + M17 Compliance | P1 |
| 9 | `apps/ai_lab/` | `ai_lab.spec.md` | M10 Experimentation + M14 ML Gov | P2 |
| 10 | `apps/knowledge_base/` | `knowledge_base.spec.md` | M15 Knowledge Base | P2 |
| 11 | `apps/devops_assistant/` | `devops_assistant.spec.md` | M08 DevOps Assistant | P2 |

---

## 5. AKTİF SPRINT

**Aktif Sprint:** S24 next — UI Fix Sprint (browser testing all 11 apps)
**Önceki:** S23 complete — metrics fix + Swagger + KB + raw log values (no hashing)
**Son commit:** S23-Fix2 — all hashing removed from Log Analyzer (659 tests)

---

## 6. TAM KLASÖR YAPISI

```
AAOP/
│
├── CLAUDE.md                        ← Navigation index (bu dosya)
├── ARCHITECTURE.md                  ← Mimari kararlar, stack, adaptor pattern
├── UI_SYSTEM.md                     ← Design system, component kuralları
├── API_CONTRACTS.md                 ← Tüm endpoint sözleşmeleri
├── CHANGELOG.md                     ← Sürüm geçmişi
├── pyproject.toml                   ← Poetry + ruff + mypy + pytest config
├── .env                             ← Gerçek değerler (gitignore'da)
├── .env.example                     ← Key listesi (değer yok)
├── .gitignore
├── .pre-commit-config.yaml
│
├── docs/
│   ├── SPRINT_PLAN.md               ← Sprint yönetimi (S01–S09)
│   └── DATA_FLOW.md                 ← Cross-app veri mimarisi
│
├── .github/
│   └── workflows/
│       └── ci.yml                   ← ruff + mypy + pytest pipeline
│
├── backend/                         ← FastAPI uygulaması (port 8000)
│   ├── main.py                      ← App, router mount, startup events
│   ├── auth.py                      ← JWT login/refresh/logout
│   ├── dependencies.py              ← DI: DB sessions, tenant context
│   ├── routers/
│   │   ├── ops_center.py            ← /ops prefix
│   │   ├── log_analyzer.py          ← /log-analyzer prefix
│   │   ├── alert_center.py          ← /alerts prefix
│   │   ├── viewer_experience.py     ← /viewer prefix
│   │   ├── live_intelligence.py     ← /live prefix
│   │   ├── growth_retention.py      ← /growth prefix
│   │   ├── capacity_cost.py         ← /capacity prefix
│   │   ├── ai_lab.py                ← /ai-lab prefix
│   │   ├── knowledge_base.py        ← /knowledge prefix
│   │   ├── devops_assistant.py      ← /devops prefix
│   │   └── admin_governance.py      ← /admin prefix
│   ├── websocket/
│   │   └── manager.py               ← Socket.IO broadcast manager
│   └── middleware/
│       ├── rate_limit.py
│       └── tenant_context.py        ← X-Tenant-ID header inject
│
├── frontend/                        ← Next.js 14 (port 3000)
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx            ← Root layout (sidebar, dark mode)
│       │   ├── page.tsx              ← Dashboard
│       │   ├── globals.css           ← Design tokens (CSS vars)
│       │   └── (apps)/
│       │       ├── ops-center/page.tsx
│       │       ├── log-analyzer/page.tsx
│       │       ├── alert-center/page.tsx
│       │       ├── viewer-experience/page.tsx
│       │       ├── live-intelligence/page.tsx
│       │       ├── growth-retention/page.tsx
│       │       ├── capacity-cost/page.tsx
│       │       ├── ai-lab/page.tsx
│       │       ├── knowledge-base/page.tsx
│       │       ├── devops-assistant/page.tsx
│       │       └── admin-governance/page.tsx
│       ├── components/
│       │   ├── ui/                   ← shadcn/ui components
│       │   ├── layout/               ← Sidebar, Header, Breadcrumb
│       │   ├── charts/               ← Recharts wrappers
│       │   └── agent-chat/           ← AI chat panel (collapsible)
│       ├── lib/
│       │   ├── api.ts                ← fetch wrappers → FastAPI
│       │   ├── trpc.ts               ← tRPC client
│       │   └── socket.ts             ← Socket.IO client
│       └── types/
│           └── index.ts              ← Shared TypeScript types
│
├── apps/                            ← 11 app (agent implementasyonları)
│   ├── ops_center/
│   │   ├── ops_center.spec.md       ← App spec
│   │   ├── __init__.py
│   │   ├── agent.py                 ← OpsAgent(BaseAgent) — M01 + M06
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │       ├── test_agent.py
│   │       ├── test_tools.py
│   │       └── fixtures/
│   │
│   ├── log_analyzer/
│   │   ├── log_analyzer.spec.md     ← App spec
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   ├── sub_modules/
│   │   │   ├── __init__.py          ← SubModuleRegistry
│   │   │   ├── base_sub_module.py   ← BaseSubModule abstract class
│   │   │   ├── akamai/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── parser.py        ← DataStream 2 CSV parser
│   │   │   │   ├── scheduler.py     ← APScheduler (her 6 saatte)
│   │   │   │   ├── analyzer.py      ← Anomali tespiti
│   │   │   │   ├── charts.py        ← 21 Plotly grafik (kaleido==0.2.1)
│   │   │   │   ├── reporter.py      ← python-docx DOCX rapor
│   │   │   │   └── schemas.py
│   │   │   └── medianova/
│   │   │       └── __init__.py      ← Placeholder stub
│   │   └── tests/
│   │
│   ├── alert_center/
│   │   ├── alert_center.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── viewer_experience/
│   │   ├── viewer_experience.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py                 ← QoEAgent + ComplaintAgent
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── live_intelligence/
│   │   ├── live_intelligence.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py                 ← LiveEventAgent + ExternalDataAgent
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── growth_retention/
│   │   ├── growth_retention.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py                 ← GrowthAgent + DataAnalystAgent
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── capacity_cost/
│   │   ├── capacity_cost.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py                 ← CapacityAgent + AutomationAgent
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── ai_lab/
│   │   ├── ai_lab.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── knowledge_base/
│   │   ├── knowledge_base.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   ├── devops_assistant/
│   │   ├── devops_assistant.spec.md
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   │
│   └── admin_governance/
│       ├── admin_governance.spec.md
│       ├── __init__.py
│       ├── agent.py                 ← TenantAgent + ComplianceAgent
│       ├── tools.py
│       ├── schemas.py
│       ├── prompts.py
│       ├── config.py
│       └── tests/
│
├── shared/                          ← Ortak kütüphaneler
│   ├── __init__.py
│   ├── agents/
│   │   └── base_agent.py            ← BaseAgent, LangGraph 4-adım
│   ├── llm_gateway.py               ← Routing + retry + cache + cost
│   ├── event_bus.py                 ← asyncio.Queue, 9 event type
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── sqlite_client.py         ← → GCP: Spanner adaptor
│   │   ├── duckdb_client.py         ← → GCP: BigQuery adaptor
│   │   ├── chroma_client.py         ← → GCP: Vertex AI VS adaptor
│   │   └── redis_client.py          ← redis.asyncio wrapper
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── base_event.py            ← BaseEvent, SeverityLevel, RiskLevel
│   │   └── agent_decision.py        ← AgentDecision (DuckDB shared schema)
│   └── utils/
│       ├── settings.py              ← Pydantic BaseSettings, .env okuma
│       └── pii_scrubber.py          ← LLM öncesi PII temizleme
│
├── data/                            ← Lokal veri (gitignore'da)
│   ├── sqlite/
│   │   └── platform.db              ← Platform metadata
│   ├── duckdb/
│   │   └── analytics.duckdb         ← Paylaşımlı analiz DB
│   ├── chromadb/                    ← Vector store kalıcı depolama
│   ├── logs/                        ← S3'ten çekilen log cache
│   └── reports/                     ← Üretilen DOCX raporlar
│       └── {tenant_id}/
│
└── tests/
    ├── conftest.py                  ← Shared fixtures
    ├── unit/                        ← Her shared/ bileşeni için
    └── integration/
        └── scenarios/               ← Mock data senaryoları
            ├── normal_weekday/
            ├── match_day_derby/
            ├── drm_outage/
            └── cdn_spike/
```

---

## 7. TEMEL KURALLAR (Özet)

```
✅ Python 3.12 | structlog | Pydantic v2 | pytest coverage ≥ 80%
✅ Lokal DB: SQLite + DuckDB + ChromaDB + Redis
✅ LLM: Haiku (batch) | Sonnet (default) | Opus (P0/P1 only)
✅ Her tool risk_level ile etiketli: LOW | MEDIUM | HIGH
✅ HIGH risk → approval_required=True
✅ Secret'lar: .env (lokal) | GCP Secret Manager (prod)
✅ GCP geçiş: sadece shared/clients/ adaptor değişir
❌ print() → structlog | ❌ Python 3.14 | ❌ kaleido 1.x
❌ Agent içinde doğrudan DB | ❌ tenant_id'siz tool çağrısı
```
