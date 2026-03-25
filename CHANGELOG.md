# CHANGELOG.md — AAOP Platform Sürüm Geçmişi
> Sprint bittiğinde Claude Code tarafından güncellenir.
> Format: Keep a Changelog | Semantic Versioning 2.0

---

## [Unreleased]

---

## [S17-P2] — 2026-03-25
### Added
- Ops Center frontend (ops-center/page.tsx) — 4 tabs implemented
  - Dashboard: 4 KPI cards (Total/Open/MTTR/P0), Severity BarChart, 24h AreaChart, recent incidents mini-table
  - Incidents: filter bar (severity/status/search), table with badges, detail Sheet (TR+EN cards, status update)
  - RCA Explorer: P0/P1 selector, root causes, correlation timeline, recommended actions
  - Decision Log: risk filter, date range, agent decisions table
  - Captain logAR chat panel (ops context, bilingual)
### Fixed
- tenant_id: bein_sports → s_sport_plus
- Field mapping: snake_case backend → camelCase frontend (open_incidents, mttr_p50_seconds, etc.)
- KPI cards: correct field references, MTTR "Xm Ys" format
- Severity badge colors: P0=red-950, P1=orange-950, P2=yellow-950, P3=blue-950
- Status dots: open=red, investigating=amber, resolved=green
- Incident detail panel: summaryTr + detailEn cards, affected services tags
- /ops/decisions endpoint (was calling /ops/health by mistake)
### Known Issues
- Minor UI bugs deferred to fix sprint

---

## [S17-P1] — 2026-03-25
### Added
- apps/ops_center/seed.py — idempotent mock data seed (50 incidents, 50 agent decisions)
  - P0×5, P1×15, P2×20, P3×10 — OTT/CDN realistic titles, summary_tr, detail_en
  - Called from backend/main.py lifespan startup (non-blocking)
- GET /ops/dashboard — KPI stats + severity breakdown + 24h trend
- GET /ops/incidents — paginated list, severity/status filter
- GET /ops/incidents/{id} — full incident record (404-safe)
- PATCH /ops/incidents/{id}/status — status transition with validation
- GET /ops/incidents/{id}/rca — RCA result from agent_decisions
- GET /ops/decisions — paginated agent decision log
- POST /ops/chat — Captain logAR for Ops Center (Sonnet, bilingual, incident context)
### Test
- pytest ops_center: 32 passed, 0 failures (regression clean)
- pytest full suite: 508 passed, 0 failures

---

## [S16-P19] — 2026-03-25
### Fixed
- Project selection auto-fills dates and fetch mode
- Date range combobox calculates relative to current time (UTC+3)
### Added
- Start/End time inputs (hour:minute) in Log Analyzer tab
- "Intelligence & Tasks" tab (merged Analysis Results + Scheduled Tasks + Anomaly Rules)

---

## [S16-P18] — 2026-03-25
### Fixed
- Project delete (undefined id bug)
- DOCX report download endpoint
- Analysis Results: date filter, deduplication, View Charts

---

## [S16-P17] — 2026-03-24
### Added
- Captain logAR AI Chat panel in Log Analyzer tab
- POST /log-analyzer/chat with job context + Turkish support
- GET /log-analyzer/chat/suggestions (context-aware)
- Anthropic API key status in Settings

---

## [S16-P16] — 2026-03-24
### Fixed
- Cache Status integer mapping (float/string coerce)
- Geographic: city-based grouping with country suffix
- All hourly charts: full 24h timeline
- Top 10 IPs: truncated labels, full hash in table
### Added
- Per-chart expand/collapse toggle
- Chart descriptions below titles

---

## [S16-P15] — 2026-03-24
### Fixed
- Cache Hit Ratio: percentage labels, always 2 bars
- Bandwidth by Hour: full 24h timeline, missing hours filled with 0
### Added
- Diagnostic structlog for status codes, cache hit, bandwidth bytes

---

## [S16-P14] — 2026-03-24
### Fixed
- Project delete endpoint (was missing)
- Anomaly Rules edit button + PATCH endpoint
- Analysis Results delete per row
### Added
- BigQuery export in Log Analyzer tab (collapsible)
- BQ export fields in Scheduled Tasks

---

