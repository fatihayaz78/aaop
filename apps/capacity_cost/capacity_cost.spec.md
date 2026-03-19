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
