# alert_center.spec.md — Alert Center
> Kapsam: M13 Alert Router | Sprint: S04 | Kritiklik: P0

## 1. KULLANICI
NOC Operatör, On-call Mühendisi — Merkezi alert yönetimi, dedup, routing, escalation

## 2. TABS
| Tab | Açıklama |
|---|---|
| Live Feed | Gerçek zamanlı alert akışı (WebSocket) |
| Alert List | Tüm alert'ler, ack/resolve |
| Rules | Routing kuralları CRUD |
| Channels | Slack/PagerDuty/Email kanal yönetimi |
| Suppression | Maintenance window + suppress |
| Analytics | Alert volume, MTTA, kanal performansı |

## 3. AGENT MİMARİSİ
```python
class AlertRouterAgent(BaseAgent):
    app_name = "alert_center"
    # Routing kararı  → claude-haiku-4-5-20251001 (hızlı, ucuz)
    # Mesaj üretimi   → claude-sonnet-4-20250514
    # context_loader: Redis dedup → SQLite kurallar → DuckDB son 1 saat
    # Dedup window: 900s (Redis fingerprint)
    # Storm threshold: > 10 alert / 5 dakika → storm mode
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| check_dedup | LOW | auto |
| get_routing_rules | LOW | auto |
| check_suppression | LOW | auto |
| detect_alert_storm | LOW | auto |
| set_dedup_cache | LOW | auto |
| route_to_slack | MEDIUM | auto+notify |
| route_to_email | MEDIUM | auto+notify |
| write_alert_to_db | MEDIUM | auto+notify |
| route_to_pagerduty | HIGH | approval_required (P0 only) |
| suppress_alert_storm | HIGH | approval_required |

## 5. ROUTING MANTIĞI
```
Alert gelir → Dedup? DROP → Suppressed? DROP → Storm? Özet alert
  P0 → Slack + PagerDuty (PD: approval_required)
  P1 → Slack (ONAY GEREKLİ badge)
  P2 → Slack
  P3 → Email
→ DuckDB: alerts_sent YAZ + Redis: dedup SET
```

## 6. API
```
prefix:    /alerts
websocket: /ws/alerts/stream
ref:       API_CONTRACTS.md → Bölüm 5
```

## 7. CROSS-APP
```
INPUT (TÜM EVENT'LERİ DİNLER):
  cdn_anomaly_detected, incident_created, rca_completed,
  qoe_degradation, live_event_starting, churn_risk_detected,
  scale_recommendation

DuckDB YAZMA: shared_analytics.alerts_sent
DuckDB OKUMA: shared_analytics.incidents, agent_decisions
```

## 8. LOKAL VERİ
### SQLite
```sql
CREATE TABLE alert_rules (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    name TEXT NOT NULL, event_types TEXT NOT NULL,
    severity_min TEXT NOT NULL, channels TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE alert_channels (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    channel_type TEXT NOT NULL, name TEXT NOT NULL,
    config_json TEXT NOT NULL, is_active INTEGER DEFAULT 1
);
CREATE TABLE suppression_rules (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    name TEXT NOT NULL, start_time TEXT NOT NULL,
    end_time TEXT NOT NULL, is_active INTEGER DEFAULT 1
);
```
### Redis
```
alert:dedup:{tenant_id}:{fingerprint}   TTL: 900s
alert:storm:{tenant_id}                 TTL: 300s
```

## 9. TEST
```bash
pytest apps/alert_center/tests/ -v --cov=apps/alert_center --cov-fail-under=80
```
Senaryolar: Dedup (2x event → 1x Slack) | Storm (15/5dk → 1 özet) | Suppress (maintenance → DROP) | P0 routing (approval_required)

---
## Sprint Completion — S04
- Date: Mart 2026
- Tests: 29 passed, 98% coverage
- ruff: clean
- Status: ✅ Complete
- Commit: bb29987

### Files Created
- apps/alert_center/config.py — AlertCenterConfig (dedup TTL, storm threshold, channels)
- apps/alert_center/schemas.py — Alert, AlertRule, AlertChannel, SuppressionRule, RoutingResult
- apps/alert_center/prompts.py — system + routing decision + message generation prompts
- apps/alert_center/tools.py — 10 tools (LOW/MEDIUM/HIGH risk)
  - check_dedup, get_routing_rules, check_suppression, detect_alert_storm, set_dedup_cache (LOW)
  - route_to_slack, route_to_email, write_alert_to_db (MEDIUM)
  - route_to_pagerduty, suppress_alert_storm (HIGH — approval_required)
- apps/alert_center/agent.py — AlertRouterAgent(BaseAgent)
  - Haiku for routing decisions, Sonnet for message generation
  - Dedup → Suppression → Storm detection → Routing pipeline
- backend/routers/alert_center.py — /alerts prefix, all endpoints
- apps/alert_center/tests/test_tools.py — 18 tests
- apps/alert_center/tests/test_agent.py — 11 tests

### Cross-App Wired
- Subscribes: cdn_anomaly_detected, incident_created, rca_completed,
  qoe_degradation, live_event_starting, churn_risk_detected, scale_recommendation
- DuckDB writes: shared_analytics.alerts_sent

### Hard Constraints Verified
- Dedup: 900s Redis TTL ✅
- Storm: >10 alerts/5min → single summary ✅
- P0 → Slack + PagerDuty (approval_required) ✅
- P1/P2 → Slack ✅
- P3 → Email ✅
- All 7 event subscriptions wired ✅

### Deviations
- None

---
## Sprint Completion — S18
- Date: Mart 2026
- Tests: 47 passed, 0 failures (11 agent + 4 schemas + 6 tools + 8 config + 18 router)
- ruff: clean
- Status: ✅ Complete
- Commit: 80c933f

### Files Created
- apps/alert_center/seed.py — 5 rules, 3 channels, 2 suppression windows, 100 DuckDB alerts
- backend/routers/alert_center.py — 10 endpoints (dashboard, list, rules CRUD, channels, suppression, analytics)
- apps/alert_center/tests/test_router.py — 18 router tests
- frontend/src/app/(apps)/alert-center/page.tsx — 6 tabs, WebSocket Live Feed

---
## Sprint Progress — S-DI-03 (2026-03-28)
### logs.duckdb Entegrasyonu
- GET /alerts/dashboard: CDN health badge (medianova_logs), DRM status badge (widevine_drm_logs + fairplay_drm_logs), API health badge (api_logs_logs)
- POST /alerts/evaluate: Anomali tespiti logs.duckdb'den gerçek veri ile
- DuckDB OKUMA: logs.duckdb aaop_company schema (medianova_logs, widevine_drm_logs, fairplay_drm_logs, api_logs_logs)

---
## Sprint Completion — S-AGENT-03

- Date: 2026-03-29
- Tests: 9 passed (agent), 148 passed (platform), 0 failure
- AlertRouterAgent: BaseAgent 4-adım döngüsü aktif
- Routing pipeline: dedup → suppression → storm → route
- route_to_pagerduty + suppress_alert_storm → approval_required
- Deviations: None

---
## Sprint Progress — S-AGENT-06 (2026-03-30) | commit: c5450d19

### Tool Fix: check_suppression
- Önceki: hardcoded `return False`
- Düzeltme: SQLite suppression_rules tablosu lookup (tenant_id + is_active + date range)
- Tests: 148 passed, 0 failure