## [S16-P13] — 2026-03-24
### Added
- Project cards with summary (last analysis, scheduled tasks, anomaly alerts)
- Project create form: description, source_type, cp_code, fetch_mode, date_range
- GET /projects/{id}/summary endpoint
- Open in Log Analyzer / Schedule buttons per project

---

## [S16-P12] — 2026-03-24
### Fixed
- Scheduled Tasks edit button opens inline form
- PATCH endpoint partial update (non-None fields only)
### Added
- Email list management per scheduled task (add/remove)

---

## [S16-P11] — 2026-03-24
### Fixed
- Cache Status Breakdown labels (0-9 full mapping)
- Total GB bytes diagnostic logging
### Added
- Quick date range combobox (Last 24h/Day/Week/Month/Custom)
- Scheduled Tasks tab with CRUD, Run Now, email notifications
- Save Config → Add to Scheduled Tasks modal
- Email settings (Gmail/Exchange) in Log Analyzer Settings

---

## [S16-P10] — 2026-03-24
### Fixed
- S3 Select MethodNotAllowed → replaced with streaming get_object
- Cancel endpoint 500 (boolean response type)
- Anomaly evaluation richer response (breakdown, top_offenders, timeline)
### Changed
- No disk writes during fetch — pure in-memory streaming

---

## [S16-P9] — 2026-03-24
### Fixed
- Summary metrics: Total GB, Cache Hit ratio, Countries calculation
- Chart Y-axis readability (bytes→MB, cache status integer→label)
- Top Error Paths truncated to 50 chars
### Added
- 3 new charts: Top 10 IPs by Bandwidth, Request Volume by Hour, Anomaly Timeline
- Anomaly Rules engine with SQLite persistence
- 2 default rules for s_sport_plus tenant
- Anomaly Rules tab with CRUD and evaluation UI

---

## [S16-P8] — 2026-03-24
### Fixed
- DataFrame column diagnostic (all 22 DS2 fields confirmed)
### Added
- fetch_mode: sampled (fast, default) | full (all files, no limit)
- Full mode uses S3 paginator (no file count cap)
- Fetch Mode dropdown + Ignore Cache checkbox in UI
- Full mode warning banner

---

## [S16-P7] — 2026-03-24
### Added
- GET /log-analyzer/akamai/analysis/{job_id} — 10 chart analyses
- 10 Recharts charts in Log Analyzer tab after fetch completes
- 6 summary metric cards (Total Rows, Total GB, Avg Latency, Error Rate, Cache Hit, Countries)
- Analysis Results tab loads from DuckDB fetch_job_history
- pyarrow dependency for parquet cache support

---

## [S16-P6] — 2026-03-24
### Fixed
- S3 recursive listing bug (Delimiter="/" fix)
- boto3 blocking event loop (ThreadPoolExecutor)
- Stop button now works (cancel flag checked after every await)
### Added
- DuckDB day-based parquet cache (log_fetch_cache table)
- fetch_job_history DuckDB table
- Force refresh (ignore cache) checkbox
- MAX_FILES_PER_DAY=500, MAX_FILES_PER_JOB=2000 hard limits
- Per-prefix S3 scan logging

---

## [S16-P5] — 2026-03-24
### Fixed
- Sample values and unique count were empty (null handling bug)
- Type inference fallback using DS2_FIELD_TYPES known types
### Added
- DS2_FIELD_DESCRIPTIONS for all 22 fields
- DS2_DEFAULT_CATEGORIES auto-suggest (saved mapping takes priority)
- Description column in Log Structure table
- Category dropdown pre-selects saved/suggested value on load

---

## [S16-P3] — 2026-03-24
### Fixed
- S3 path format: logs/{cp_code}/{year}/{DD}/{MM}/{HH}/ (day before month)
- Timezone: user input UTC+3 → S3 paths converted to UTC
- .gz file decompression for both structure/analyze and fetch-range
- cp_code missing → clear error message
### Added
- cp_code field in settings table and Log Analyzer Settings UI

---

## [S16-P2] — 2026-03-24
### Added
- Log Structure tab: S3 log sampling, field analysis, category mapping
- POST /log-analyzer/structure/analyze
- POST /log-analyzer/structure/mappings
- GET /log-analyzer/structure/mappings
- field_category_mappings SQLite table
- Type inference: string/integer/float/timestamp/ip_hash/boolean
- Export Mappings JSON download
- 13 new tests (test_structure_analysis.py)

---

