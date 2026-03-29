# ARCHITECTURE.md — AAOP Teknik Mimari
> Claude Code bu dosyayı her prompt'ta okur.
> Versiyon: 2.0 | Mart 2026

---

## 1. MİMARİ KARAR ÖZETİ (ADR)

| ADR | Karar | Gerekçe |
|---|---|---|
| ADR-001 | **LangGraph** agent orchestration | Stateful döngü, node-bazlı test edilebilirlik |
| ADR-002 | **FastAPI** backend (port 8000) | Async-first, Pydantic v2 native, OpenAPI otomatik |
| ADR-003 | **Next.js 14** frontend (port 3000) | SSR, App Router, TypeScript strict |
| ADR-004 | **SQLite** platform metadata | Lokal sıfır-kurulum, GCP'de Cloud Spanner'a adaptor ile geçiş |
| ADR-005 | **DuckDB** paylaşımlı analiz DB | Cross-app analytics, columnar, sıfır-sunucu, BigQuery'e adaptor |
| ADR-006 | **ChromaDB** vector store | Lokal kalıcı, GCP'de Vertex AI VS'ye adaptor |
| ADR-007 | **Redis** context cache | TTL-based context yönetimi, lokal + GCP Memorystore aynı API |
| ADR-008 | **asyncio.Queue** Event Bus | Lokal cross-app sinyal, GCP'de Pub/Sub'a adaptor |
| ADR-009 | **Anthropic Claude** tek LLM sağlayıcı | Haiku/Sonnet/Opus 3-model strateji, severity-based routing |
| ADR-010 | **Adaptor Pattern** her GCP servisi için | Agent kodu değişmeden lokal↔GCP geçiş |
| ADR-011 | **logs.duckdb** ayrı log cache DB | 30 gün hot retention, kaynak bazlı tablo izolasyonu, tenant schema |

---

## 2. TEKNOLOJİ STACK

### Frontend (mor katman)
```
Next.js 14          App Router + SSR
TypeScript          strict mode, noImplicitAny
Tailwind CSS        dark-mode-first (class strategy)
shadcn/ui           component library
Recharts            veri grafikleri
Socket.IO Client    WebSocket real-time
```

### API Katmanı (yeşil-mavi katman)
```
FastAPI             Python 3.12, port 8000, async
tRPC               type-safe backend↔frontend köprüsü
Socket.IO           WebSocket (python-socketio) ⚠️ tanımlı ama mount edilmemiş — S-WS-01'de
Pydantic v2         tüm request/response modelleri
JWT                 python-jose, HS256
python-multipart    dosya upload (log dosyaları)
```

### Agentic AI Katmanı (turuncu-kırmızı katman)
```
LangGraph           stateful 4-adım döngü (her agent)
BaseAgent           shared/agents/base_agent.py — tüm app'ler extend eder
LLM Gateway         shared/llm_gateway.py — routing + retry + cost
Event Bus           shared/event_bus.py — asyncio.Queue cross-app
tenacity            retry logic (exponential backoff)
structlog           yapılandırılmış loglama
```

### Veri Katmanı (mavi katman)
```
SQLite              platform metadata (tenants, users, configs)
                    → GCP: Cloud Spanner (adaptor: shared/clients/sqlite_client.py)
DuckDB              paylaşımlı analiz çıktıları
                    → GCP: BigQuery (adaptor: shared/clients/duckdb_client.py)
logs.duckdb         log verisi hot cache (≤30 gün, tenant schema bazlı)
                    → GCP: BigQuery (adaptor: shared/clients/logs_duckdb_client.py)
ChromaDB            vector RAG (3 collection: code, docs, incidents)
                    → GCP: Vertex AI VS (adaptor: shared/clients/chroma_client.py)
Redis               context cache (redis-py async)
                    → GCP: Memorystore (aynı API, sadece host değişir)
```

### LLM Routing
```
claude-haiku-4-5-20251001      Batch işlemler, toplu analiz, P3 events
claude-sonnet-4-20250514       Default, P2 events, rutin analizler
claude-opus-4-20250514         P0/P1 incident, RCA — sadece bu iki app
```

### Log Analyzer Özel Kütüphaneler (pembe katman)
```
boto3               S3 log okuma (Akamai DataStream 2)
APScheduler         zamanlanmış log çekme görevleri
watchdog            file system watcher (watch folder → auto import+delete)
python-docx         DOCX rapor üretme
kaleido==0.2.1      DOCX'e grafik gömme (1.x Chrome gerektirir — PIN'Lİ)
plotly              grafik üretme (kaleido ile birlikte)
```

