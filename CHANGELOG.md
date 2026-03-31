# CHANGELOG.md — AAOP Platform Sürüm Geçmişi
> Sprint bittiğinde Claude Code tarafından güncellenir.
> Format: Keep a Changelog | Semantic Versioning 2.0

---

## [Unreleased]

---

### S-OPS-FIX-01 — 2026-03-31
- ops-center/page.tsx: Add Incident slide-over form (title, severity, description, affected_service)
  - POST /ops/incidents submit (graceful error if endpoint missing)
- ops-center/page.tsx: RCA Explorer — P0/P1 incident dropdown + GET /incidents/{id}/rca
  - Root causes, timeline, recommended actions display
- ops-center/page.tsx: Decision Log — fixed data fetching, snake_case→camelCase mapping
- ops-center/page.tsx: s_sport_plus → ott_co (tüm API çağrıları)
- Note: POST /ops/incidents backend endpoint henüz mevcut değil — S-OPS-API-01'de eklenecek
- Tests: 181 passed, 0 failure

---

### S-DASH-FIX-01 — 2026-03-31
- frontend/src/app/page.tsx: statik 72 satır → API-wired 180+ satır dashboard
  - 4 KPI kartı: Active Incidents, Events 24h, MTTR P50, Avg QoE Score
  - 3 widget: SLO Status (X/Y met), CDN Health (error rate + cache hit), Severity Breakdown (bar chart)
  - Incident Trend 24h (bar chart)
  - Live Anomaly Feed (30s polling, son 10 anomali)
  - Recent Agent Decisions (son 5 karar)
  - Applications grid (11 app, icon + link)
- Endpoint'ler: /ops/dashboard, /slo/status, /realtime/anomalies, /ops/decisions
- Tests: 181 passed, 0 failure

---

### S-UI-FIX-01 — 2026-03-31
- Sidebar.tsx: separator başlıkları (P0/P1/P2/DEV) kaldırıldı — temiz nav
- Settings/page.tsx: dark/light toggle classList.toggle('dark') eklendi
- layout.tsx: dark class + inline script ile tema flash önleme
- Login/page.tsx: demo credentials butonu eklendi (auto-fill)
- Alert-center/page.tsx: window.alert() → inline toast (3s auto-hide)
- ServiceSwitcher.tsx: cursor-pointer + title tooltip tüm roller için
- Tests: 181 passed, 0 failure

---

### S-DATA-RESEED-01 — 2026-03-31
- analytics.duckdb: tenant_id migrated (s_sport_plus/bein_sports/aaop_company → ott_co)
  - 50 incidents, 204 agent_decisions, 200 qoe_metrics, 15 live_events, 100 retention_scores all → ott_co
- shared/ingest/log_queries.py: tenant→schema mapping eklendi
  - `_resolve_schema(tenant_id)`: ott_co → aaop_company (DuckDB schema)
  - `_resolve_row_tenant(tenant_id)`: ott_co → aaop_company (row-level tenant_id)
  - 11 fonksiyon + 38 WHERE clause güncellendi
- scripts/migrate_tenant_data.py: one-shot migration script
- Tests: 181 passed, 0 failure

---

### S-SHARED-SPEC-01 — 2026-03-30
- shared/SHARED_MODULES.md: kapsamlı shared modül spec dosyası (~400 satır)
  - 12 modül bölümü, cross-module bağımlılık haritası, kırılma noktaları, test gereksinimleri
- CLAUDE.md: SHARED_MODULES.md doküman haritasına + klasör yapısına eklendi

---

### S-DOC-HEALTH — 2026-03-30 — Periyodik Dokümantasyon Sağlık Kontrolü

#### Tespit Edilen Tutarsızlıklar
- CLAUDE.md: test sayısı 148→181 (stale), sprint S-AGENT-06→S-RT-01, 3 yeni shared modül eksik, 3 router eksik
- ARCHITECTURE.md: SLO, NL Query, Realtime Engine bölümleri eksik
- API_CONTRACTS.md: /slo/ (8 ep), /nl-query/ (3 ep), /realtime/ (3 ep) = 14 endpoint eksik

#### Yapılan Güncellemeler
- CLAUDE.md: test 181, sprint S-RT-01, shared/slo + nl_query + realtime eklendi, 3 router eklendi, nl-query + settings sayfaları eklendi
- ARCHITECTURE.md: Bölüm 10 SLO, 11 NL Query, 12 Realtime Engine eklendi
- API_CONTRACTS.md: 1B SLO (8), 1C NL Query (3), 1D Realtime (3) bölümleri eklendi
- CHANGELOG.md: S-DOC-HEALTH entry