## [S16-P1] — 2026-03-24
### Fixed
- POST /log-analyzer/projects 405 bug
- GET /log-analyzer/settings/test-connection 404 bug
- POST /log-analyzer/bigquery/export method bug (GET→POST)
### Changed
- "Akamai Analyzer" tab renamed to "Log Analyzer"
- "BigQuery Export" tab removed, merged into Settings/GCP Settings accordion
- Settings tab restructured as 3 collapsible accordion sections
### Added
- Project selector in Log Analyzer tab
- Akamai DataStream 2 labeled sub-section in Log Analyzer tab
- Accordion.tsx component

---

## [S15] — 2026-03-24
### Added
- AkamaiLogEntry: 22 DS2 alanı, TSV parser, client_ip SHA256 hash
- charts.py: 21 DS2-uyumlu grafik, her biri (figure, summary_df) tuple
- bigquery_exporter.py: 9 kategori export (client_ip excluded)
- shared/utils/encryption.py: Fernet AES-256 credential encryption
- SQLite settings tablosu: encrypted AWS + GCP credentials
- Endpoints: settings CRUD, fetch-range, bigquery export, test-connection
- Frontend: Log Analyzer 5 tab (Projects/Akamai Analyzer/Analysis Results/Settings/BigQuery Export)
- Tests: 451 passed, 0 failed

---

## [1.1.0] — 2026-03-21 — S15: Log Analyzer Full Enhancement

### Eklendi
- Akamai DS2 22-field schema (version, cp_code, dns_lookup_time_ms, transfer_time_ms, turn_around_time_ms, client_bytes, response_body_size, content_type, cache_hit, etc.)
- TSV parser (tab-separated 22 fields) alongside existing CSV/JSON parsers
- `shared/utils/encryption.py` — Fernet AES-256 encrypt/decrypt for credentials
- `apps/log_analyzer/sub_modules/akamai/bigquery_exporter.py` — 9-category field export to BigQuery
- SQLite `settings` table (AWS/GCP credentials, encrypted storage)
- Backend endpoints: GET/POST /log-analyzer/settings, DELETE /log-analyzer/settings/credentials, POST /log-analyzer/akamai/fetch-range, GET /log-analyzer/bigquery/export, GET /log-analyzer/bigquery/jobs/{id}
- Frontend: 5-tab Log Analyzer (Projects, Akamai Analyzer with date range + 21 charts, Results, Settings with AWS/GCP, BigQuery Export with 9-category checkboxes)
- 21 revised charts matching DS2 fields: timing (4), traffic (3), response/error (3), cache (3), geo (2), content (2), client/network (2), composite (2)
- Each chart returns (figure, summary_table) tuple
- `test_settings.py` — encrypt/decrypt roundtrip, masking tests
- 451 tests (39 log analyzer + 412 rest), 0 failures, ruff clean

---

## [1.0.1] — 2026-03-21 — Release: Full Platform

### Release Summary
- **11 apps** fully implemented (backend agents + frontend UI)
- **39 tabs** across all app pages
- **448 tests**, 0 failures
- **15 frontend routes**, 0 build errors
- **9 EventBus flows** wired and integration tested
- Backend: FastAPI + 11 routers + JWT auth + seed admin user
- Frontend: Next.js 14, dark-mode-first, Recharts, Agent Chat Panel
- Auth: `POST /auth/login` with admin/admin123 returns JWT
- Health: `/health` + `/health/detailed` (SQLite, DuckDB, Redis, ChromaDB, LLM Gateway)
- Global Search: Cmd+K across incidents/alerts/tenants/runbooks
- Responsive: mobile bottom nav on <768px

---

## [1.0.2] — 2026-03-21 — S13: Targeted Fixes (3 items)

### Düzeltildi
- Seed admin user: system tenant + admin/admin123 user auto-created on startup if users table empty
- Login endpoint: `POST /auth/login` now authenticates against SQLite users table (was 501 placeholder)
- `/health/detailed` endpoint: returns status of SQLite, DuckDB, Redis, ChromaDB, LLM Gateway
- Test isolation: `test_login_not_implemented` updated to `test_login_requires_credentials` (401/500)
- 448 tests pass, 0 failures, ruff clean

---

## [1.0.1] — 2026-03-21 — S12: P2 Apps + Platform Polish