### Geliştirme Araçları (yeşil katman)
```
pytest + pytest-asyncio   test framework
ruff                      lint + format (black yerine)
mypy                      type checking
poetry                    dependency management
pre-commit                hook'lar (ruff, mypy, pytest smoke)
GitHub Actions            CI/CD
```

---

## 3. TAM KLASÖR YAPISI

```
AAOP/
├── CLAUDE.md
├── ARCHITECTURE.md
├── UI_SYSTEM.md
├── API_CONTRACTS.md
├── CHANGELOG.md
├── pyproject.toml              ← Poetry + pytest + ruff + mypy config
├── .env.example                ← Tüm gerekli env değişkenleri (değer yok)
├── .env                        ← Gerçek değerler (gitignore'da)
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml              ← ruff + mypy + pytest pipeline
│
├── docs/
│   ├── SPRINT_PLAN.md
│   └── DATA_FLOW.md
│
├── backend/                    ← FastAPI uygulaması
│   ├── main.py                 ← FastAPI app, router mount, startup events
│   ├── auth.py                 ← JWT middleware, login endpoint
│   ├── dependencies.py         ← Pydantic settings, DB session injection
│   ├── routers/
│   │   ├── ops_center.py
│   │   ├── log_analyzer.py
│   │   ├── alert_center.py
│   │   ├── viewer_experience.py
│   │   ├── live_intelligence.py
│   │   ├── growth_retention.py
│   │   ├── capacity_cost.py
│   │   ├── ai_lab.py
│   │   ├── knowledge_base.py
│   │   ├── devops_assistant.py
│   │   └── admin_governance.py
│   ├── websocket/
│   │   └── manager.py          ← Socket.IO real-time broadcast
│   └── middleware/
│       ├── rate_limit.py
│       └── tenant_context.py   ← tenant_id header inject
│
├── frontend/                   ← Next.js 14
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── src/
│   │   ├── app/                ← App Router
│   │   │   ├── layout.tsx      ← Root layout (sidebar, dark mode)
│   │   │   ├── page.tsx        ← Dashboard
│   │   │   ├── (apps)/
│   │   │   │   ├── ops-center/page.tsx
│   │   │   │   ├── log-analyzer/page.tsx
│   │   │   │   ├── alert-center/page.tsx
│   │   │   │   └── ... (8 more)
│   │   │   └── admin/page.tsx
│   │   ├── components/
│   │   │   ├── ui/             ← shadcn/ui components
│   │   │   ├── layout/         ← Sidebar, Header, BreadCrumb
│   │   │   ├── charts/         ← Recharts wrappers
│   │   │   └── agent-chat/     ← AI chat panel (collapsible)
│   │   ├── lib/
│   │   │   ├── api.ts          ← fetch wrappers → FastAPI
│   │   │   ├── trpc.ts         ← tRPC client
│   │   │   └── socket.ts       ← Socket.IO client
│   │   └── types/
│   │       └── index.ts        ← Shared TypeScript types
│   └── public/
│       └── captain-logar.png   ← Logo
│
├── apps/                       ← 11 app (agent implementasyonları)
│   ├── ops_center/
│   │   ├── .spec.md            ← App spec (Claude Code okur)
│   │   ├── __init__.py
│   │   ├── agent.py            ← OpsAgent(BaseAgent) — M01 + M06
│   │   ├── tools.py            ← risk_level etiketli tools
│   │   ├── schemas.py          ← Pydantic modeller
│   │   ├── prompts.py          ← System prompts
│   │   ├── config.py           ← OpsModuleConfig(BaseSettings)
│   │   └── tests/
│   │       ├── test_agent.py
│   │       ├── test_tools.py
│   │       └── fixtures/
│   ├── log_analyzer/
│   │   ├── .spec.md
│   │   ├── __init__.py
│   │   ├── agent.py            ← LogAnalyzerAgent(BaseAgent)
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   ├── sub_modules/
│   │   │   ├── akamai/         ← Akamai DataStream 2 parser
│   │   │   │   ├── parser.py
│   │   │   │   ├── scheduler.py   ← APScheduler jobs
│   │   │   │   ├── charts.py      ← Plotly + kaleido
│   │   │   │   └── reporter.py    ← python-docx
│   │   │   └── medianova/      ← Placeholder (future)
│   │   │       └── __init__.py
│   │   └── tests/
│   ├── alert_center/
│   │   ├── .spec.md
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── config.py
│   │   └── tests/
│   ├── viewer_experience/
│   ├── live_intelligence/
│   ├── growth_retention/
│   ├── capacity_cost/
│   ├── ai_lab/
│   ├── knowledge_base/
│   ├── devops_assistant/
│   └── admin_governance/
│
├── shared/                     ← Ortak kütüphaneler
│   ├── __init__.py
│   ├── agents/
│   │   └── base_agent.py       ← BaseAgent, 4-adım LangGraph, risk routing
│   ├── llm_gateway.py          ← LLM routing, tenacity retry, Redis cache, cost tracking
│   ├── event_bus.py            ← asyncio.Queue, publish/subscribe, 9 event type
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── sqlite_client.py    ← SQLite async wrapper (→ Spanner adaptor)
│   │   ├── duckdb_client.py    ← DuckDB wrapper (→ BigQuery adaptor)
│   │   ├── chroma_client.py    ← ChromaDB wrapper (→ Vertex AI VS adaptor)
│   │   ├── redis_client.py     ← redis.asyncio wrapper
│   │   └── logs_duckdb_client.py ← logs.duckdb hot cache client
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── source_config.py        ← SourceConfig Pydantic modeli + SQLite DDL
│   │   ├── log_schemas.py          ← 13 kaynak DuckDB tablo şemaları
│   │   ├── jsonl_parser.py         ← JSONL.gz parser, directory scanner
│   │   ├── sync_engine.py          ← Sync orchestration, file tracking
│   │   ├── query_router.py         ← Hot/cold query routing
│   │   ├── watch_folder.py         ← File system watcher (watchdog)
│   │   └── default_configs.py      ← aaop_company default source config seed
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── base_event.py       ← BaseEvent, SeverityLevel, RiskLevel, TenantContext
│   │   └── agent_decision.py   ← AgentDecision (DuckDB'ye yazılan ortak schema)
│   └── utils/
│       ├── settings.py         ← Pydantic BaseSettings, .env okuma
│       └── pii_scrubber.py     ← LLM çağrısı öncesi PII temizleme
│
├── data/                       ← Lokal veri dizini (gitignore)
│   ├── sqlite/
│   │   └── platform.db         ← Platform metadata
│   ├── duckdb/
│   │   ├── analytics.duckdb    ← Paylaşımlı analiz DB
│   │   └── logs.duckdb             ← Log data hot cache (≤30 gün)
│   ├── chromadb/               ← Vector store kalıcı depolama
│   └── logs/                   ← Akamai S3'ten çekilen log dosyaları (cache)
│
└── tests/
    ├── conftest.py             ← Shared fixtures (mock tenants, mock LLM)
    ├── unit/
    └── integration/
        └── scenarios/          ← Mock data senaryoları (aaop-mock-data-gen'den)
```

