# CHANGELOG.md — AAOP Platform Sürüm Geçmişi
> Sprint bittiğinde Claude Code tarafından güncellenir.
> Format: Keep a Changelog | Semantic Versioning 2.0

---

## [Unreleased]

_S11: P1 apps full frontend in progress._

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