### Eklendi
- `ai-lab/page.tsx` — 5 tabs (Experiments, Model Registry, Prompt Lab, Evaluations, Cost Tracker)
  - A/B experiment table with p-value highlight, new experiment sheet
  - Model switch/config HIGH risk buttons, prompt version history
  - Token budget gauge with warning banner (>80%), cost trend charts
- `knowledge-base/page.tsx` — 4 tabs (Search, Incidents, Runbooks, Ingest)
  - Full-width search with collection/top-k selectors, relevance color-coded results
  - Auto-indexed incidents with RCA badge, runbook card grid with tag filters
  - Drag & drop ingest zone (PDF/MD/TXT), delete HIGH risk
- `devops-assistant/page.tsx` — 4 tabs (Assistant, Diagnostics, Deployments, Runbooks)
  - Terminal-like assistant: dark bg, monospace font, green prompt, command chips
  - 7-service diagnostics grid, deployment history, runbook execution HIGH risk
- `components/global-search/index.tsx` — Cmd+K search across incidents/alerts/tenants/runbooks
- Loading skeletons: all 12 routes with card/table skeleton patterns
- Error boundaries: all 12 routes with collapsible detail + retry
- Responsive mobile: sidebar → bottom nav on <768px, overflow-x tables
- Frontend build: 0 errors, 0 TypeScript errors, 15 routes

---

## [1.2.0] — 2026-03-21 — S11: P1 Apps Full Frontend Implementation

### Eklendi
- `viewer-experience/page.tsx` — 5 tabs (QoE Dashboard, Sessions, Anomalies, Complaints, Trends)
- `live-intelligence/page.tsx` — 6 tabs (Calendar, Monitor, Pre-Scale, SportRadar, DRM, EPG)
- `growth-retention/page.tsx` — 4 tabs (Retention, Churn Risk, Data Analyst, Insights)
- `capacity-cost/page.tsx` — 5 tabs (Forecast, Usage, Jobs, Cost, Thresholds)
- `admin-governance/page.tsx` — 6 tabs (Tenants, Modules, API Keys, Audit, Compliance, Usage)
- QoE color zones, churn risk progress bars, capacity gauges
- NL→SQL data analyst with query history, generated SQL, AI interpretation
- Admin role check (Access Denied for non-admin), API key rotate with one-time display
- DRM/SportRadar auto-refresh, event calendar grid, EPG schedule
- All HIGH risk actions: confirm dialogs (send campaign, create job, rotate key, delete tenant, export audit)
- Frontend build: 0 errors, 15 routes, 26 tabs across 5 P1 apps

---

## [1.1.0] — 2026-03-21 — S10: P0 Apps Full Frontend Implementation

### Eklendi
- `frontend/src/app/(apps)/ops-center/page.tsx` — Full 4-tab UI
  - Dashboard: MetricCards (open incidents, MTTR P50, active tenants, decisions 24h)
  - Incidents: filterable table (severity/status/search), detail dialog, HIGH risk action buttons
  - RCA Explorer: trigger RCA → poll 3s → result display
  - Decision Log: time range filters, RiskBadge, CSV export
  - WebSocket: useOpsWebSocket hook → toast on P0/P1
- `frontend/src/app/(apps)/log-analyzer/page.tsx` — Full 3-tab UI
  - Projects: card grid, new project sheet, sub-module select (Akamai/Medianova)
  - Akamai Analyzer: config form, fetch logs → progress bar → 21 charts grid (3 cols)
  - Analysis Results: table with expandable detail dialog, anomaly list
- `frontend/src/app/(apps)/alert-center/page.tsx` — Full 5-tab UI
  - Live Feed: WebSocket alerts, storm mode banner (>20/60s)
  - Alerts: filterable table, ack/resolve dialogs with note textarea
  - Rules: CRUD with sheet form (event_type, severity, channel)
  - Channels: Slack/PagerDuty/Email cards with status + Test button
  - Suppression: maintenance windows, weekly calendar grid
- `frontend/src/components/ui/SeverityBadge.tsx` — P0-P3 color-coded badge
- `frontend/src/components/ui/LogTable.tsx` — Generic table with hover, row click
- `frontend/src/components/charts/RechartsWrapper.tsx` — Line/bar, dark theme, no animation
- Updated: `lib/api.ts` — apiPatch, apiDelete, exportToCsv
- Updated: `lib/socket.ts` — useOpsWebSocket, useAlertWebSocket hooks
- Updated: `types/index.ts` — OpsMetrics, RCAResult, FetchJob, AlertRule, etc.
- Frontend build: 0 errors, 15 routes