---

## 4. AGENT 4-ADIM DÖNGÜSÜ (Her App İçin Standart)

```python
# shared/agents/base_agent.py — her app bu sınıfı extend eder
class BaseAgent:
    graph: StateGraph  # LangGraph

    # Adım 1: Context yükleme
    async def context_loader_node(state):
        # Redis cache → DuckDB → ChromaDB RAG (bu sırayla)
        # Timeout: Redis < 5ms, DuckDB < 50ms, Chroma < 100ms

    # Adım 2: LLM reasoning
    async def reasoning_node(state):
        # LLM Gateway → severity'ye göre model seç
        # PII scrub → LLM call → parse response

    # Adım 3: Tool execution
    async def tool_execution_node(state):
        # risk_level kontrolü:
        # LOW    → otomatik çalıştır
        # MEDIUM → çalıştır + Event Bus'a notify yayınla
        # HIGH   → approval_required=True set et, bekle

    # Adım 4: Memory güncelleme
    async def memory_update_node(state):
        # DuckDB shared_analytics.agent_decisions'a yaz
        # Redis context cache güncelle
        # Event Bus'a sonuç yayınla (ilgili event type ile)
```

> ✅ **Mevcut Durum (Mart 2026):** BaseAgent LangGraph StateGraph implement edildi (S-AGENT-01). 4-adım cycle çalışıyor: context_loader (Redis→DuckDB→ChromaDB) → reasoning (LLM JSON parse) → tool_execution (LOW=auto, MEDIUM=auto+notify, HIGH=approval) → memory_update (DuckDB write + Redis cache). 15 unit test. Tüm app'lerde agent.py stub — concrete agent'lar S-AGENT-02+ sprint'lerinde yapılacak.

