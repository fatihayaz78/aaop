# capacity_cost.spec.md — Capacity & Cost
> Kapsam: M16 Capacity Planning + M04 Universal Automation | Sprint: S07-B | Kritiklik: P1

## 1. KULLANICI
DevOps Mühendisi, Platform Mühendisi — Kapasite tahmin, ölçekleme, maliyet optimizasyonu

## 2. TABS
Capacity Forecast | Current Usage | Automation Jobs | Cost Analysis | Thresholds

## 3. AGENT MİMARİSİ
```python
class CapacityAgent(BaseAgent):
    app_name = "capacity_cost"
    # claude-sonnet-4-20250514
    # Günlük tahmin + saatlik kullanım kontrolü
    # live_event_starting alındığında pre-scale hesapla
    # scale_recommendation YAYINLA (eşik yaklaşıldığında)

class AutomationAgent(BaseAgent):
    app_name = "capacity_cost"
    # claude-haiku-4-5-20251001 (rutin otomasyon)
    # Multi-step workflow (CrewAI pattern)
    # Yüksek riskli eylemler: approval_required=True
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| get_current_metrics | LOW | auto |
| forecast_capacity | LOW | auto |
| calculate_cost | LOW | auto |
| detect_threshold_breach | LOW | auto |
| write_forecast | MEDIUM | auto+notify |
| publish_scale_recommendation | MEDIUM | auto+notify |
| create_automation_job | HIGH | approval_required |
| execute_scale_action | HIGH | approval_required |

## 5. API
```
prefix: /capacity
ref:    API_CONTRACTS.md → Bölüm 9
```

## 6. CROSS-APP
```
OUTPUT: scale_recommendation → ops_center, alert_center
INPUT:  live_event_starting  ← live_intelligence (pre-scale hesapla)

DuckDB OKUMA: shared_analytics.live_events, qoe_metrics
DuckDB YAZMA: shared_analytics.agent_decisions
```

## 7. LOKAL VERİ
### SQLite
```sql
CREATE TABLE automation_jobs (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    job_type TEXT NOT NULL, status TEXT DEFAULT 'pending',
    config_json TEXT, result_json TEXT,
    started_at TEXT, completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE capacity_thresholds (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    warn_pct REAL DEFAULT 70, crit_pct REAL DEFAULT 90,
    updated_at TEXT DEFAULT (datetime('now'))
);
```

## 8. TEST
```bash
pytest apps/capacity_cost/tests/ -v --cov=apps/capacity_cost --cov-fail-under=80
```
Senaryolar: CAPACITY_BREACH (eşik aşımı → event) | Pre-scale (live_event → hesapla → HIGH tool) | Cost calc

## Sprint Completion — S07 (2026-03-21)

### Files Created
- `apps/capacity_cost/__init__.py`
- `apps/capacity_cost/config.py` — CapacityCostConfig
- `apps/capacity_cost/schemas.py` — CapacityMetrics, CapacityForecast, ThresholdBreach, CostReport, ScaleAction, AutomationJob
- `apps/capacity_cost/prompts.py` — CAPACITY_SYSTEM, AUTOMATION_SYSTEM, CAPACITY_ANALYSIS, PRE_SCALE prompts
- `apps/capacity_cost/tools.py` — 8 tools (4 LOW, 2 MEDIUM, 2 HIGH)
- `apps/capacity_cost/agent.py` — CapacityAgent (M16) + AutomationAgent (M04)
- `apps/capacity_cost/tests/conftest.py` — mock_llm, mock_db, mock_redis, event_bus
- `apps/capacity_cost/tests/test_agent.py` — 9 tests
- `apps/capacity_cost/tests/test_tools.py` — 14 tests
- `apps/capacity_cost/tests/test_schemas.py` — 7 tests
- `apps/capacity_cost/tests/test_config.py` — 2 tests
- `backend/routers/capacity_cost.py` — /capacity prefix (health, forecast, usage, jobs, cost)

### Cross-App Wiring
- EventBus publishes: `scale_recommendation` → ops_center, alert_center (verified in test_agent)
- EventBus subscribes: `live_event_starting` (from live_intelligence, pre-scale trigger)
- DuckDB writes: `shared_analytics.agent_decisions`
- DuckDB reads: `shared_analytics.live_events`, `qoe_metrics`

### Hard Constraints Verified
- ✅ CapacityAgent AND AutomationAgent both implemented
- ✅ create_automation_job → approval_required=True
- ✅ execute_scale_action → approval_required=True
- ✅ publish_scale_recommendation → EventBus: scale_recommendation
- ✅ EventBus subscribes: live_event_starting (pre-scale trigger for >50k viewers)
- ✅ DuckDB writes: shared_analytics.agent_decisions
- ✅ DuckDB reads: shared_analytics.live_events, qoe_metrics

### Deviations
- None. All spec constraints met.