#### Temiz Bulunan Dosyalar
- Tüm 12 spec dosyası (son sprint'lerden güncel)
- .gitignore (güncel)
- pyproject.toml (değişiklik gerekmedi)

#### Metrikler
- Test sayısı: 181 (CLAUDE.md'de: 148 → 181 düzeltildi)
- Endpoint sayısı: 169 (165 REST + 4 WS)
- Uyuşma oranı: Önceki ~70% → Şimdiki ~95%

---

### S-RT-01 — 2026-03-30
- shared/realtime/: AnomalyEngine + 4 detectors (cdn, drm, qoe, api)
  - CDN: error_rate >0.05 P1, >0.15 P0
  - DRM: failure_rate >0.10 P1
  - QoE: avg_score <2.5 P1, <1.5 P0
  - API: error_rate >0.05 P2, p99 >2000ms P2
- backend/routers/realtime.py: 3 endpoint (anomalies, status, detector toggle)
- backend/main.py: AnomalyEngine lifespan (30s polling, startup skip)
- frontend/ops-center: Live Anomaly Feed (30s polling, severity badges)
- EventBus entegrasyonu: cdn_anomaly_detected + qoe_degradation publish
- Tests: 181 passed (148 + 8 SLO + 12 NL + 13 RT), 0 failure

---

### S-NL-01 — 2026-03-30
- shared/nl_query/: NLEngine + SchemaRegistry (18 tablo) + SQLValidator (6 güvenlik kontrolü)
  - PII koruma: client_ip, subscriber_id SELECT/WHERE'de yasak
  - Write koruma: INSERT/UPDATE/DELETE/DROP engelli
  - tenant_id filtresi zorunlu, LIMIT zorunlu (max 1000)
- backend/routers/nl_query.py: 3 endpoint (query, tables, examples)
- backend/main.py: nl_query_router mount
- frontend/src/app/(apps)/nl-query/page.tsx: standalone NL query sayfası
  - Örnek sorgular (chip), tablo browser, SQL görüntüleme, sonuç tablosu
- frontend/src/components/layout/Sidebar.tsx: NL Query link eklendi
- Tests: 168 passed (148 + 8 SLO + 12 NL), 0 failure

---

### S-SLO-01 — 2026-03-30
- shared/slo/: SLOCalculator (5 metrik: availability, qoe_score, cdn_error_rate, api_p99, incident_mttr)
- backend/routers/slo.py: 8 endpoint (definitions CRUD, status, history, calculate, report)
- backend/main.py: SLO router mount + 5 varsayılan SLO seed (tenant başına)
- frontend/admin-governance: SLO Tracking tab (kart grid, error budget bar, calculate now)
- frontend/ops-center: SLO summary widget (X/Y SLO Met)
- SQLite: slo_definitions + slo_measurements tabloları
- Tests: 156 passed (148 + 8 SLO), 0 failure

---

### S-AGENT-06 — 2026-03-30 (commit: c5450d19)
- alert_center/tools.py: check_suppression → SQLite suppression_rules lookup (was hardcoded False)
- live_intelligence/tools.py: get_epg_schedule → logs.duckdb epg_logs query via log_queries helper (was empty [])
- devops_assistant/tools.py: check_service_health → newrelic+api logs real health (was hardcoded "healthy")
  - error_rate >0.05 → degraded, >0.15 → down
- ops_center/tools.py: trigger_rca → RCAAgent invoke for P0/P1, skip for P2+ (was logger only)
- Tests: 148 platform + 188 app tests passed, 0 failure

---

### S-SETTINGS-01 — 2026-03-30 (commit: 2c831d5f)
- backend/auth.py: PATCH /auth/password (bcrypt verify + strength validation + update)
- backend/routers/admin_governance.py: PATCH /admin/tenant/sector + PATCH /admin/modules/{id} + GET /admin/modules
- frontend/src/app/(apps)/settings/page.tsx: 4 bölümlü settings sayfası
  - Security: şifre değiştirme + auto-logout
  - Appearance: dark/light tema toggle (localStorage, anlık geçiş)
  - Tenant Sector: OTT/Telecom/Broadcast/Airline/Other (tenant_admin+ only)
  - Module Management: 11 app toggle, P0 modüller kilitli
- frontend/src/components/layout/Header.tsx: user dropdown menü + Settings link
- P0 modüller (ops_center, log_analyzer, alert_center) devre dışı bırakılamaz
- Tests: 148 passed, 0 failure

---

### S-DATA-FIX-01 — 2026-03-30 (commit: 219de56e)
- medianova_logs: double timezone bug (+00:00Z) → DuckDB read_json native ingest, 1,343,539 satır
  - Root cause: generator timestamp format "+00:00Z" (double TZ), sync_engine batch insert çok yavaş
  - Fix: DuckDB read_json_auto ile glob pattern, REPLACE ile timestamp cleanup
- crm_subscriber_logs: 552,900 NULL timestamp → synthetic distribution (28 gün)
  - Root cause: CRM mock data dosyaları üretilmemiş, ingest pipeline boş kayıt oluşturmuş
  - Fix: ROW_NUMBER % 28 ile tarih dağıtımı, subscriber_id/tier/country/device dolduruldu
- sport_stream schema: her iki tablo güncellendi (kopyalandı)
- Tests: 148 passed, 0 failure

---

### S-MT-04 — 2026-03-30 (commit: e8cf6827)
- SQLite: users.tenant_id NOT NULL → nullable (tablo rebuild migration)
- super_admin tenant_id → NULL, tüm service erişimi korunuyor
- frontend/contexts/AuthContext.tsx: switchService(), logout(), localStorage sync
- frontend/components/layout/ServiceSwitcher.tsx: tenant/service dropdown (role-based)
  - service_user: sadece göster, dropdown yok
  - tenant_admin: service switch dropdown
  - super_admin: tüm tenant/service hiyerarşik liste
- frontend/components/layout/Header.tsx: active service badge + user info
- frontend/components/layout/Sidebar.tsx: ServiceSwitcher entegrasyonu
- frontend/app/layout.tsx: AuthProvider wrapper
- frontend/app/(apps)/admin-governance/tenants/page.tsx: Platform Admin sayfası
- backend/routers/admin_governance.py: GET /admin/platform/tenants endpoint
- frontend/src/lib/api.ts: default tenant s_sport_plus → ott_co
- Tests: 148 passed, 0 failure

---

### S-MT-03 — 2026-03-30 (commit: 2cb040c5)
- scripts/seed_demo_tenants.py: DuckDB SQL-native bulk data generation
  - tv_plus: 1,372,000 rows (5 tablo, 28 gün, 0 gap) — OTT/IPTV profili
  - music_stream: 392,000 rows (5 tablo, 28 gün, 0 gap) — müzik streaming profili
  - fly_ent: 252,000 rows (5 tablo, 28 gün, 0 gap) — havayolu IFE profili
  - Toplam: 2,016,000 yeni satır
- docs/data_audit_report_v2.md: 4 aktif schema audit raporu
- super_admin: tenant_id = 'ott_co' (NOT NULL constraint), tüm service erişimi korunuyor
- Tests: 148 passed, 0 failure

---

### S-MT-02 — 2026-03-30 (commit: 7c477020)
- backend/auth.py: multi-tenant JWT payload (service_ids, active_service_id, role)
  - POST /auth/login: JSON body (tenant_id + email + password)
  - POST /auth/switch-service: JWT-based service switch (403 if unauthorized)
  - GET /auth/tenants: public endpoint for login page dropdown
  - POST /auth/login/form: legacy OAuth2 form login (backward compat)
- backend/dependencies.py: tenant cleanup (system, s_sport_plus, bein_sports, tivibu silindi)
  - 5 demo kullanıcı seed (Captain2026! şifre)
  - super_admin, tenant_admin, service_user rolleri
- backend/middleware/service_context.py: stub → tam JWT implementasyon
  - Authorization header decode → active_service_id → duckdb_schema
  - In-memory schema cache (TTL 5dk)
- frontend/src/app/login/page.tsx: tenant dropdown + email/password form
- Tests: 148 passed, 0 failure

---

### S-MT-01 — 2026-03-29 (commit: 8d607fdd)
- Multi-tenant 3-katman hiyerarşi: super_admin → tenant → service
- SQLite: tenants tablosu (3 kayıt: ott_co, tel_co, airline_co) + services tablosu (4 kayıt: sport_stream, tv_plus, music_stream, fly_ent)
- SQLite migration: sector, status, updated_at (tenants), service_ids, active_service_id (users)
- DuckDB: sport_stream schema oluşturuldu (aaop_company kopyası, 13 tablo, 45.6M satır)
- shared/models/tenant_models.py: TenantBase, ServiceBase, TenantWithServices Pydantic modelleri
- backend/middleware/service_context.py: ServiceContextMiddleware stub (tenant → default service mapping)
- shared/clients/logs_duckdb_client.py: schema_name parametresi eklendi (backward compat)
- backend/dependencies.py: _seed_tenant_hierarchy() idempotent seed
- aaop_company schema korundu (silinmedi)
- Tests: 148 passed, 0 failure

---

### S-EB-01 — 2026-03-29
- shared/event_bus.py: queue recreation on start() (cross-loop fix)
- backend/main.py: lifespan'da Event Bus başlatma/durdurma + _wire_event_subscriptions()
- 8 agent'a subscribe_events() + _on_event handler eklendi:
  - ops_center IncidentAgent: cdn_anomaly, qoe_degradation, live_event, scale_recommendation, external_data (5)
  - alert_center AlertRouterAgent: cdn_anomaly, incident, rca, qoe, live_event, churn, scale (7)
  - viewer_experience QoEAgent: analysis_complete, live_event_starting (2)
  - growth_retention GrowthAgent: external_data_updated, analysis_complete (2)
  - capacity_cost CapacityAgent: live_event_starting (1)
  - knowledge_base KnowledgeBaseAgent: incident_created, rca_completed (2)
- ARCHITECTURE.md: Event Bus ⚠️ → ✅ güncellendi
- Tests: 148 passed, 0 failure

---

### S-AGENT-05 — 2026-03-29
- apps/ai_lab/agent.py: ExperimentationAgent + ModelGovernanceAgent concrete implementation
  - ExperimentationAgent: A/B test statistical significance, Sonnet
  - ModelGovernanceAgent: budget warning (>80%), action mapping, Haiku
- apps/knowledge_base/agent.py: KnowledgeBaseAgent concrete implementation
  - Auto-index incident_created + rca_completed events via ChromaDB
  - Search/delete/ingest pipeline, Haiku
- apps/devops_assistant/agent.py: DevOpsAssistantAgent concrete implementation
  - Action mapping: diagnose/restart/runbook/suggest/search_runbooks
  - P3→Haiku, default→Sonnet (technical analysis)
  - restart_service + execute_runbook → HIGH risk approval
- Tests: 148 passed (platform) + 21 passed (3 app agent tests), 0 failure

---

### S-AGENT-04 — 2026-03-29
- apps/viewer_experience/agent.py: QoEAgent + ComplaintAgent concrete implementation
  - QoEAgent: QoE scoring (dedup→score→degrade event), P0/P1→Sonnet, diğer→Haiku
  - ComplaintAgent: NLP kategorizasyon (category/sentiment/priority), her zaman Sonnet
  - qoe_degradation event publish (score < 2.5)
- apps/live_intelligence/agent.py: LiveEventAgent + ExternalDataAgent concrete implementation
  - LiveEventAgent: 30dk öncesinden live_event_starting publish, scale_factor hesaplama, Sonnet
  - ExternalDataAgent: veri değişimi tespiti, external_data_updated publish, Haiku
- apps/growth_retention/agent.py: GrowthAgent + DataAnalystAgent concrete implementation
  - GrowthAgent: churn risk hesaplama, churn_risk_detected publish (>0.7), Sonnet
  - DataAnalystAgent: NL→SQL üretimi + validasyon, P3→Haiku diğer→Sonnet
- apps/capacity_cost/agent.py: CapacityAgent + AutomationAgent concrete implementation
  - CapacityAgent: threshold breach (warn 70%, crit 90%), scale_recommendation publish, Sonnet
  - AutomationAgent: job creation + scale actions, Haiku
- apps/admin_governance/agent.py: TenantAgent + ComplianceAgent concrete implementation
  - TenantAgent: admin role check + action mapping, Haiku
  - ComplianceAgent: violation detection (high_risk + approval_rate < 95%), Sonnet
- Tests: 148 passed (platform) + 48 passed (5 app agent tests), 0 failure

---

### S-AGENT-03 — 2026-03-29
- apps/log_analyzer/agent.py: LogAnalyzerAgent concrete implementation
  - get_tools(): 12 tool (8 LOW + 3 MEDIUM + 1 HIGH) BaseAgent-uyumlu wrapper
  - get_llm_model(): P0→Opus, P3→Haiku, diğer→Sonnet
  - cdn_anomaly_detected + analysis_complete event publish
  - No-data erken dönüş (metrics yoksa)
- apps/alert_center/agent.py: AlertRouterAgent concrete implementation
  - Routing pipeline: dedup → suppression → storm → route (invoke override)
  - get_tools(): 10 tool (5 LOW + 3 MEDIUM + 2 HIGH)
  - get_llm_model(): P0/P1→Sonnet, P2/P3→Haiku
  - P0→Slack+PagerDuty(approval), P1/P2→Slack, P3→Email
  - Storm: >10 alert/5dk → storm_summary + approval_required
- Tests: 148 passed (platform) + 7 log_analyzer + 9 alert_center, 0 failure

---

### S-AGENT-02 — 2026-03-29
- apps/ops_center/agent.py: IncidentAgent + RCAAgent concrete implementation
  - IncidentAgent.get_tools(): 10 tool (4 LOW + 4 MEDIUM + 2 HIGH) BaseAgent-uyumlu wrapper
  - IncidentAgent.get_system_prompt(): INCIDENT_SYSTEM_PROMPT
  - IncidentAgent.get_llm_model(): P0/P1→Opus, P2→Sonnet, P3→Haiku
  - IncidentAgent._memory_update_node(): bilingual output (summary_tr + detail_en), incident_created event publish
  - RCAAgent.get_tools(): 5 tool (4 LOW + 1 MEDIUM)
  - RCAAgent.get_system_prompt(): RCA_SYSTEM_PROMPT
  - RCAAgent.get_llm_model(): her zaman Opus
  - RCAAgent.invoke(): P0/P1 dışında erken dönüş
  - RCAAgent._memory_update_node(): rca_completed event publish, confidence_score
- apps/ops_center/tests/test_agent.py: 15 test (model routing, event publish, bilingual, RCA skip)
- Tests: 148 passed, 0 failure (tests/ altında) + 52 passed (apps/ops_center/tests/)

---

### S-AGENT-01 — 2026-03-29
- shared/agents/base_agent.py: LangGraph StateGraph 4-adım cycle tam implementasyon
  - context_loader: Redis cache → DuckDB recent decisions → ChromaDB RAG
  - reasoning: LLM invoke + JSON parse + fallback + model routing (P0/P1→Opus, P2→Sonnet)
  - tool_execution: LOW=auto, MEDIUM=auto+EventBus notify, HIGH=approval_required
  - memory_update: DuckDB agent_decisions write + Redis context cache + structured output
- AgentState TypedDict: tenant_id, input, context, reasoning, tool_results, output, approval_required, error
- Abstract methods: get_tools(), get_system_prompt(), get_llm_model()
- Public API: invoke(tenant_id, input_data) + legacy run(tenant_context, input_data)
- Conditional edge: HIGH risk → END (approval gate), else → memory_update
- tests/unit/test_base_agent.py: 15 test (context loader, reasoning, tool execution, memory update, model routing, graph compilation)
- tests/integration/test_event_flows.py: full chain test güncellendi (yeni AgentState formatına uyum)
- ARCHITECTURE.md: BaseAgent stub notu ✅ olarak güncellendi
- Tests: 148 passed, 0 failure

---

### S-WS-01 — 2026-03-29
- backend/websocket/manager.py: WebSocketManager tam implementasyon (connect/disconnect/broadcast per tenant+app)
- backend/main.py: 4 WS endpoint mount edildi (/ws/ops/incidents, /ws/alerts/stream, /ws/viewer/qoe, /ws/live/events)
- backend/routers/ops_center.py: incident update broadcast eklendi
- backend/routers/alert_center.py: alert evaluate broadcast eklendi
- frontend/src/lib/socket.ts: MockSocket → AppWebSocket (native WS, auto-reconnect 3s)
- tests/unit/test_websocket_manager.py: 2 test (broadcast + disconnect)
- Tests: 126 passed, 0 failure

---

### S-SEC-01 — 2026-03-29
- backend/main.py: RateLimitMiddleware mount edildi (100 req/min per tenant)
- shared/llm_gateway.py: PII scrubber tüm LLM çağrılarına eklendi (scrub() prompt + system_prompt'a uygulanır)
- backend/dependencies.py: Default admin şifresi settings.admin_password'den okunuyor
- shared/utils/settings.py: admin_password field eklendi
- .env.example: ADMIN_PASSWORD eklendi
- Güvenlik durumu: Rate limiting ✅ | PII scrubbing ✅ | Hardcoded credential ✅ env var'a taşındı
- Tests: 125 passed, 0 failure

---

### S-DOC-02 — 2026-03-29
- CLAUDE.md: Aktif sprint güncellendi, shared/ingest/ + backend/models/ + docs/kb/ + logs.duckdb eklendi
- ARCHITECTURE.md: Agent stub notu, Event Bus runtime notu, WebSocket notu eklendi
- API_CONTRACTS.md: 3 eksik endpoint eklendi, WebSocket implementasyon uyarısı eklendi
- 8 stale spec dosyası: S-DI-03/S-DI-04 logs.duckdb entegrasyon notları eklendi
- ops_center_spec.md: Agent stub durumu notu eklendi
- Temel bulgular: Uyuşma %57 → hedef %90+ | 7 kritik eksik CLAUDE.md'de kapatıldı | 12 endpoint gap kapatıldı

---

### S-DI-04 — 2026-03-28
- shared/ingest/log_queries.py: 5 yeni helper (get_app_reviews, get_epg_schedule, get_churn_metrics, get_billing_summary, get_data_source_stats)
- backend/routers: 7 P1/P2 modül logs.duckdb'den gerçek veri okur (viewer_experience, live_intelligence, growth_retention, capacity_cost, admin_governance, devops_assistant)
- frontend: 8 sayfadan empty state kaldırıldı, gerçek veri akışı aktif
- Tüm modüller artık logs.duckdb üzerinden çalışıyor
- Tests: 14 passed (test_log_queries.py)

---

### S-DI-03 — 2026-03-28
- shared/ingest/log_queries.py: 7 query helper (get_cdn_metrics, get_cdn_anomalies, get_drm_status, get_api_health, get_infrastructure_health, get_player_qoe, detect_incidents_from_logs)
- backend/routers/ops_center.py: dashboard CDN/QoE/infra kartları logs.duckdb'den, chat context zenginleştirildi
- backend/routers/log_analyzer.py: 4 yeni Medianova endpoint (dashboard, timeseries, anomalies, analyze)
- backend/routers/alert_center.py: CDN/DRM/API status badge'leri + POST /alerts/evaluate
- frontend/ops-center/page.tsx: CDN Health + Infrastructure + QoE kartları eklendi
- frontend/log-analyzer/page.tsx: Medianova tab eklendi (KPI, time series, anomaliler, analyze)
- frontend/alert-center/page.tsx: Evaluate Now butonu eklendi
- tests/unit/test_log_queries.py: 9 test (mock DataFrame ile)
- tests/unit/test_data_ingestion.py: 2 yeni test (toplam 25)
- Incident detection thresholds: CDN >5% P1, >15% P0 | DRM >10% P1 | API p99 >2s P2 | Apdex <0.7 P2 | QoE <2.5 P1

---

### S-DI-02-fix — 2026-03-28
- ingestion_log SQLite tablosu yeniden oluşturuldu (file_mtime kolonu eksikti)
- backend/routers/data_sources.py: migration guard eklendi (PRAGMA table_info + ALTER TABLE ADD COLUMN file_mtime)
- shared/ingest/watch_folder.py: process_existing_files() startup scan düzeltildi
- shared/ingest/default_configs.py: local_path /{DEFAULT_TENANT}/ segment eksikliği giderildi
- watchdog kuruldu (pip install watchdog)
- Startup sync sonucu: 62,335 dosya tarandı, 45,650,663 satır import edildi, 26,047 dosya lokalden silindi
- logs.duckdb: 13 kaynak, aaop_company tenant, tam veri yüklü

---

### S-DI-02 — 2026-03-27
- shared/ingest/watch_folder.py: LogFolderWatcher + LogFileHandler — watchdog, 14 klasör mapping, 2s debounce, otomatik sync+delete
- shared/ingest/default_configs.py: aaop_company için 14 kaynak config otomatik seed (idempotent)
- shared/ingest/sync_engine.py: mtime-based upsert (unchanged→skip, changed→reprocess), delete_source_file(), delete_after_import flag
- shared/ingest/source_config.py: akamai_ds2 eklendi, FOLDER_TO_SOURCE mapping (14 giriş), file_mtime ingestion_log, files_deleted SyncResult
- backend/main.py: seed_default_configs + LogFolderWatcher start/stop lifespan
- backend/routers/data_sources.py: POST /import-delete/{config_id} + GET /watch-status
- frontend/admin-governance/page.tsx: Watch Status bölümü, Import & Delete butonu, kaynak başına watch göstergesi
- pyproject.toml: watchdog >=3.0.0 eklendi
- .env.example: MOCK_DATA_BASE_PATH + LOGS_DUCKDB_PATH eklendi
- tests/unit/test_data_ingestion.py: 8 yeni test (toplam 21)
- Base path: /Users/fatihayaz/Documents/Projects/AAOP/aaop-mock-data/aaop_company/

---

### S-DI-01 — 2026-03-27
- shared/clients/logs_duckdb_client.py: LogsDuckDBClient — logs.duckdb yönetimi, tenant schema izolasyonu, batch insert, 30 gün retention
- shared/ingest/__init__.py: package init
- shared/ingest/source_config.py: SourceConfig/SourceConfigCreate/SyncResult Pydantic v2 modelleri + SQLite DDL (data_source_configs, ingestion_log)
- shared/ingest/log_schemas.py: 13 kaynak için DuckDB CREATE TABLE (tenant schema bazlı)
- shared/ingest/jsonl_parser.py: JSONL.gz parser tüm 13 kaynak + directory scanner
- shared/ingest/sync_engine.py: SyncEngine — file-level sync, skip-already-ingested, delete >30 days from cache
- shared/ingest/query_router.py: QueryRouter — hot path (DuckDB ≤30 gün) / cold path (source >30 gün) / mixed
- backend/routers/data_sources.py: 8 endpoint (source config CRUD, sync, sync-all, sync-status, query)
- backend/main.py: data_sources_router mount, seed calls kaldırıldı, logs.duckdb startup init
- frontend/src/app/(apps)/admin-governance/page.tsx: Data Sources tab (7. tab) — 13 kaynak kartı, config panel, sync status tablosu
- frontend: 11 sayfaya empty state eklendi ("No data available — connect a data source")
- tests/unit/test_data_ingestion.py: 13 test, 0 failures
- Tenant: aaop_company (default tenant, logs.duckdb schema izolasyonu)

---

### S-MDG-10 — 2026-03-26
- backend/routers/mock_data_gen.py: GET /mock-data-gen/sources/{source_name}/fields endpoint (type + sample value per field)
- frontend/src/app/(apps)/mock-data-gen/page.tsx: Step 2 redesigned — two-panel layout (left: source list with live field counts, right: relationship fields + other fields)
- Relationship detection: frontend-only, field name overlap across selected sources → join keys
- Relationship fields: amber-themed, auto pre-checked, link indicator showing cross-source connection
- Other fields: checkbox + type (monospace) + sample value
- Action bar: live summary "{total} fields · {n} join keys"
- Tests: 10 passed, 0 failures

---

### S-MDG-09 — 2026-03-26
- backend/routers/mock_data_gen.py: POST /jobs/{job_id}/cancel endpoint added, asyncio.Task.cancel() support
- frontend/src/app/(apps)/mock-data-gen/page.tsx: Stop button (visible only when status=running), page renamed to "Data Generation & Extraction"
- frontend/src/components/layout/Sidebar.tsx: label renamed to "Data Generation & Extraction"
- backend/models/export_schema.py: Pydantic v2 models (FieldSelection, JoinKey, ExportSchema, ExportSchemaCreate)
- backend/routers/mock_data_gen.py: 5 new Export Schema endpoints (GET/POST/DELETE schemas, export/sql)
- frontend/src/app/(apps)/mock-data-gen/page.tsx: Export Schema tab (3rd tab) — two-panel layout, new schema flow (2 steps), SQL modal
- JOIN_KEY_CATALOG: 17 cross-source join key rules across 9 source pairs
- SQLite: export_schemas table added to platform.db
- Tests: 10 passed (existing test_run_validate.py)

---

### S-MDG-08 — 2026-03-26
- apps/mock_data_gen/run_all.py: 13 source registry, argparse --start/--end/--sources, sequential runner
- apps/mock_data_gen/validate.py: 8 korelasyon check, run_all_checks()
- apps/mock_data_gen/requirements.txt: pydantic, structlog, faker
- backend/routers/mock_data_gen.py: 6 endpoint (sources, schema, generate, jobs, output/summary, validate)
- backend/main.py: mock_data_gen_router mount eklendi
- frontend/mock-data-gen/page.tsx: Generator tab (source selector, date range, progress, validate) + Schema Browser (field table, category filter, export JSON)
- tests/test_run_validate.py: 10 test passed
- Tests: 156 passed toplam (26+18+18+19+19+25+21+10)
- mock_data_gen modülü TAMAMLANDI — 13 kaynak, 8 sprint, 156 test

---

### S-MDG-07 — 2026-03-26
- generators/push_notifications/schemas.py: PushNotificationEntry 27 alan, 10 notification_type, Türkçe templates
- generators/push_notifications/generator.py: match reminder/starting/score, system_alert CDN outage + FairPlay ios-only, service_restored +32dk, open rate dağılımları
- generators/app_reviews/schemas.py: AppReviewEntry 19 alan, sentiment/category/topics
- generators/app_reviews/generator.py: 15-30/gün normal, 250+ CDN outage, 400+ ElClasico, FairPlay ios DRM dominant, developer response %15-35
- tests/test_push_reviews.py: 21 test passed (Push 11 + Reviews 10)
- Tests: 146 passed toplam (26+18+18+19+19+25+21)

---

### S-MDG-06 — 2026-03-26
- generators/crm/schemas.py: SubscriberProfile 50+ alan, SubscriberDailyDelta, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/crm/generator.py: 485K base CSV + daily delta, churn risk formula, calendar effects
- generators/epg/schemas.py: EPGProgram 23 alan, capacity/pre-scale fields
- generators/epg/generator.py: 6 kanal, 24h schedule, pre_scale_required >50K, ElClasico 420K+
- generators/billing/schemas.py: BillingLogEntry 26 alan, 8 event_type
- generators/billing/generator.py: monthly renewal spike 85K, holiday fail %8, CDN outage cancellations
- tests/test_crm_epg_billing.py: 25 test passed (CRM 7 + EPG 8 + Billing 8 + schema 2)
- Tests: 125 passed toplam (26+18+18+19+19+25)

---

### S-MDG-05 — 2026-03-26
- generators/api_logs/schemas.py: APILogEntry 16 alan, 13 endpoint, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/api_logs/generator.py: 280K/gün normal, 2.8M derby, CDN outage 503, rate limit 429
- generators/newrelic/schemas.py: NewRelicAPMEntry 20 alan, 3 event_type, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/newrelic/generator.py: 5 servis profili, dakika bazlı APM, 60s infra, derby pod scaling (4→16), CDN outage apdex 0.12
- tests/test_api_newrelic.py: 19 test passed (API 10 + NewRelic 9)
- Tests: 100 passed toplam (26+18+18+19+19)

---

### S-MDG-04 — 2026-03-26
- generators/player_events/schemas.py: PlayerEventEntry 30 alan, 7 event_type, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/player_events/generator.py: session chain (start→buffer→bitrate→error→seek→end), QoE formula, 50K session/gün normal, derby/outage degradation
- generators/npaw/schemas.py: NPAWSessionEntry 25 alan, youbora_score/qoe_score
- generators/npaw/generator.py: post-session agregat, Player Events korelasyonlu (session_id, qoe ±0.1, rebuf ±5%)
- tests/test_player_npaw.py: 19 test passed (Player 11 + NPAW 8)
- Tests: 81 passed toplam (26 + 18 + 18 + 19)

---

### S-MDG-03 — 2026-03-26
- generators/drm_widevine/schemas.py: WidevineLogEntry 29 alan, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/drm_widevine/generator.py: 120K/gün normal, session chain, L1/L3 security levels, derby timeout spike
- generators/drm_fairplay/schemas.py: FairPlayLogEntry 33 alan, certificate_status/expiry/ksm_response_code
- generators/drm_fairplay/generator.py: 55K/gün normal, 15 Mart cert expired (ios/apple_tv etkilenir, web_safari etkilenmez, 18 UTC sonrası restore)
- tests/test_drm.py: 18 test passed (Widevine 9 + FairPlay 8 + cross-DRM 1)
- Tests: 62 passed toplam (26 + 18 + 18)

---

### S-MDG-02 — 2026-03-26
- generators/medianova/schemas.py: MedianovaLogEntry 32 alan, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/medianova/generator.py: 50K/gün normal, 500K/gün derby, 5dk dosyalar, CDN outage 503 spike
- generators/origin_logs/schemas.py: OriginLogEntry 4 event_type, FIELD_CATEGORIES, FIELD_DESCRIPTIONS
- generators/origin_logs/generator.py: cdn_miss (Medianova korelasyonlu), health_check 30s, transcoder_event
- tests/test_medianova.py: 10 test passed
- tests/test_origin.py: 8 test passed
- Tests: 44 passed toplam (26 S-MDG-01 + 18 S-MDG-02)

---

### S-MDG-01 — 2026-03-26
- apps/mock_data_gen/ modülü oluşturuldu
- generators/calendar_events.py: 18 CalendarEvent, get_traffic_multiplier(), is_anomaly_active()
- generators/subscriber_pool.py: 485K abone, lazy load, seed(42), TR demographics
- generators/base_generator.py: BaseGenerator ABC, write_jsonl_gz/json/csv, generate_range()
- tests/test_base_infra.py: 26 test, 26 passed
- Tests: 93 + 26 = toplam passed (3 DuckDB IO error — S-MDG-01 ile ilgisiz)

---

## [S24-Fix1] — 2026-03-25
### Fixed
- Log Analyzer: invalid JSX removed (lines 1108-1110 in log-analyzer/page.tsx)
  - {/* comment */} inside && conditional caused runtime crash after analysis load
  - All 13 charts were crashing with "Something went wrong" error boundary
  - Fix: removed 3 lines, build now clean
### Test
- npm build: 0 errors
- Full platform: 659 passed, 0 failures

---

## [S23-Fix2] — 2026-03-25
### Fixed
- Log Analyzer: removed ALL hashing/anonymization from client_ip and user_agent
- Raw Akamai DS2 log values stored and displayed exactly as received
- Removed "Client IPs are anonymized (SHA256)" labels from charts and UI
- Removed ip_hash type inference — now correctly detected as ip_address
- Reverted all field names and test data to use real IP addresses
### Test
- log_analyzer: 99 passed, 0 failures
- Full platform: 659 passed, 0 failures

---

## [S23-Fix] — 2026-03-25
### Fixed
- Knowledge Base: document cards now clickable → Dialog with full content
- Knowledge Base: search results clickable with score bar (green/amber/red)
- Knowledge Base: akamai_ds2 added to search filter dropdown
- Knowledge Base: Index Status tab now shows dynamic counts (not hardcoded)
- Log Analyzer: removed PII hashing — client_ip and user_agent stored as raw values from DS2 logs
  (hashing was never requested, reverted completely)
### Test
- log_analyzer: 99 passed, 0 failures
- knowledge_base: 36 passed, 0 failures
- Full platform: 659 passed, 0 failures

---

## [S23] — 2026-03-25
### Fixed (Log Analyzer — Critical Metric Corrections)
- Bandwidth: now uses bytes field (idx 3) — was using responseBodySize (idx 6)
- Cache Hit Rate: now uses cacheHit binary flag (idx 18) — was using cacheStatus==1
- Error Rate: ERR_CLIENT_ABORT excluded (user behavior, not platform error)
- Transfer Time: now uses transferTimeMSec (idx 15)
- Removed fake "HTTPS %" metric (proto field not in DS2 22-field stream)
- Renamed "Unique Subscribers" → "Unique Client IPs"
- Added abort_rate, access_denied_rate, segment_type_distribution, bandwidth_savings_pct
### Security (PII Fix — Critical)
- client_ip and userAgent: SHA256 hashed at parse time, never stored raw
### Added
- docs/openapi.json — complete OpenAPI spec (101 paths, 116 operations)
- docs/SWAGGER_GUIDE.md — API reference guide
- GET /openapi-spec endpoint
- Knowledge Base: "akamai_ds2" collection (8 docs), "platform" expanded
- GET /knowledge/collections endpoint
### Test
- Full platform: 659 passed, 0 failures

---

## [S22] — 2026-03-25
### Added
- apps/ai_lab/seed.py — 10 experiments + 8 model registry entries (DuckDB)
- GET /ai-lab/dashboard, experiments CRUD, models list/detail
- Frontend: 4 tabs (Dashboard, Experiments, Models, Model Governance)
- apps/knowledge_base/seed.py — 23 documents (incidents/runbooks/platform)
- GET /knowledge/dashboard, search, documents CRUD, delete approval_required
- Frontend: 4 tabs (Dashboard, Search, Documents, Index Status)
- apps/devops_assistant/seed.py — reads from knowledge_base
- POST /devops/chat — dangerous command detection + RAG + Sonnet
- GET /devops/dashboard, runbooks, runbooks/search
- Frontend: 3 tabs (Dashboard, Chat, Runbooks)
### Test
- ai_lab: 42 passed | knowledge_base: 36 passed | devops_assistant: 36 passed
- Full platform: 659 passed, 0 failures
- ALL 11 APPS COMPLETE

---

## [S21] — 2026-03-25
### Added
- apps/admin_governance/seed.py — 3 tenants, module configs, 50 audit entries, 200 token usage rows
- GET /admin/dashboard — tenant stats, audit summary, token usage, compliance score
- GET/POST /admin/tenants — tenant list and create
- GET/PATCH /admin/tenants/{id}/modules — per-tenant module config
- GET /admin/audit — paginated audit log, tenant/action/status filter
- GET /admin/compliance — checks, violations, overall score
- GET /admin/usage — cost by model/app, daily trend, token breakdown
- Frontend: 6 tabs (Dashboard, Tenants, Module Config, Audit Log, Compliance, Usage Stats)
### Test
- admin_governance suite: 54 passed, 0 failures
- Full platform: 623 passed, 0 failures

---

## [S20] — 2026-03-25
### Added
- apps/growth_retention/seed.py — 100 retention scores (DuckDB)
- GET /growth/dashboard — churn stats, segment breakdown, 7d trend, top reasons
- GET /growth/retention — paginated, segment filter, churn risk sorted
- GET /growth/churn-risk — top 20 high-risk users
- GET /growth/segments — 4 segment summaries with recommendations
- POST /growth/query — NL to DuckDB SQL (Sonnet, SELECT-only guard)
- Frontend: 5 tabs (Dashboard, Retention, Churn Risk, Segments, AI Query)
- apps/capacity_cost/seed.py — 150 capacity metrics (DuckDB) + 10 automation jobs (SQLite)
- GET /capacity/dashboard — warning/critical counts, utilization, cost estimate
- GET /capacity/forecast — 7-day service forecast with recommendations
- GET /capacity/usage — paginated metrics, service filter
- GET /capacity/jobs — automation job list
- GET /capacity/cost — cost breakdown, optimization tips
- Frontend: 5 tabs (Dashboard, Forecast, Usage, Automation Jobs, Cost)
### Test
- growth_retention suite: 51 passed, 0 failures
- capacity_cost suite: 47 passed, 0 failures
- Full platform: 605 passed, 0 failures

---

## [S19] — 2026-03-25
### Added
- apps/viewer_experience/seed.py — 20 complaints (SQLite) + 200 QoE sessions (DuckDB)
- GET /viewer/dashboard — avg score, distribution, device breakdown, 24h trend
- GET /viewer/qoe/metrics — paginated, device/content_type filter
- GET /viewer/qoe/anomalies — sessions below 2.5 threshold
- GET /viewer/complaints — paginated, status/priority/category filter
- POST /viewer/complaints — submit new complaint
- GET /viewer/trends — by device, by region, by category
- Frontend: 6 tabs (QoE Dashboard, Live Sessions, Anomaly Feed, Complaints, Trends, Segments)
- apps/live_intelligence/seed.py — 15 live events (DuckDB)
- GET /live/dashboard — live now, upcoming, pre-scale, DRM summary
- GET /live/events — paginated, status filter
- GET /live/events/{id} — detail
- GET /live/drm/status — Widevine, FairPlay, PlayReady health
- GET /live/sportradar — mock SportRadar fixture
- GET /live/epg — 4-channel EPG schedule
- Frontend: 6 tabs (Dashboard, Event Calendar, Live Monitor, Pre-Scale, DRM Status, EPG)
### Test
- viewer_experience suite: 52 passed, 0 failures
- live_intelligence suite: 51 passed, 0 failures
- Full platform: 575 passed, 0 failures

---

## [S18] — 2026-03-25
### Added
- apps/alert_center/seed.py — 5 rules, 3 channels, 2 suppression windows, 100 alert history
- GET /alerts/dashboard — 24h stats, severity/channel breakdown, trend
- GET /alerts/list — paginated, severity/channel/event_type filter
- GET/POST/PATCH/DELETE /alerts/rules — full CRUD
- GET /alerts/channels — masked config
- GET/POST /alerts/suppression — maintenance windows
- GET /alerts/analytics — MTTA, top events, channel performance, 7d volume
- Frontend: 6 tabs (Dashboard, Live Feed, Alert List, Rules, Suppression, Analytics)
- WebSocket Live Feed: real-time stream, reconnect logic, dedup/storm badges
### Test
- alert_center suite: 47 passed, 0 failures
- Full platform suite: 545 passed, 0 failures

---

## [S17-P3] — 2026-03-25
### Added
- apps/ops_center/tests/test_router.py — 19 router tests
  - Dashboard: shape, empty DB zeros, 24-slot trend
  - Incidents: list, severity filter, status filter, pagination, detail found/not found
  - Status patch: valid, invalid 422, not found 404
  - RCA: found (rca_available=True), not found (rca_available=False)
  - Decisions: list items, default limit 100
  - Chat: response key, incident context, tenant header required
### Test
- ops_center suite: 51 passed, 0 failures (19 router + 14 agent + 10 tools + 8 schemas)
- Full platform suite: 527 passed, 0 failures

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
