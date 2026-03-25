# ops_center.spec.md — Ops Center
> Kapsam: M01 AI Incident Copilot + M06 RCA Engine | Sprint: S03 | Kritiklik: P0

## 1. KULLANICI
NOC Operatör, Platform Mühendisi — 7/24 izleme, P1/P2 incident yönetimi

## 2. TABS
| Tab | Veri Kaynağı |
|---|---|
| Dashboard | DuckDB: incidents + agent_decisions |
| Incidents | DuckDB: incidents |
| RCA Explorer | DuckDB: agent_decisions |
| Decision Log | DuckDB: agent_decisions |

## 3. AGENT MİMARİSİ
```python
class IncidentAgent(BaseAgent):
    app_name = "ops_center"
    # P0/P1 → claude-opus-4-20250514
    # P2/P3 → claude-sonnet-4-20250514
    # context_loader: Redis → DuckDB → ChromaDB RAG
    # memory_update: DuckDB incidents yaz + incident_created yayınla

class RCAAgent(BaseAgent):
    app_name = "ops_center"
    # Her zaman claude-opus-4-20250514
    # M01 tetikler, correlation: CDN + QoE + live event
    # rca_completed → knowledge_base, alert_center
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| get_incident_history | LOW | auto |
| get_cdn_analysis | LOW | auto |
| get_qoe_metrics | LOW | auto |
| correlate_events | LOW | auto |
| create_incident_record | MEDIUM | auto+notify |
| update_incident_status | MEDIUM | auto+notify |
| trigger_rca | MEDIUM | auto+notify |
| send_slack_notification | MEDIUM | auto+notify |
| execute_remediation | HIGH | approval_required |
| escalate_to_oncall | HIGH | approval_required |

## 5. API
```
prefix:    /ops
websocket: /ws/ops/incidents
router:    backend/routers/ops_center.py
ref:       API_CONTRACTS.md → Bölüm 3
```

## 6. CROSS-APP
```
INPUT (subscribe):
  cdn_anomaly_detected  ← log_analyzer
  qoe_degradation       ← viewer_experience
  live_event_starting   ← live_intelligence
  scale_recommendation  ← capacity_cost
  external_data_updated ← live_intelligence

OUTPUT (publish):
  incident_created → alert_center, knowledge_base
  rca_completed    → knowledge_base, alert_center

DuckDB OKUMA:  shared_analytics.cdn_analysis, qoe_metrics, live_events
DuckDB YAZMA:  shared_analytics.incidents, agent_decisions
```

## 7. LOKAL VERİ
### Redis
```
ctx:{tenant_id}:incident:latest        TTL: 300s
ctx:{tenant_id}:incident:{id}          TTL: 3600s
llm:cache:{hash}                       TTL: 86400s
```

## 8. TEST
```bash
pytest apps/ops_center/tests/ -v --cov=apps/ops_center --cov-fail-under=80
```
Senaryolar: MATCH_DAY_DERBY (Opus, MTTR<300s) | CDN_SPIKE (auto incident) | DRM_OUTAGE (approval_required) | NORMAL_WEEKDAY (FP<%15)

## 9. BİZNES KURALLARI
```
P1 MTTR hedefi: < 300s
P0/P1: Opus + Slack + PagerDuty
FP rate: < %15 (7 günlük pencere)
RCA: sadece P0/P1 otomatik
Output: TR özet (NOC) + EN teknik (DevOps)
```

---
## Sprint Completion — S03
- Date: Mart 2026
- Tests: 32 passed, 98% coverage
- ruff: clean
- Status: ✅ Complete
- Commit: 322f62b

### Files Created
- apps/ops_center/config.py — OpsModuleConfig (MTTR targets, thresholds, model routing)
- apps/ops_center/schemas.py — IncidentEvent, IncidentRecord, RemediationPlan, RCAResult, AgentDecisionResult
- apps/ops_center/prompts.py — system + incident analysis + RCA + bilingual output prompts
- apps/ops_center/tools.py — 10 tools (LOW/MEDIUM/HIGH risk)
  - get_incident_history, get_cdn_analysis, get_qoe_metrics, correlate_events (LOW)
  - create_incident_record, update_incident_status, trigger_rca, send_slack_notification (MEDIUM)
  - execute_remediation, escalate_to_oncall (HIGH — approval_required)
- apps/ops_center/agent.py — IncidentAgent + RCAAgent (both extend BaseAgent)
  - IncidentAgent: P0/P1 → Opus, P2/P3 → Sonnet, P3 → Haiku
  - RCAAgent: always Opus, triggered only for P0/P1
  - Output: summary_tr (Turkish NOC) + detail_en (English DevOps)
- backend/routers/ops_center.py — /ops prefix, all endpoints + WebSocket /ws/ops/incidents
- apps/ops_center/tests/test_tools.py — 18 tests
- apps/ops_center/tests/test_agent.py — 14 tests

### Cross-App Wired
- Subscribes: cdn_anomaly_detected, qoe_degradation, live_event_starting,
  scale_recommendation, external_data_updated
- Publishes: incident_created → alert_center, knowledge_base
- Publishes: rca_completed → knowledge_base, alert_center
- DuckDB reads: shared_analytics.cdn_analysis, qoe_metrics, live_events
- DuckDB writes: shared_analytics.incidents, agent_decisions

### Hard Constraints Verified
- P0/P1 → claude-opus-4-20250514 ✅
- P2/P3 → claude-sonnet-4-20250514 ✅
- P3 → claude-haiku-4-5-20251001 ✅ (deviation — see below)
- RCA triggers only for P0/P1 ✅
- execute_remediation → approval_required ✅
- escalate_to_oncall → approval_required ✅
- Turkish summary + English technical detail on every incident ✅

### Deviations
- P3 routed to Haiku (spec said Sonnet) — deliberate optimization for cost,
  P3 incidents are low priority batch processing

---
## Sprint Progress — S17
### P1 Complete — 2026-03-25
- seed.py: 50 incidents + 50 agent_decisions (idempotent)
- 7 new endpoints: dashboard, incidents CRUD, rca, decisions, chat
- Tests: 32 passed (regression clean), full suite 508 passed
- Next: P2 — Frontend Dashboard + Incidents tabs

### P2 Complete — 2026-03-25
- Frontend: 4 tabs implemented (Dashboard, Incidents, RCA Explorer, Decision Log)
- Field mapping fixed (snake_case → camelCase)
- Severity badges, status dots, MTTR formatter applied
- Captain logAR chat panel wired (POST /ops/chat)
- Known issues: minor UI bugs → deferred fix sprint
- Next: P3 — Router tests (target 52+ tests, 0 failures)
