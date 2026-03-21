# docs/SPRINT_PLAN.md — Sprint Yönetimi
> Claude Code bu dosyayı her sprint'te okur.
> Sprint bitince: biten sprint CHANGELOG.md'ye taşınır, bu dosya güncellenir.
> Versiyon: 2.0 | Mart 2026

---

## AKTİF SPRINT: S09 — Cross-App Integrations + Full Frontend + E2E

**Hedef:** Cross-app entegrasyon testleri, full frontend, E2E senaryolar
**Bitti Kriteri:** `pytest tests/ -v` + E2E senaryolar yeşil
**Test Komutu:**
```bash
source ~/.venvs/aaop/bin/activate
pytest tests/ -v --cov=. --cov-fail-under=80
```

---

## SPRINT SIRASI TABLOSU

| Sprint | Kapsam | Bağımlılıklar | Tahmini Süre |
|---|---|---|---|
| **S01** | Foundation Layer | — | ✅ Tamamlandı (2026-03-19) |
| **S02** | Log Analyzer (Akamai sub-module + agent) | S01 | ✅ Tamamlandı (2026-03-19) |
| **S03** | Ops Center (M01 + M06) | S01, S02 (event bus) | ✅ Tamamlandı (2026-03-19) |
| **S04** | Alert Center (M13) | S01, S03 | ✅ Tamamlandı (2026-03-19) |
| **S05** | Viewer Experience (M02 + M09) | S01 | ✅ Tamamlandı (2026-03-19) |
| **S06** | Live Intelligence (M05 + M11) | S01, S03 | ✅ Tamamlandı (2026-03-19) |
| **S07** | Growth & Retention + Capacity & Cost | S01, S05 | ✅ Tamamlandı (2026-03-21) |
| **S08** | AI Lab + Knowledge Base + DevOps + Admin | S01 | ✅ Tamamlandı (2026-03-21) |
| **S09** | Cross-app integrations + Full Frontend + E2E | S01–S08 | 5-7 gün |

---

## SPRINT KAPANIŞ PROTOKOLÜ (Her Sprint İçin Aynı)

Claude Code şu adımları sırayla uygular:

```
1. pytest tests/ -v --cov=. --cov-fail-under=80   → yeşil olmalı
2. ruff check .                                     → hata yok
3. mypy . --ignore-missing-imports                  → hata yok
4. CHANGELOG.md güncelle (sprint özeti ekle)
5. docs/SPRINT_PLAN.md güncelle (biten sprint ✅, aktif sprint → sonraki)
6. git add -A
7. git commit -m "chore(sprint): close S0X — <özet>"
8. git push
```

---

## TAMAMLANAN SPRINTLER

### S01 — Foundation Layer (2026-03-19)

**Sonuç:** 86 test yeşil | 96% coverage (shared + backend) | ruff + mypy sıfır hata