---

## 5. LOKAL → GCP GEÇİŞ HARİTASI (Adaptor Pattern)

| Lokal | GCP | Adaptor Dosyası | Değişen |
|---|---|---|---|
| SQLite | Cloud Spanner | `shared/clients/sqlite_client.py` | Sadece adaptor |
| DuckDB | BigQuery | `shared/clients/duckdb_client.py` | Sadece adaptor |
| ChromaDB | Vertex AI Vector Search | `shared/clients/chroma_client.py` | Sadece adaptor |
| asyncio.Queue | Google Cloud Pub/Sub | `shared/event_bus.py` | Sadece adaptor |
| Redis (lokal) | Cloud Memorystore | `shared/clients/redis_client.py` | Host değişir |
| `.env` secrets | GCP Secret Manager | `shared/utils/settings.py` | Provider değişir |

**Kural:** Agent kodu (`apps/*/agent.py`, `apps/*/tools.py`) GCP'ye geçişte **HİÇ değişmez.**

---

## 6. EVENT BUS — 9 CROSS-APP EVENT

| Event Type | Kaynak App | Hedef App(lar) |
|---|---|---|
| `cdn_anomaly_detected` | log_analyzer | ops_center, alert_center |
| `incident_created` | ops_center | alert_center, knowledge_base |
| `rca_completed` | ops_center (M06) | knowledge_base, alert_center |
| `qoe_degradation` | viewer_experience | ops_center, alert_center |
| `live_event_starting` | live_intelligence | ops_center, log_analyzer, alert_center |
| `external_data_updated` | live_intelligence | ops_center, growth_retention |
| `churn_risk_detected` | growth_retention | alert_center |
| `scale_recommendation` | capacity_cost | ops_center, alert_center |
| `analysis_complete` | log_analyzer | growth_retention, viewer_experience |

> Detaylı şemalar ve DuckDB tablo yapısı: `docs/DATA_FLOW.md`

> ⚠️ **Mevcut Durum (Mart 2026):** shared/event_bus.py tanımlı ve 9 event type spec'te mevcut. Ancak hiçbir app runtime'da subscribe/publish yapmıyor. Event Bus wiring: S-EB-01 sprint'inde yapılacak.

---

## 7. GÜVENLİK (LOKAL)

```python
# .env dosyası — gitignore'da
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET_KEY=random-256bit-key
SQLITE_PATH=./data/sqlite/platform.db
DUCKDB_PATH=./data/duckdb/analytics.duckdb
LOGS_DUCKDB_PATH=./data/duckdb/logs.duckdb
MOCK_DATA_BASE_PATH=/Users/fatihayaz/Documents/Projects/AAOP/aaop-mock-data
REDIS_HOST=localhost
REDIS_PORT=6379
CHROMADB_PATH=./data/chromadb
AWS_ACCESS_KEY_ID=...          # S3 log okuma (log_analyzer)
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=ssport-datastream

# Asla kod içinde credential yok
# Asla .env dosyası commit'leme
# .env.example → değer yok, sadece key listesi
```

---

## 8. TEST STRATEJİSİ

```
Unit Tests       pytest         Her tool, her schema, her utility
Integration      pytest         Agent + mock SQLite/DuckDB + mock LLM
Scenario Tests   pytest         Mock data senaryoları (NORMAL_WEEKDAY, MATCH_DAY_DERBY, DRM_OUTAGE)
Coverage hedefi  ≥ 80%          CI'da blocker

# Test komutu (her sprint sonunda çalıştır)
source ~/.venvs/aaop/bin/activate
pytest tests/ -v --cov=. --cov-report=term-missing --cov-fail-under=80
```

---

## 9. KIRMIZI ÇİZGİLER

```
❌ print()                    → structlog kullan
❌ Python 3.14                → 3.12 kullan
❌ kaleido 1.x                → 0.2.1 pin'li (Chrome bağımlılığı var)
❌ Agent içinde doğrudan DB   → tools üzerinden git
❌ HIGH risk tool auto-run    → approval_required=True set et
❌ LLM'e ham PII gönderme     → pii_scrubber.py'den geç
❌ Hardcoded credential       → .env kullan
❌ tenant_id'siz tool çağrısı → tüm tool'lar tenant_id alır
❌ Dokümansız ADR             → ARCHITECTURE.md güncelle
```