---

## [1.0.0] — 2026-03-21 — S09: Cross-App Integration + Frontend + Platform Complete

### Eklendi
- Cross-app integration: all 9 EventBus flows wired and tested end-to-end
  - cdn_anomaly → ops_center + alert_center
  - incident_created → alert_center + knowledge_base (auto-index)
  - rca_completed → knowledge_base (auto-index) + alert_center
  - qoe_degradation → ops_center + alert_center
  - live_event_starting → ops_center + log_analyzer + alert_center
  - external_data_updated → ops_center + growth_retention
  - churn_risk_detected → alert_center
  - scale_recommendation → ops_center + alert_center
  - analysis_complete → growth_retention + viewer_experience
- 10 integration tests (tests/integration/test_event_flows.py) including full E2E chain
- Frontend: Next.js 14, dark-mode-first, 11 app pages + dashboard
  - Sidebar: 240px/64px, 11 apps grouped P0/P1/P2
  - Header: tenant selector + user menu
  - Components: RiskBadge, MetricCard, StatusDot, AgentChatPanel
  - Charts: TimeSeriesChart, PieChart, BarChart (Recharts, dark theme, animation:false)
  - Every page: loading.tsx + error.tsx
  - Agent Chat Panel: collapsible, bottom-right, on every page
- Backend: all 11 routers mounted in main.py (v1.0.0)
- 448 total tests, zero failures, ruff clean

---

## [0.8.0] — 2026-03-21 — S08: AI Lab + Knowledge Base + DevOps Assistant + Admin & Governance

