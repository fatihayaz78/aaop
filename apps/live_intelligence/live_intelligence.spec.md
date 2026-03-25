# live_intelligence.spec.md — Live Intelligence
> Kapsam: M05 Live Event Monitor + M11 External Data Connectors | Sprint: S06 | Kritiklik: P1

## 1. KULLANICI
Yayın Operatörü, Live Planner — Canlı maç izleme, pre-scale, dış veri entegrasyonu

## 2. TABS
Event Calendar | Live Monitor | Pre-Scale | SportRadar | DRM Status | EPG

## 3. AGENT MİMARİSİ
```python
class LiveEventAgent(BaseAgent):
    app_name = "live_intelligence"
    # claude-sonnet-4-20250514
    # Kickoff - 30 dakika → otomatik tetik
    # live_event_starting YAYINLA
    # Redis cache TTL: 60s (sık yenilenir)

class ExternalDataAgent(BaseAgent):
    app_name = "live_intelligence"
    # claude-haiku-4-5-20251001 (toplu veri işleme)
    # SportRadar: 30s | DRM: 60s | EPG: 300s poll
    # external_data_updated YAYINLA (önemli değişimde)
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| get_upcoming_events | LOW | auto |
| get_sportradar_data | LOW | auto |
| get_drm_status | LOW | auto |
| get_epg_schedule | LOW | auto |
| calculate_scale_factor | LOW | auto |
| register_live_event | MEDIUM | auto+notify |
| update_event_status | MEDIUM | auto+notify |
| publish_event_start | MEDIUM | auto+notify |
| publish_external_update | MEDIUM | auto+notify |
| trigger_pre_scale | HIGH | approval_required |
| override_drm_fallback | HIGH | approval_required |

## 5. API
```
prefix:    /live
websocket: /ws/live/events
ref:       API_CONTRACTS.md → Bölüm 7
```

## 6. CROSS-APP
```
OUTPUT:
  live_event_starting  → ops_center, log_analyzer, alert_center
  external_data_updated → ops_center, growth_retention

DuckDB YAZMA: shared_analytics.live_events, agent_decisions
DuckDB OKUMA: shared_analytics.qoe_metrics, incidents
```

## 7. LOKAL VERİ
### SQLite
```sql
CREATE TABLE external_connectors (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    connector TEXT NOT NULL,    -- 'sportradar', 'drm', 'epg', 'npaw'
    config_json TEXT,
    poll_seconds INTEGER DEFAULT 60,
    is_active INTEGER DEFAULT 1,
    last_synced TEXT, status TEXT DEFAULT 'idle'
);
```
### Redis
```
ctx:{tenant_id}:live:active_event     TTL: 60s
ctx:{tenant_id}:live:pre_scale_status TTL: 3600s
ctx:{tenant_id}:drm:status            TTL: 60s
ctx:{tenant_id}:sportradar:{match_id} TTL: 30s
```

## 8. TEST
```bash
pytest apps/live_intelligence/tests/ -v --cov=apps/live_intelligence --cov-fail-under=80
```
Senaryolar: MATCH_DAY (30dk önce start event) | DRM_OUTAGE (approval_required) | EPG sync (external_data_updated)

---
## Sprint Completion — S06
- Date: Mart 2026
- Tests: 36 passed, 98% coverage
- ruff: clean
- Status: ✅ Complete

### Files Created
- apps/live_intelligence/config.py — LiveIntelligenceConfig (poll intervals, Redis TTLs)
- apps/live_intelligence/schemas.py — LiveEvent, DRMStatus, SportRadarData, EPGEntry, ExternalConnector, ScaleRecommendation
- apps/live_intelligence/prompts.py — system + live event analysis + external data prompts
- apps/live_intelligence/tools.py — 11 tools (LOW/MEDIUM/HIGH risk)
  - get_upcoming_events, get_sportradar_data, get_drm_status, get_epg_schedule, calculate_scale_factor (LOW)
  - register_live_event, update_event_status, publish_event_start, publish_external_update, cache_* (MEDIUM)
  - trigger_pre_scale, override_drm_fallback (HIGH — approval_required)
- apps/live_intelligence/agent.py — LiveEventAgent + ExternalDataAgent (both extend BaseAgent)
  - LiveEventAgent: Sonnet, publishes live_event_starting 30 min before kickoff
  - ExternalDataAgent: Haiku for batch, publishes external_data_updated on significant changes
- backend/routers/live_intelligence.py — /live prefix, all endpoints
- 4 test files: test_agent (12), test_tools (16), test_schemas (7), test_config (2)

### Cross-App Wired
- Publishes: live_event_starting → ops_center, log_analyzer, alert_center
            external_data_updated → ops_center, growth_retention
- Subscribes: (none — live_intelligence is a source app)
- DuckDB writes: shared_analytics.live_events, agent_decisions
- DuckDB reads: shared_analytics.qoe_metrics, incidents

### Hard Constraints Verified
- LiveEventAgent AND ExternalDataAgent implemented ✅
- live_event_starting published exactly 30 min before kickoff ✅
- SportRadar poll: 30s, DRM poll: 60s, EPG poll: 300s ✅
- trigger_pre_scale → approval_required ✅
- override_drm_fallback → approval_required ✅
- DRM: Widevine + FairPlay + PlayReady tracked ✅
- Redis TTLs: active_event=60s, pre_scale_status=3600s, drm_status=60s, sportradar=30s ✅
- EventBus subscribes: none (source app) ✅

### Deviations
- None

---
## Sprint Completion — S19
- Date: Mart 2026
- seed.py: 15 live events
- 6 endpoints (dashboard, events, DRM, SportRadar, EPG)
- Frontend: 6 tabs
- Tests: 51 passed, 0 failures
- Status: ✅ Complete
