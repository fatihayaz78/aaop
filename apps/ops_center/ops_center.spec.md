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
