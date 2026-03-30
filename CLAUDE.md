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
| `docs/AUDIT_REPORT.md` | Platform sağlık değerlendirmesinde | Platform audit, puan kartı, kritik eksikler |
| `docs/DOC_GAP_REPORT.md` | Dokümantasyon güncellemesinde | MD dosyaları vs code base tutarsızlıkları |
| `docs/kb/` | Platform dokümantasyonu için | 15 standalone HTML, her modül detayı |

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
| 12 | `apps/mock_data_gen/` | `mock_data_gen_spec.md` | Mock Data Generator (13 kaynak, 91 gün) | Dev/Test |

---

## 5. AKTİF SPRINT

**Son tamamlanan:** S-MT-04 — Service Switcher UI + Multi-Tenant Auth
**Önceki:** S-AGENT-01..05 → S-EB-01 → S-MT-01..04
**Baseline:** 148 test, 0 failure (30 Mart 2026)
**Multi-Tenant:** ✅ 3 katman (super_admin → tenant → service), 22 concrete agent, Event Bus aktif

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
│   ├── DATA_FLOW.md                 ← Cross-app veri mimarisi
│   ├── AUDIT_REPORT.md              ← Platform audit (28 Mart 2026)
│   ├── DOC_GAP_REPORT.md            ← Dokümantasyon gap analizi
│   └── kb/                          ← Standalone HTML dokümantasyon (15 dosya)
│       ├── index.html               ← Platform genel bakış
│       ├── ops_center.html ... (11 modül + architecture + api_reference + log_schemas)
│       └── knowledge_base.html
│
├── .github/
│   └── workflows/
│       └── ci.yml                   ← ruff + mypy + pytest pipeline
│
├── backend/                         ← FastAPI uygulaması (port 8000)
│   ├── main.py                      ← App, router mount, startup events
│   ├── auth.py                      ← JWT multi-tenant login/switch-service/tenants
│   ├── dependencies.py              ← DI: DB sessions, tenant/service seed
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
│   │   ├── admin_governance.py      ← /admin prefix
│   │   ├── data_sources.py          ← /data-sources prefix, 10 endpoint
│   │   └── mock_data_gen.py         ← /mock-data-gen prefix, 13 endpoint
│   ├── websocket/
│   │   └── manager.py               ← Socket.IO broadcast manager
│   ├── models/
│   │   ├── __init__.py
│   │   └── export_schema.py         ← ExportSchema Pydantic model
│   └── middleware/
│       ├── rate_limit.py
│       ├── tenant_context.py        ← X-Tenant-ID header inject
│       └── service_context.py       ← JWT → service_id + duckdb_schema (S-MT-02)
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
│       │       ├── login/page.tsx          ← Multi-tenant login (S-MT-02)
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
│       │       ├── admin-governance/page.tsx
│       │       └── admin-governance/tenants/page.tsx  ← Platform Admin (S-MT-04)
│       ├── contexts/
│       │   └── AuthContext.tsx        ← Multi-tenant auth state (S-MT-04)
│       ├── components/
│       │   ├── ui/                   ← shadcn/ui components
│       │   ├── layout/               ← Sidebar, Header, ServiceSwitcher
│       │   ├── charts/               ← Recharts wrappers
│       │   └── agent-chat/           ← AI chat panel (collapsible)
│       ├── lib/
│       │   ├── api.ts                ← fetch wrappers → FastAPI
│       │   ├── trpc.ts               ← tRPC client
│       │   └── socket.ts             ← Socket.IO client
│       └── types/
│           └── index.ts              ← Shared TypeScript types
│   └── public/
│       ├── captain-logar.png
│       └── kb/                      ← docs/kb/ kopyası (Next.js serving, 15 HTML)
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
│   ├── event_bus.py                 ← asyncio.Queue, 9 event type, 8 agent subscribe
│   ├── models/
│   │   ├── __init__.py
│   │   └── tenant_models.py         ← TenantBase, ServiceBase, TenantWithServices (S-MT-01)
│   ├── middleware/
│   │   └── service_context.py       ← JWT→service_id→duckdb_schema (S-MT-02)
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── sqlite_client.py         ← → GCP: Spanner adaptor
│   │   ├── duckdb_client.py         ← → GCP: BigQuery adaptor
│   │   ├── chroma_client.py         ← → GCP: Vertex AI VS adaptor
│   │   ├── redis_client.py          ← redis.asyncio wrapper
│   │   └── logs_duckdb_client.py   ← logs.duckdb hot cache client
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── source_config.py        ← SourceConfig Pydantic modeli + SQLite DDL
│   │   ├── log_schemas.py          ← 13 kaynak DuckDB tablo şemaları
│   │   ├── jsonl_parser.py         ← JSONL.gz parser, directory scanner
│   │   ├── sync_engine.py          ← Sync orchestration, file tracking
│   │   ├── query_router.py         ← Hot/cold query routing
│   │   ├── watch_folder.py         ← File system watcher (watchdog)
│   │   ├── log_queries.py          ← 12 query helper (tüm app'ler okur)
│   │   └── default_configs.py      ← aaop_company default source config seed
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── base_event.py            ← BaseEvent, SeverityLevel, RiskLevel
│   │   └── agent_decision.py        ← AgentDecision (DuckDB shared schema)
│   └── utils/
│       ├── settings.py              ← Pydantic BaseSettings, .env okuma
│       └── pii_scrubber.py          ← LLM öncesi PII temizleme
│
├── scripts/
│   ├── data_audit.py                ← DuckDB veri denetim scripti (S-DATA-AUDIT-01)
│   └── seed_demo_tenants.py         ← Multi-tenant demo veri seed (S-MT-03)
│
├── docs/
│   ├── data_audit_report.md         ← İlk audit raporu
│   └── data_audit_report_v2.md      ← Multi-tenant audit raporu (S-MT-03)
│
├── data/                            ← Lokal veri (gitignore'da)
│   ├── sqlite/
│   │   └── platform.db              ← Platform metadata
│   ├── duckdb/
│   │   ├── analytics.duckdb         ← Paylaşımlı analiz DB
│   │   └── logs.duckdb             ← Log data hot cache (≤30 gün)
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

## 7. MULTI-TENANT HİYERARŞİ

| tenant_id | Tenant Name | service_id | Service Name | DuckDB Schema |
|---|---|---|---|---|
| ott_co | OTT Co | sport_stream | Sport Stream | sport_stream |
| tel_co | Tel Co | tv_plus | TV Plus | tv_plus |
| tel_co | Tel Co | music_stream | Music Stream | music_stream |
| airline_co | Airline Co | fly_ent | Fly Entertainment | fly_ent |

### Demo Kullanıcılar (Şifre: `Captain2026!`)

| Email | Tenant | Role | Services |
|---|---|---|---|
| admin@captainlogar.demo | NULL | super_admin | Tümü |
| admin@ottco.demo | ott_co | tenant_admin | sport_stream |
| admin@telco.demo | tel_co | tenant_admin | tv_plus, music_stream |
| user@telco.demo | tel_co | service_user | tv_plus |
| admin@airlineco.demo | airline_co | tenant_admin | fly_ent |

---

## 8. TEMEL KURALLAR (Özet)

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