Tamamlanan adımlar (22/22):
- `pyproject.toml`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`
- `shared/` — settings, schemas (BaseEvent, AgentDecision), 4 client (SQLite, DuckDB, ChromaDB, Redis)
- `shared/event_bus.py` — 9 EventType, asyncio.Queue pub/sub
- `shared/llm_gateway.py` — severity routing (Haiku/Sonnet/Opus), tenacity retry, Redis cache
- `shared/utils/pii_scrubber.py` — regex PII temizleme
- `shared/agents/base_agent.py` — LangGraph 4-adim StateGraph
- `backend/` — FastAPI main + auth (JWT) + dependencies + middleware (rate_limit, tenant_context) + WebSocket manager
- SQLite init (tenants, users, module_configs, audit_log) + DuckDB init (6 shared_analytics tablosu)
- `tests/conftest.py` + 14 unit test dosyasi
- `frontend/` — Next.js 14 + TypeScript + Tailwind + 11 app page stubs + design tokens

### S02 — Log Analyzer (2026-03-19)

**Sonuç:** 36 test yeşil | 80% coverage | ruff sıfır hata | 86 S01 test regresyon yok

Tamamlanan:
- `apps/log_analyzer/config.py` — LogAnalyzerConfig (S3, thresholds, paths)
- `apps/log_analyzer/schemas.py` — LogProject, LogSource, FetchJob, AnalysisResult, SubModuleStatus
- `apps/log_analyzer/sub_modules/base_sub_module.py` — BaseSubModule ABC
- `apps/log_analyzer/sub_modules/__init__.py` — SubModuleRegistry
- `apps/log_analyzer/sub_modules/akamai/` — tam Akamai DataStream 2 implementasyonu:
  - `schemas.py` — AkamaiLogEntry (21 alan), AkamaiConfig, AkamaiMetrics, AkamaiAnomaly
  - `parser.py` — CSV/JSON/NDJSON parser, PII scrub (cliIP + UA SHA256 hash)
  - `analyzer.py` — metrics hesaplama + 3 anomaly detection (error_rate, cache_hit, ttfb)
  - `charts.py` — 21 Plotly dark-theme chart (kaleido==0.2.1)
  - `reporter.py` — python-docx DOCX rapor (cover, summary, metrics table, anomalies, chart gallery)
  - `scheduler.py` — APScheduler AsyncIOScheduler
- `apps/log_analyzer/tools.py` — 12 tool (LOW/MEDIUM/HIGH risk tagged)
- `apps/log_analyzer/prompts.py` — system + analysis prompts
- `apps/log_analyzer/agent.py` — LogAnalyzerAgent(BaseAgent) + Event Bus publish (cdn_anomaly_detected, analysis_complete)
- `backend/routers/log_analyzer.py` — /log-analyzer prefix, health, sub-modules, projects, results
- `apps/log_analyzer/sub_modules/medianova/` — placeholder stub
- Test fixtures: sample_akamai_normal.csv, sample_akamai_spike.csv

### S03 — Ops Center (2026-03-19)

**Sonuç:** 32 test yeşil | 98% coverage | ruff sıfır hata | 122 toplam test regresyon yok

Tamamlanan:
- `apps/ops_center/config.py` — OpsCenterConfig (MTTR target, auto-RCA severities, FP threshold)
- `apps/ops_center/schemas.py` — Incident, IncidentCreate, RCARequest, RCAResult, OpsMetrics (bilingual TR/EN fields)
- `apps/ops_center/prompts.py` — INCIDENT_SYSTEM/ANALYSIS + RCA_SYSTEM/ANALYSIS prompts (TR+EN output)
- `apps/ops_center/tools.py` — 10 tools:
  - LOW: get_incident_history, get_cdn_analysis, get_qoe_metrics, correlate_events
  - MEDIUM: create_incident_record, update_incident_status, trigger_rca, send_slack_notification, publish_*
  - HIGH (approval_required): execute_remediation, escalate_to_oncall
- `apps/ops_center/agent.py` — IncidentAgent (M01) + RCAAgent (M06):
  - P0/P1 → Opus, P2 → Sonnet, P3 → Haiku (severity-based model routing)
  - RCA only triggers for P0/P1 (auto_rca_severities config)
  - EventBus publish: incident_created, rca_completed
  - EventBus subscribe targets: cdn_anomaly_detected, qoe_degradation, live_event_starting
  - Bilingual output: Turkish summary + English technical detail
- `backend/routers/ops_center.py` — /ops prefix (health, dashboard, incidents)
- 4 test files: test_agent (14), test_tools (8), test_schemas (8), test_config (2)

### S04 — Alert Center (2026-03-19)

**Sonuç:** 29 test yeşil | 98% coverage | ruff sıfır hata | 154 toplam test regresyon yok

Tamamlanan:
- `apps/alert_center/config.py` — AlertCenterConfig (dedup 900s, storm 10/5min)
- `apps/alert_center/schemas.py` — Alert, AlertRule, AlertChannel, SuppressionRule, RoutingDecision, compute_fingerprint
- `apps/alert_center/prompts.py` — system + alert message prompts
- `apps/alert_center/tools.py` — 10 tools:
  - LOW: check_dedup, get_routing_rules, check_suppression, detect_alert_storm, set_dedup_cache
  - MEDIUM: route_to_slack, route_to_email, write_alert_to_db
  - HIGH (approval_required): route_to_pagerduty (P0 only), suppress_alert_storm
- `apps/alert_center/agent.py` — AlertRouterAgent:
  - Subscribes to ALL 7 events (cdn_anomaly, incident_created, rca_completed, qoe_degradation, live_event_starting, churn_risk, scale_recommendation)
  - Routing: P0→Slack+PD, P1→Slack, P2→Slack, P3→Email
  - Dedup: 900s Redis TTL fingerprint window
  - Storm: >10 alerts/5min → storm mode → approval_required
- `backend/routers/alert_center.py` — /alerts prefix (health, list, rules, channels)
- 4 test files: test_agent (7), test_tools (12), test_schemas (7), test_config (2)

### S05 — Viewer Experience (2026-03-19)

**Sonuç:** 37 test yeşil | 95% coverage | ruff sıfır hata | 183 toplam test regresyon yok

Tamamlanan:
- `apps/viewer_experience/config.py` — ViewerExperienceConfig (QoE threshold, dedup window)
- `apps/viewer_experience/schemas.py` — QoESession, QoEAnomaly, Complaint, ComplaintAnalysis
- `apps/viewer_experience/tools.py` — 10 tools:
  - LOW: score_qoe_session, get_session_context, detect_qoe_anomaly, search_similar_issues, categorize_complaint, find_related_complaints
  - MEDIUM: write_qoe_metrics, write_complaint, trigger_qoe_alert
  - HIGH (approval_required): escalate_complaint
- `apps/viewer_experience/agent.py` — QoEAgent (M02) + ComplaintAgent (M09):
  - QoE score formula exact match (0.0-5.0 scale, spec Section 4)
  - score < 2.5 → qoe_degradation event published
  - Session dedup: same session_id within 5 min → skip
  - ComplaintAgent: NLP category + sentiment + priority
  - ChromaDB: similar complaints searched
- EventBus subscribes: analysis_complete, live_event_starting
- EventBus publishes: qoe_degradation → ops_center, alert_center
- DuckDB writes: shared_analytics.qoe_metrics, agent_decisions
- DuckDB reads: shared_analytics.cdn_analysis, live_events
- `backend/routers/viewer_experience.py` — /viewer prefix
- 4 test files: test_agent (10), test_tools (21), test_schemas (4), test_config (2)

### S06 — Live Intelligence (2026-03-19)

**Sonuç:** 36 test yeşil | 98% coverage | ruff sıfır hata | 220 toplam test regresyon yok

Tamamlanan:
- `apps/live_intelligence/config.py` — LiveIntelligenceConfig (poll intervals, Redis TTLs)
- `apps/live_intelligence/schemas.py` — LiveEvent, DRMStatus (Widevine+FairPlay+PlayReady), SportRadarData, EPGEntry, ScaleRecommendation
- `apps/live_intelligence/tools.py` — 11 tools:
  - LOW: get_upcoming_events, get_sportradar_data, get_drm_status, get_epg_schedule, calculate_scale_factor
  - MEDIUM: register_live_event, update_event_status, publish_event_start, publish_external_update, cache_*
  - HIGH (approval_required): trigger_pre_scale, override_drm_fallback
- `apps/live_intelligence/agent.py` — LiveEventAgent (M05) + ExternalDataAgent (M11):
  - live_event_starting published exactly 30 min before kickoff
  - ExternalDataAgent uses Haiku for batch processing
  - Poll intervals: SportRadar 30s, DRM 60s, EPG 300s
  - Redis TTLs: active_event=60s, pre_scale_status=3600s, drm_status=60s, sportradar=30s
- EventBus publishes: live_event_starting, external_data_updated
- DuckDB writes: shared_analytics.live_events, agent_decisions
- DuckDB reads: shared_analytics.qoe_metrics, incidents
- `backend/routers/live_intelligence.py` — /live prefix
- 4 test files: test_agent (12), test_tools (16), test_schemas (7), test_config (2)

### S07 — Growth & Retention + Capacity & Cost (2026-03-21)

**Sonuç:** 68 test yeşil | 98%+ coverage | ruff sıfır hata | 324 toplam test regresyon yok

Tamamlanan — Growth & Retention (M18+M03):
- `apps/growth_retention/config.py` — GrowthRetentionConfig (churn threshold 0.7, SQL limits, allowed tables)
- `apps/growth_retention/schemas.py` — RetentionScore, CustomerSegment, ChurnRiskResult, GrowthInsight, NLQueryResult, RetentionCampaign
- `apps/growth_retention/tools.py` — 9 tools:
  - LOW: calculate_churn_risk, get_qoe_correlation, get_cdn_impact, segment_customers, nl_to_sql_query, get_growth_insights
  - MEDIUM: write_analysis_result, trigger_churn_alert
  - HIGH (approval_required): send_retention_campaign
- `apps/growth_retention/agent.py` — GrowthAgent (M18) + DataAnalystAgent (M03):
  - Weighted churn formula: QoE (0.4) + CDN errors (0.3) + retention trend (0.3)
  - churn_risk > 0.7 → churn_risk_detected published to EventBus
  - DataAnalystAgent: NL → SQL, SELECT-only, shared_analytics tables only
  - PII: user_id_hash only, no raw IDs
- EventBus publishes: churn_risk_detected → alert_center
- EventBus subscribes: analysis_complete, external_data_updated
- DuckDB writes: shared_analytics.agent_decisions, retention_scores
- DuckDB reads: shared_analytics.qoe_metrics, cdn_analysis, live_events
- `backend/routers/growth_retention.py` — /growth prefix
- 4 test files: test_agent (7), test_tools (21), test_schemas (6), test_config (2)

Tamamlanan — Capacity & Cost (M16+M04):
- `apps/capacity_cost/config.py` — CapacityCostConfig (warn 70%, crit 90%, forecast 24h)
- `apps/capacity_cost/schemas.py` — CapacityMetrics, CapacityForecast, ThresholdBreach, CostReport, ScaleAction, AutomationJob
- `apps/capacity_cost/tools.py` — 8 tools:
  - LOW: get_current_metrics, forecast_capacity, calculate_cost, detect_threshold_breach
  - MEDIUM: write_forecast, publish_scale_recommendation
  - HIGH (approval_required): create_automation_job, execute_scale_action
- `apps/capacity_cost/agent.py` — CapacityAgent (M16) + AutomationAgent (M04):
  - Threshold breach → scale_recommendation published
  - live_event_starting → pre_scale triggered (>50k viewers)
  - AutomationAgent uses Haiku for routine automation
- EventBus publishes: scale_recommendation → ops_center, alert_center
- EventBus subscribes: live_event_starting
- DuckDB writes: shared_analytics.agent_decisions
- DuckDB reads: shared_analytics.live_events, qoe_metrics
- `backend/routers/capacity_cost.py` — /capacity prefix
- 4 test files: test_agent (9), test_tools (14), test_schemas (7), test_config (2)

### S08 — AI Lab + Knowledge Base + DevOps + Admin (2026-03-21)

**Sonuç:** 114 test yeşil | 99% coverage | ruff sıfır hata | 438 toplam test regresyon yok

Tamamlanan — AI Lab (M10+M14):
- `apps/ai_lab/` — ExperimentationAgent (Sonnet) + ModelGovernanceAgent (Haiku)
- A/B testing: z-test, p-value, CI calculation
- Token budget >80% → warning logged
- switch_model_production, update_model_config → approval_required
- DuckDB reads: shared_analytics.agent_decisions
- `/ai-lab` API endpoints: health, experiments, models, cost
- 4 test files: test_agent (8), test_tools (14), test_schemas (6), test_config (2)

Tamamlanan — Knowledge Base (M15):
- `apps/knowledge_base/` — KnowledgeBaseAgent (Haiku for fast Q&A)
- ChromaDB collections: 'incidents', 'runbooks', 'platform'
- Auto-index: incident_created → index, rca_completed → index
- Chunking: 500 token, 50 overlap, all-MiniLM-L6-v2
- delete_document → approval_required
- `/knowledge` API endpoints: health, search, incidents, runbooks
- 4 test files: test_agent (6), test_tools (11), test_schemas (4), test_config (2)

Tamamlanan — DevOps Assistant (M08):
- `apps/devops_assistant/` — DevOpsAssistantAgent (Sonnet)
- Diagnostics, deployment tracking, dangerous command detection
- Reads ChromaDB 'runbooks' collection (from knowledge_base)
- restart_service, execute_runbook → approval_required
- DuckDB reads: shared_analytics.incidents, agent_decisions
- `/devops` API endpoints: health, diagnostics, deployments, runbooks
- 4 test files: test_agent (7), test_tools (10), test_schemas (5), test_config (2)

Tamamlanan — Admin & Governance (M12+M17):
- `apps/admin_governance/` — TenantAgent (Haiku) + ComplianceAgent (Sonnet)
- Tenant CRUD, module config, API key management, audit trail, compliance
- delete_tenant, rotate_api_key, export_audit_log → approval_required
- API keys: encrypted (SHA256), response masked (sk-ant-...XXXX)
- Every action (success+fail) → audit_log
- Admin endpoints: 'admin' JWT role required
- `/admin` API endpoints: health, tenants, modules, audit, compliance, usage
- 4 test files: test_agent (10), test_tools (14), test_schemas (10), test_config (2)

---

## MOCK DATA SENARYOLARI (Test için)

| Senaryo | Açıklama | Hangi Sprint'te Kullanılır |
|---|---|---|
| `NORMAL_WEEKDAY` | Rutin gün, düşük trafik | S01-S09 (smoke) |
| `MATCH_DAY_DERBY` | Galatasaray-Fenerbahçe, yüksek trafik | S03, S06, S09 |
| `DRM_OUTAGE` | Widevine servisi down | S04, S06 |
| `CDN_SPIKE` | Akamai error rate spike | S02, S03 |
| `CHURN_RISK` | Retention düşüşü senaryosu | S07 |
| `CAPACITY_BREACH` | Kaynak limitine yaklaşma | S07 |

> Mock data: `github.com/fatihayaz78/aaop-mock-data-gen` reposundan çekil
> Lokal konum: `tests/integration/scenarios/`
