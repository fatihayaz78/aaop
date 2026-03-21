# docs/DATA_FLOW.md — Cross-App Veri Mimarisi
> Claude Code bu dosyayı sadece cross-app entegrasyon sprint'lerinde (S09) okur.
> Günlük app geliştirmesinde gerek yok.
> Versiyon: 2.0 | Mart 2026

---

## 1. GENEL MİMARİ

```
┌─────────────────────────────────────────────────────────────────┐
│                        EVENT BUS                                 │
│              shared/event_bus.py (asyncio.Queue)                 │
│                                                                   │
│  log_analyzer ──cdn_anomaly──▶ ops_center                        │
│  log_analyzer ──analysis_complete──▶ growth_retention            │
│  ops_center ──incident_created──▶ alert_center, knowledge_base  │
│  ops_center ──rca_completed──▶ knowledge_base, alert_center      │
│  viewer_experience ──qoe_degradation──▶ ops_center, alert_center │
│  live_intelligence ──live_event_starting──▶ ops_center, log_*    │
│  live_intelligence ──external_data_updated──▶ ops_center, growth │
│  growth_retention ──churn_risk_detected──▶ alert_center          │
│  capacity_cost ──scale_recommendation──▶ ops_center, alert_center│
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DUCKDB SHARED                              │
│              data/duckdb/analytics.duckdb                        │
│                                                                   │
│  shared_analytics.cdn_analysis   ← log_analyzer yazar           │
│  shared_analytics.incidents      ← ops_center yazar             │
│  shared_analytics.qoe_metrics    ← viewer_experience yazar       │
│  shared_analytics.live_events    ← live_intelligence yazar       │
│  shared_analytics.agent_decisions← tüm app'ler yazar            │
│  shared_analytics.alerts_sent    ← alert_center yazar           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. DUCKDB SHARED ANALYTICS — TABLO ŞEMAları

### `shared_analytics.cdn_analysis`
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.cdn_analysis (
    analysis_id     VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    project_id      VARCHAR,
    sub_module      VARCHAR NOT NULL,          -- 'akamai', 'medianova'
    analysis_time   TIMESTAMPTZ NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    total_requests  BIGINT,
    error_rate      DOUBLE,
    cache_hit_rate  DOUBLE,
    avg_ttfb_ms     DOUBLE,
    p99_ttfb_ms     DOUBLE,
    top_errors      JSON,                      -- [{code, count, pct}]
    edge_breakdown  JSON,                      -- [{edge, requests, errors}]
    anomalies       JSON,                      -- [{type, severity, description}]
    agent_summary   TEXT,                      -- LLM'in ürettiği özet
    report_path     VARCHAR,                   -- DOCX dosya yolu
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### `shared_analytics.incidents`
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.incidents (
    incident_id     VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    severity        VARCHAR NOT NULL,          -- P0/P1/P2/P3
    title           VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,          -- open/investigating/resolved
    source_app      VARCHAR,                   -- hangi app tetikledi
    correlation_ids JSON,                      -- bağlantılı event ID'leri
    affected_svcs   JSON,
    metrics_at_time JSON,
    rca_id          VARCHAR,                   -- rca_results tablosuna FK
    mttr_seconds    INTEGER,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### `shared_analytics.qoe_metrics`
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.qoe_metrics (
    metric_id       VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    session_id      VARCHAR NOT NULL,
    user_id_hash    VARCHAR,                   -- PII scrubbed
    content_id      VARCHAR,
    device_type     VARCHAR,
    region          VARCHAR,
    buffering_ratio DOUBLE,
    startup_time_ms INTEGER,
    bitrate_avg     INTEGER,
    quality_score   DOUBLE,                    -- 0.0-5.0
    errors          JSON,
    event_ts        TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### `shared_analytics.live_events`
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.live_events (
    event_id        VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    event_name      VARCHAR NOT NULL,
    sport           VARCHAR,
    competition     VARCHAR,
    kickoff_time    TIMESTAMPTZ,
    status          VARCHAR,                   -- scheduled/live/completed
    expected_viewers INTEGER,
    peak_viewers    INTEGER,
    pre_scale_done  BOOLEAN DEFAULT FALSE,
    sportradar_id   VARCHAR,
    epg_id          VARCHAR,
    metrics         JSON,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### `shared_analytics.agent_decisions`
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.agent_decisions (
    decision_id         VARCHAR PRIMARY KEY,
    tenant_id           VARCHAR NOT NULL,
    app                 VARCHAR NOT NULL,      -- 'ops_center', 'log_analyzer', vb.
    action              VARCHAR NOT NULL,
    risk_level          VARCHAR NOT NULL,      -- LOW/MEDIUM/HIGH
    approval_required   BOOLEAN DEFAULT FALSE,
    llm_model_used      VARCHAR NOT NULL,
    reasoning_summary   TEXT,
    tools_executed      JSON,
    confidence_score    DOUBLE,
    duration_ms         INTEGER,
    input_event_id      VARCHAR,
    output_event_type   VARCHAR,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### `shared_analytics.alerts_sent`
```sql
CREATE TABLE IF NOT EXISTS shared_analytics.alerts_sent (
    alert_id        VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    source_app      VARCHAR NOT NULL,
    severity        VARCHAR NOT NULL,
    channel         VARCHAR NOT NULL,          -- slack/pagerduty/email
    title           VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,          -- sent/acknowledged/resolved
    decision_id     VARCHAR,                   -- agent_decisions FK
    sent_at         TIMESTAMPTZ NOT NULL,
    acked_at        TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3. SQLITE PLATFORM METADATA — TABLO ŞEMAları

```sql
-- tenants
CREATE TABLE tenants (
    id          TEXT PRIMARY KEY,              -- 'bein_sports', 'dazn', 'tivibu'
    name        TEXT NOT NULL,
    plan        TEXT NOT NULL,                 -- 'starter', 'growth', 'enterprise'
    timezone    TEXT DEFAULT 'Europe/Istanbul',
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- users
CREATE TABLE users (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id),
    username    TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role        TEXT NOT NULL,                 -- 'admin', 'analyst', 'viewer'
    is_active   INTEGER DEFAULT 1,
    last_login  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- module_configs
CREATE TABLE module_configs (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id),
    module_name TEXT NOT NULL,                 -- 'ops_center', 'log_analyzer', vb.
    is_enabled  INTEGER DEFAULT 1,
    config_json TEXT,                          -- JSON blob (modül özel ayarlar)
    updated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(tenant_id, module_name)
);

-- audit_log
CREATE TABLE audit_log (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    user_id     TEXT,
    action      TEXT NOT NULL,
    resource    TEXT,
    detail_json TEXT,
    ip_hash     TEXT,                          -- PII scrubbed
    created_at  TEXT DEFAULT (datetime('now'))
);
```

---

## 4. EVENT BUS — 9 EVENT DETAYI

```python
# shared/event_bus.py — Event type definitions

class EventType(str, Enum):
    CDN_ANOMALY_DETECTED       = "cdn_anomaly_detected"
    INCIDENT_CREATED           = "incident_created"
    RCA_COMPLETED              = "rca_completed"
    QOE_DEGRADATION            = "qoe_degradation"
    LIVE_EVENT_STARTING        = "live_event_starting"
    EXTERNAL_DATA_UPDATED      = "external_data_updated"
    CHURN_RISK_DETECTED        = "churn_risk_detected"
    SCALE_RECOMMENDATION       = "scale_recommendation"
    ANALYSIS_COMPLETE          = "analysis_complete"

# Her event'in publisher ve subscriber'ları:
EVENT_ROUTING = {
    EventType.CDN_ANOMALY_DETECTED:    {"pub": "log_analyzer",       "subs": ["ops_center", "alert_center"]},       # ✅ S02+S03+S04
    EventType.INCIDENT_CREATED:        {"pub": "ops_center",          "subs": ["alert_center", "knowledge_base"]},  # ✅ S03+S04
    EventType.RCA_COMPLETED:           {"pub": "ops_center",          "subs": ["knowledge_base", "alert_center"]},  # ✅ S03+S04
    EventType.QOE_DEGRADATION:         {"pub": "viewer_experience",   "subs": ["ops_center", "alert_center"]},      # ✅ S05+S03+S04
    EventType.LIVE_EVENT_STARTING:     {"pub": "live_intelligence",   "subs": ["ops_center", "log_analyzer", "alert_center"]},  # ✅ S06+S03+S02+S04
    EventType.EXTERNAL_DATA_UPDATED:   {"pub": "live_intelligence",   "subs": ["ops_center", "growth_retention"]},             # ✅ S06+S03
    EventType.CHURN_RISK_DETECTED:     {"pub": "growth_retention",    "subs": ["alert_center"]},                           # ✅ S07
    EventType.SCALE_RECOMMENDATION:    {"pub": "capacity_cost",       "subs": ["ops_center", "alert_center"]},              # ✅ S07
    EventType.ANALYSIS_COMPLETE:       {"pub": "log_analyzer",        "subs": ["growth_retention", "viewer_experience"]},
}
```

---

## 5. REDIS CONTEXT CACHE — KEY'LER VE TTL'LER

```
# Incident context
ctx:{tenant_id}:incident:{incident_id}       TTL: 3600s  (1 saat)
ctx:{tenant_id}:incident:latest              TTL: 300s   (5 dakika)

# CDN analysis
ctx:{tenant_id}:cdn:latest_analysis          TTL: 300s   (5 dakika)
ctx:{tenant_id}:cdn:active_anomalies         TTL: 120s   (2 dakika)

# Live event
ctx:{tenant_id}:live:active_event            TTL: 60s    (1 dakika — sık yenilenir)
ctx:{tenant_id}:live:pre_scale_status        TTL: 3600s

# QoE
ctx:{tenant_id}:qoe:session:{session_id}     TTL: 1800s  (30 dakika)
ctx:{tenant_id}:qoe:active_anomalies         TTL: 120s

# LLM Gateway cache
llm:cache:{sha256(prompt+model)}             TTL: 86400s (24 saat)
llm:rate:{tenant_id}:{model}                 TTL: 60s    (rate limit)

# Alert dedup
alert:dedup:{tenant_id}:{alert_fingerprint}  TTL: 900s   (15 dakika — dedup window)
```

---

## 6. UÇTAN UCA ÖRNEK AKIŞ

### Senaryo: Akamai Log Anomaly → Incident → Alert

```
1. [APScheduler] log_analyzer Akamai job tetiklenir (her 6 saatte)
   ↓
2. [log_analyzer] S3'ten log dosyası çekilir (boto3)
   ↓
3. [log_analyzer agent] Analiz yapılır, error_rate > 5% tespit edilir
   ↓
4. [DuckDB] shared_analytics.cdn_analysis'e yazılır
   ↓
5. [Event Bus] cdn_anomaly_detected event'i publish edilir
   {tenant_id, analysis_id, error_rate: 0.067, severity: "P1"}
   ↓
6. [ops_center] Event'i subscribe eder, IncidentAgent tetiklenir
   ↓
7. [ops_center agent M01] Claude Opus ile analiz (P1 severity)
   → RCA Agent (M06) paralel başlatılır
   ↓
8. [DuckDB] shared_analytics.incidents'e yazılır
   shared_analytics.agent_decisions'a yazılır
   ↓
9. [Event Bus] incident_created event'i publish edilir
   ↓
10. [alert_center] Event'i subscribe eder, Slack'e mesaj gönderilir
    [knowledge_base] Event'i subscribe eder, incident doc index'e eklenir
    ↓
11. [DuckDB] shared_analytics.alerts_sent'e yazılır
    ↓
12. [Frontend WebSocket] Tüm subscribe olan dashboard'lar real-time güncellenir
```

---

## 7. SHARED ANALYTICS API — FastAPI Endpoints

```
# Cross-app analytics (tüm app'ler bu verileri okuyabilir)
GET  /analytics/cdn-analysis          Query: tenant_id, limit → [CdnAnalysis]
GET  /analytics/incidents             Query: tenant_id, severity, period → [Incident]
GET  /analytics/qoe-metrics           Query: tenant_id, period → QoEAggregate
GET  /analytics/agent-decisions       Query: tenant_id, app, limit → [AgentDecision]
GET  /analytics/live-events           Query: tenant_id, status → [LiveEvent]
GET  /analytics/alerts-summary        Query: tenant_id, period → AlertSummary
```
