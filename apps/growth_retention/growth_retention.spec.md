# growth_retention.spec.md — Growth & Retention
> Kapsam: M18 Customer Growth Intelligence + M03 AI Data Analyst | Sprint: S07-A | Kritiklik: P1

## 1. KULLANICI
Büyüme Analisti, Ürün Yöneticisi — Churn riski, retention, NL veri sorguları

## 2. TABS
| Tab | Açıklama |
|---|---|
| Retention Dashboard | Retention metrikleri, churn trendi |
| Churn Risk | Risk altındaki abone segmentleri |
| Segments | Müşteri segmentasyonu |
| Data Analyst | Doğal dil ile DuckDB sorguları (M03) |
| Insights | AI büyüme önerileri |

## 3. AGENT MİMARİSİ
```python
class GrowthAgent(BaseAgent):
    app_name = "growth_retention"
    # claude-sonnet-4-20250514
    # Günlük periyodik analiz (APScheduler)
    # risk_score > 0.7 → churn_risk_detected yayınla
    # QoE + CDN verilerini cross-app kullanır

class DataAnalystAgent(BaseAgent):
    app_name = "growth_retention"
    # claude-sonnet-4-20250514
    # NL → SQL (DuckDB) dönüştürme
    # Sadece shared_analytics tabloları, read-only
    # PII: user_id_hash kullan (ham ID yasak)
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| calculate_churn_risk | LOW | auto |
| get_qoe_correlation | LOW | auto |
| get_cdn_impact | LOW | auto |
| segment_customers | LOW | auto |
| nl_to_sql_query | LOW | auto |
| get_growth_insights | LOW | auto |
| write_analysis_result | MEDIUM | auto+notify |
| trigger_churn_alert | MEDIUM | auto+notify |
| send_retention_campaign | HIGH | approval_required |

## 5. API
```
prefix: /growth
ref:    API_CONTRACTS.md → Bölüm 8
```

## 6. CROSS-APP
```
OUTPUT: churn_risk_detected → alert_center
INPUT:  analysis_complete   ← log_analyzer
        external_data_updated ← live_intelligence

DuckDB OKUMA: shared_analytics.qoe_metrics, cdn_analysis, live_events
DuckDB YAZMA: shared_analytics.agent_decisions, retention_scores
```

## 7. LOKAL VERİ
### DuckDB (shared_analytics.retention_scores)
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.retention_scores (
    score_id      VARCHAR PRIMARY KEY,
    tenant_id     VARCHAR NOT NULL,
    segment_id    VARCHAR NOT NULL,
    churn_risk    DOUBLE NOT NULL,
    retention_7d  DOUBLE,
    retention_30d DOUBLE,
    factors       JSON,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 8. TEST
```bash
pytest apps/growth_retention/tests/ -v --cov=apps/growth_retention --cov-fail-under=80
```
Senaryolar: CHURN_RISK (risk>0.7 → event) | NL query (→ doğru SQL → doğru sonuç) | CDN korelasyon
