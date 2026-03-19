# CHANGELOG.md — AAOP Platform Sürüm Geçmişi
> Sprint bittiğinde Claude Code tarafından güncellenir.
> Format: Keep a Changelog | Semantic Versioning 2.0

---

## [Unreleased] — Aktif Geliştirme

### Planlanıyor
- S03: Ops Center (M01 Incident + M06 RCA)
- S04: Alert Center (M13)
- S05: Viewer Experience (M02 + M09)
- S06: Live Intelligence (M05 + M11)
- S07: Growth & Retention + Capacity & Cost
- S08: Remaining apps + Admin & Governance
- S09: Cross-app integrations + Frontend (Next.js)

---

## [0.2.0] — 2026-03-19 — S02: Log Analyzer

### Eklendi
- `apps/log_analyzer/` — tam Log Analyzer app implementasyonu
- Akamai DataStream 2 sub-module: CSV/JSON parser, metrics calculator, anomaly detector
- 21 Plotly dark-theme chart (kaleido==0.2.1 pinned)
- python-docx DOCX report generator (cover, summary, metrics, anomalies, chart gallery)
- SubModuleRegistry pattern — yeni log kaynakları kolayca eklenir
- LogAnalyzerAgent(BaseAgent) — LangGraph 4-step, Event Bus publish
- 12 risk-tagged tools (LOW/MEDIUM/HIGH)
- APScheduler async scheduler for periodic S3 log fetch
- PII scrubbing: cliIP + UA → SHA256 hash before storage
- `/log-analyzer` API endpoints: health, sub-modules, projects, results
- 36 unit tests, 80% coverage
- Test fixtures: sample_akamai_normal.csv, sample_akamai_spike.csv

---

## [0.1.0] — 2026-03-19 — S01: Foundation Layer

### Eklendi
- `pyproject.toml` — Poetry, ruff, mypy, pytest config
- `shared/utils/settings.py` — Pydantic BaseSettings (.env okuma)
- `shared/schemas/` — BaseEvent, SeverityLevel, RiskLevel, TenantContext, AgentDecision
- `shared/clients/` — SQLiteClient (async), DuckDBClient, ChromaClient, RedisClient
- `shared/event_bus.py` — asyncio.Queue Event Bus (9 EventType, pub/sub routing)
- `shared/llm_gateway.py` — Severity-based model routing (Haiku/Sonnet/Opus), tenacity retry, Redis cache
- `shared/utils/pii_scrubber.py` — Regex PII temizleme (email, IP, phone, TC kimlik)
- `shared/agents/base_agent.py` — LangGraph 4-adim StateGraph (context_loader, reasoning, tool_execution, memory_update)
- `backend/main.py` — FastAPI app, lifespan, CORS, /health endpoint
- `backend/auth.py` — JWT token create/verify, password hashing (bcrypt)
- `backend/dependencies.py` — DI: DB client injection, tenant context header parsing
- `backend/middleware/` — TenantContextMiddleware, RateLimitMiddleware
- `backend/websocket/manager.py` — Socket.IO broadcast manager
- SQLite init: tenants, users, module_configs, audit_log tabloları
- DuckDB init: shared_analytics schema (6 tablo — cdn_analysis, incidents, qoe_metrics, live_events, agent_decisions, alerts_sent)
- `frontend/` — Next.js 14, TypeScript strict, Tailwind dark-mode-first, 11 app page stubs
- `frontend/src/app/layout.tsx` — Sidebar navigation, design tokens (CSS vars)
- `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`
- 86 unit test, 96% coverage (shared + backend)

---

## [2.0.0-alpha] — 2026-03-19

### Eklendi
- Proje sıfırdan yeniden tasarlandı (v2.0)
- 11-app mimarisi tanımlandı (18 modül → 11 uygulama)
- Lokal stack belirlendi: SQLite + DuckDB + ChromaDB + Redis
- Next.js 14 + FastAPI ayrı servis mimarisi
- Log Analyzer app: Akamai + sub-module mimarisi
- 9-event cross-app Event Bus kataloğu
- Adaptor pattern: Lokal → GCP geçiş tasarımı

### Değişti
- Eski: GCP-native (Spanner + BigQuery + Pub/Sub)
- Yeni: Lokal-first (SQLite + DuckDB + asyncio.Queue)
- Eski: Jinja2 templates (monolithic)
- Yeni: Next.js 14 frontend (ayrı servis)
- Eski: 18 ayrı modül klasörü
- Yeni: 11 app altında gruplanmış

### Kaldırıldı
- Terraform / Helm / GKE konfigürasyonları (yeni repo'ya taşındı)
- GCP emülatör bağımlılıkları
- Jinja2 template sistemi

---

_Sprint kapandıkça bu dosyaya ekleme yapılır. Git log özeti her versiyonda bulunur._