### Eklendi
- `apps/ai_lab/` — AI Lab (M10 Experimentation + M14 Model Governance)
- ExperimentationAgent: A/B test design + statistical significance (z-test, p-value, CI)
- ModelGovernanceAgent: Haiku for routine, token budget monitoring (>80% → warning)
- switch_model_production, update_model_config → approval_required
- DuckDB reads: shared_analytics.agent_decisions (all apps' model usage)
- 30 tests, 99% coverage

- `apps/knowledge_base/` — Knowledge Base (M15)
- ChromaDB collections: 'incidents', 'runbooks', 'platform'
- Auto-index: incident_created → index, rca_completed → index
- Chunking: 500 token, 50 overlap, all-MiniLM-L6-v2 embedding
- delete_document → approval_required
- 24 tests, 99% coverage

- `apps/devops_assistant/` — DevOps Assistant (M08)
- Sonnet for technical Q&A, dangerous command detection
- Reads ChromaDB 'runbooks' collection from knowledge_base
- restart_service, execute_runbook → approval_required
- DuckDB reads: shared_analytics.incidents, agent_decisions
- 26 tests, 100% coverage

- `apps/admin_governance/` — Admin & Governance (M12 Tenant + M17 Compliance)
- TenantAgent (Haiku) + ComplianceAgent (Sonnet)
- delete_tenant, rotate_api_key, export_audit_log → approval_required
- API keys: AES-256 encrypted, response masked (sk-ant-...XXXX only)
- Every action (success + fail) → audit_log
- Admin endpoints: 'admin' JWT role required
- 34 tests, 99% coverage

- 438 total tests (114 new + 324 regression), zero failures

---

## [0.7.0] — 2026-03-21 — S07: Growth & Retention + Capacity & Cost

### Eklendi
- `apps/growth_retention/` — Growth & Retention (M18 Customer Growth + M03 AI Data Analyst)
- GrowthAgent: churn risk analysis with weighted formula (QoE + CDN + retention trend)
- churn_risk > 0.7 → churn_risk_detected published to EventBus → alert_center
- DataAnalystAgent: NL → DuckDB SQL translation, read-only, shared_analytics only
- PII protection: user_id_hash only, no raw IDs in queries
- SQL validation: SELECT-only, allowed tables whitelist enforced
- send_retention_campaign → approval_required=True
- EventBus subscribes: analysis_complete, external_data_updated
- EventBus publishes: churn_risk_detected → alert_center
- DuckDB writes: shared_analytics.agent_decisions, retention_scores
- DuckDB reads: shared_analytics.qoe_metrics, cdn_analysis, live_events
- `/growth` API endpoints: health, retention, churn-risk, segments, query
- 36 unit tests, 98% coverage

- `apps/capacity_cost/` — Capacity & Cost (M16 Capacity Planning + M04 Automation)
- CapacityAgent: capacity forecasting, threshold breach detection (warn 70%, crit 90%)
- AutomationAgent: Haiku for routine automation, multi-step workflows
- create_automation_job → approval_required=True
- execute_scale_action → approval_required=True
- publish_scale_recommendation → EventBus: scale_recommendation → ops_center, alert_center
- EventBus subscribes: live_event_starting (pre-scale trigger for >50k viewers)
- DuckDB writes: shared_analytics.agent_decisions
- DuckDB reads: shared_analytics.live_events, qoe_metrics
- `/capacity` API endpoints: health, forecast, usage, jobs, cost
- 32 unit tests, 99% coverage
- 324 total tests (68 new + 256 regression), zero failures

---

## [0.6.0] — 2026-03-19 — S06: Live Intelligence

### Eklendi
- `apps/live_intelligence/` — Live Intelligence (M05 Live Event + M11 External Data)
- LiveEventAgent: live_event_starting published exactly 30 min before kickoff
- ExternalDataAgent: Haiku for batch processing, publishes external_data_updated on changes
- DRM tracking: Widevine + FairPlay + PlayReady status
- Poll intervals: SportRadar 30s, DRM 60s, EPG 300s
- Redis TTLs: active_event=60s, pre_scale_status=3600s, drm_status=60s, sportradar=30s
- trigger_pre_scale, override_drm_fallback → approval_required
- DuckDB writes: live_events, agent_decisions; reads: qoe_metrics, incidents
- `/live` API endpoints: health, events, drm status
- 36 unit tests, 98% coverage

---

## [0.5.0] — 2026-03-19 — S05: Viewer Experience

### Eklendi
- `apps/viewer_experience/` — Viewer Experience (M02 QoE + M09 Complaints)
- QoEAgent: exact QoE score formula (0.0-5.0), score < 2.5 → qoe_degradation event
- ComplaintAgent: NLP category + sentiment + priority, ChromaDB similar search
- Session dedup: same session_id within 5 min window skipped
- escalate_complaint → approval_required=True
- EventBus publishes: qoe_degradation → ops_center, alert_center
- EventBus subscribes: analysis_complete, live_event_starting
- DuckDB writes: shared_analytics.qoe_metrics, agent_decisions
- `/viewer` API endpoints: health, qoe/metrics, complaints
- 37 unit tests, 95% coverage

---

## [0.4.0] — 2026-03-19 — S04: Alert Center

### Eklendi
- `apps/alert_center/` — Alert Center (M13 Alert Router)
- AlertRouterAgent: subscribes to all 7 cross-app events
- Routing logic: P0→Slack+PagerDuty, P1→Slack, P2→Slack, P3→Email
- Dedup: 900s Redis TTL fingerprint window (alert:dedup:{tenant_id}:{fingerprint})
- Storm detection: >10 alerts/5min → storm mode → single summary (approval_required)
- route_to_pagerduty → approval_required=True (P0 only)
- suppress_alert_storm → approval_required=True
- DuckDB writes: shared_analytics.alerts_sent
- `/alerts` API endpoints: health, list, rules, channels
- 29 unit tests, 98% coverage

---

## [0.3.0] — 2026-03-19 — S03: Ops Center

### Eklendi
- `apps/ops_center/` — Ops Center (M01 AI Incident Copilot + M06 RCA Engine)
- IncidentAgent: severity-based LLM routing (P0/P1→Opus, P2→Sonnet, P3→Haiku)
- RCAAgent: always Opus, only triggers for P0/P1 incidents
- 10 risk-tagged tools (execute_remediation, escalate_to_oncall → approval_required)
- Bilingual output: Turkish summary + English technical detail on every incident
- EventBus publish: incident_created, rca_completed
- EventBus subscribe: cdn_anomaly_detected, qoe_degradation, live_event_starting
- DuckDB reads: shared_analytics.cdn_analysis (from S02 log_analyzer)
- DuckDB writes: shared_analytics.incidents, agent_decisions
- `/ops` API endpoints: health, dashboard, incidents
- Correlation engine: CDN + QoE + incident cross-referencing
- 32 unit tests, 98% coverage

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
