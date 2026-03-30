# API_CONTRACTS.md — FastAPI Endpoint Sözleşmeleri
> Claude Code bu dosyayı API yazarken okur.
> Base URL: http://localhost:8000
> Auth: Bearer JWT (header: Authorization)
> Tenant: X-Tenant-ID header (her request'te zorunlu)
> Versiyon: 2.0 | Mart 2026

---

## 1. AUTH (S-MT-02 ile güncellendi)

```
GET    /auth/tenants              → [{id, name}] (public, auth yok — login dropdown için)
POST   /auth/login                Body: {tenant_id?, email, password}
                                  → {access_token, tenant_id, tenant_name, active_service_id,
                                     service_ids, services[], role}
POST   /auth/switch-service       Auth: Bearer → Body: {service_id}
                                  → {access_token, active_service_id, ...}
                                  403: service_id kullanıcının listesinde değilse
POST   /auth/login/form           Body: OAuth2 form {username, password} → {access_token} (legacy)
PATCH  /auth/password              Auth: Bearer → Body: {current_password, new_password}
                                  → {message: "Password updated"}
                                  400: Current password incorrect / Password too weak
POST   /auth/refresh              Auth: Bearer → {access_token}
POST   /auth/logout               Auth: Bearer → {detail: "Logged out"}
PATCH  /admin/tenant/sector       Auth: tenant_admin+ → Body: {sector}
                                  → {tenant_id, sector}
GET    /admin/modules             Auth: Bearer → [{id, module_name, enabled}]
PATCH  /admin/modules/{id}       Auth: tenant_admin+ → Body: {enabled: bool}
                                  → {module_id, enabled}
                                  400: P0 modules cannot be disabled
GET    /admin/platform/tenants    Auth: super_admin only
                                  → [{id, name, sector, status, services[], user_count}]
```

---

## 1B. SLO TRACKING (S-SLO-01)

```
GET    /slo/definitions             Auth: Bearer → [SLODefinition]
POST   /slo/definitions             Auth: Bearer → Body: {name, metric, target, operator} → SLODefinition
PATCH  /slo/definitions/{id}        Auth: Bearer → Body: SLOUpdate → SLODefinition
DELETE /slo/definitions/{id}        Auth: Bearer → {deleted: id}
GET    /slo/status                  Auth: Bearer → [SLOStatus] (current value + is_met + error_budget)
GET    /slo/history/{slo_id}        Auth: Bearer → [SLOMeasurement] (Query: days=90)
POST   /slo/calculate               Auth: Bearer → [SLOMeasurement] (manual trigger + persist)
GET    /slo/report                  Auth: Bearer → {total_slos, met, breached, slos[]} (Query: period_days=30)
```

---

## 1C. NATURAL LANGUAGE QUERY (S-NL-01)

```
POST   /nl-query/query              Auth: Bearer → Body: {natural_language, max_rows=100}
                                    → {generated_sql, rows[], row_count, execution_ms, columns, warnings, error}
                                    PII columns blocked, tenant_id filter enforced
GET    /nl-query/tables             Auth: Bearer → [{table, description, columns, db}] (PII columns hidden)
GET    /nl-query/examples           Auth: Bearer → [str] (8 example NL queries)
```

---

## 1D. REAL-TIME ANOMALY (S-RT-01)

```
GET    /realtime/anomalies          Auth: Bearer → [AnomalyEvent] (Query: minutes=60)
GET    /realtime/status             → {running, detectors[], last_cycle_at, anomalies_24h}
POST   /realtime/detectors/{name}/toggle  Body: {enabled: bool} → {name, enabled}
```

---

## 2. PLATFORM

```
GET    /health              → {status, version, uptime_s, db_status}
GET    /health/detailed     → {sqlite, duckdb, chromadb, redis, llm_gateway}
GET    /metrics/platform    → {total_events_24h, active_tenants, agent_decisions_24h}
```

---

## 3. OPS CENTER (M01 + M06)

```
GET    /ops/health                   → {status, module}
POST   /ops/incidents/analyze       Body: IncidentEvent → AgentDecisionResult
GET    /ops/incidents               Query: tenant_id, status, severity, limit → [Incident]
GET    /ops/incidents/{id}          → IncidentDetail (with RCA if available)
PATCH  /ops/incidents/{id}/status   Body: StatusUpdate → UpdatedIncident
POST   /ops/rca/trigger             Body: {incident_id, tenant_id} → RCAJob
GET    /ops/rca/{job_id}            → RCAResult (polling)
GET    /ops/dashboard               Query: tenant_id → OpsMetrics (CDN+QoE+Infra from logs.duckdb)
GET    /ops/decisions               Query: tenant_id → [AgentDecision]
POST   /ops/chat                    Body: ChatRequest → ChatResponse
WS     /ws/ops/incidents            WebSocket: real-time incident stream
```

**IncidentEvent (request):**
```json
{
  "tenant_id": "bein_sports",
  "incident_id": "INC-20260319-001",
  "severity": "P1",
  "title": "CDN Error Rate Spike",
  "description": "Error rate exceeded 5% threshold",
  "affected_services": ["cdn", "player"],
  "metrics": {"error_rate": 0.067, "affected_users": 12400},
  "source_app": "log_analyzer",
  "correlation_ids": ["cdn-anomaly-2026-001"]
}
```

Note: `/ops/dashboard` now includes `cdn_health`, `infrastructure`, `qoe`, `detected_incidents` from logs.duckdb

---

## 4. LOG ANALYZER (M07)

```
# Project management
GET    /log-analyzer/projects                    Query: tenant_id → [LogProject]
POST   /log-analyzer/projects                    Body: CreateProjectRequest → LogProject
GET    /log-analyzer/projects/{id}               → LogProjectDetail
DELETE /log-analyzer/projects/{id}               → 204

# Sub-modules
GET    /log-analyzer/sub-modules                 → [SubModule] (akamai, medianova, ...)
GET    /log-analyzer/sub-modules/{name}/status   → SubModuleStatus

# Akamai sub-module
POST   /log-analyzer/akamai/configure            Body: AkamaiConfig → 200
POST   /log-analyzer/akamai/fetch                Body: FetchRequest → FetchJob
GET    /log-analyzer/akamai/jobs/{job_id}        → FetchJobStatus
GET    /log-analyzer/akamai/analysis/{job_id}    → AkamaiAnalysisResult
POST   /log-analyzer/akamai/report               Body: ReportRequest → {download_url}
GET    /log-analyzer/akamai/charts               Query: job_id, chart_type → ChartData

# Agent analysis
POST   /log-analyzer/analyze                     Body: LogAnalysisRequest → AgentDecisionResult
GET    /log-analyzer/results                     Query: tenant_id, project_id, limit → [AnalysisResult]

WS     /ws/log-analyzer/stream                   WebSocket: log ingest real-time
```

**AkamaiConfig (request):**
```json
{
  "tenant_id": "bein_sports",
  "project_id": "proj-001",
  "s3_bucket": "ssport-datastream",
  "s3_prefix": "logs/",
  "schedule_cron": "0 */6 * * *",
  "enabled": true
}
```

### S15 Endpoints

#### Settings
```
GET    /log-analyzer/settings              → Masked credentials döner
POST   /log-analyzer/settings              → AWS + GCP credentials kaydet (encrypted)
DELETE /log-analyzer/settings/credentials  → Credentials sil
GET    /log-analyzer/settings/test-connection?type=s3|bq → Bağlantı testi
```

#### Fetch & Export
```
POST /log-analyzer/akamai/fetch-range
  Body: { job_id, cp_code, start_date, end_date }
  → S3'ten TSV indir, cache'le, FetchJob döner

POST /log-analyzer/bigquery/export
  Body: { job_id, categories: [...], bq_table_id }
  → Seçili kategorileri BQ'ya export et

GET /log-analyzer/bigquery/jobs/{id}
  → Export job durumu (queued/running/complete/failed)
```

### S16-P1 Fixes
```
POST /log-analyzer/projects — eklendi (CreateProjectRequest → LogProject)
GET  /log-analyzer/settings/test-connection?type=s3|bq — eklendi, daima 200 döner
POST /log-analyzer/bigquery/export — GET'ten POST'a düzeltildi
```

### S16-P2 Endpoints

#### Log Structure Analysis
```
POST /log-analyzer/structure/analyze
  Body: { tenant_id, start_date, end_date, sample_size (default 1000, max 5000) }
  → { fields: [FieldAnalysis], total_rows_sampled: int, files_scanned: int }

POST /log-analyzer/structure/mappings
  Body: { tenant_id, field_name, category }
  → 200 (upsert)

GET /log-analyzer/structure/mappings
  Query: tenant_id
  → [{ field_name, category }]
```

**FieldAnalysis model:**
```
field_name, sample_values, null_count, unique_count, inferred_type, current_category
```

**Valid categories:** meta | timing | traffic | content | client | network | response | cache | geo | custom

```
# Medianova Local CDN (from logs.duckdb)
GET    /log-analyzer/medianova/dashboard    Query: tenant_id, hours → CDNMetrics + anomalies
GET    /log-analyzer/medianova/timeseries   Query: tenant_id, metric, hours → list[{timestamp, value}]
GET    /log-analyzer/medianova/anomalies    Query: tenant_id, hours → list[AnomalyEvent]
POST   /log-analyzer/medianova/analyze      Body: {tenant_id, hours, generate_report} → {job_id, status, summary}
```

---

## 5. ALERT CENTER (M13)

```
POST   /alerts/route                Body: AlertEvent → RoutingResult
GET    /alerts                      Query: tenant_id, status, severity, limit → [Alert]
GET    /alerts/{id}                 → AlertDetail
PATCH  /alerts/{id}/acknowledge     Body: {ack_by, note} → Alert
PATCH  /alerts/{id}/resolve         Body: {resolved_by, resolution} → Alert
GET    /alerts/rules                Query: tenant_id → [AlertRule]
POST   /alerts/rules                Body: AlertRule → AlertRule
PUT    /alerts/rules/{id}           Body: AlertRule → AlertRule
DELETE /alerts/rules/{id}           → 204
GET    /alerts/channels             Query: tenant_id → [AlertChannel]
POST   /alerts/test                 Body: {channel_id, message} → TestResult
WS     /ws/alerts/stream            WebSocket: real-time alert stream
POST   /alerts/evaluate                  Body: {tenant_id} → {evaluated, routed, suppressed}
```

---

## 6. VIEWER EXPERIENCE (M02 + M09)

```
# QoE (M02)
POST   /viewer/qoe/event            Body: PlayerEvent → ProcessingResult
GET    /viewer/qoe/metrics          Query: tenant_id, start, end → QoEMetrics
GET    /viewer/qoe/sessions         Query: tenant_id, status, limit → [QoESession]
GET    /viewer/qoe/sessions/{id}    → QoESessionDetail
GET    /viewer/qoe/anomalies        Query: tenant_id, limit → [QoEAnomaly]
WS     /ws/viewer/qoe               WebSocket: real-time QoE stream

# Complaint (M09)
POST   /viewer/complaints/analyze   Body: ComplaintData → AnalysisResult
GET    /viewer/complaints           Query: tenant_id, status, limit → [Complaint]
GET    /viewer/complaints/trends    Query: tenant_id, period → TrendData
```

---

## 7. LIVE INTELLIGENCE (M05 + M11)

```
# Live Events (M05)
GET    /live/events                 Query: tenant_id, status → [LiveEvent]
POST   /live/events/register        Body: LiveEventData → LiveEvent
GET    /live/events/{id}/metrics    → LiveEventMetrics
POST   /live/events/{id}/prescale   Body: {scale_factor} → ScaleJob

# External Data (M11)
GET    /live/external/sportradar    Query: tenant_id, event_id → SportRadarData
GET    /live/external/drm           Query: tenant_id → DRMStatus
GET    /live/external/epg           Query: tenant_id, date → EPGData
POST   /live/external/sync          Body: {source, tenant_id} → SyncJob
WS     /ws/live/events              WebSocket: real-time event stream
```

---

## 8. GROWTH & RETENTION (M18 + M03)

```
GET    /growth/churn-risk           Query: tenant_id, limit → [ChurnRiskProfile]
POST   /growth/analyze              Body: GrowthAnalysisRequest → AnalysisResult
GET    /growth/retention-metrics    Query: tenant_id, period → RetentionMetrics
POST   /growth/data-analyst/query   Body: {tenant_id, question} → DataAnalystResult
GET    /growth/segments             Query: tenant_id → [CustomerSegment]
```

---

## 9. CAPACITY & COST (M16 + M04)

```
GET    /capacity/forecast           Query: tenant_id, horizon_days → CapacityForecast
POST   /capacity/analyze            Body: CapacityRequest → AnalysisResult
POST   /automation/trigger          Body: AutomationRequest → AutomationJob
GET    /automation/jobs             Query: tenant_id, status → [AutomationJob]
GET    /automation/jobs/{id}        → AutomationJobDetail
```

---

## 10. ADMIN & GOVERNANCE (M12 + M17)

```
# Tenant management (M12)
GET    /admin/tenants               → [Tenant]
POST   /admin/tenants               Body: CreateTenantRequest → Tenant
GET    /admin/tenants/{id}          → TenantDetail
PATCH  /admin/tenants/{id}          Body: UpdateTenantRequest → Tenant
GET    /admin/tenants/{id}/modules  → [ModuleConfig]
PATCH  /admin/tenants/{id}/modules/{module} Body: ModuleConfig → ModuleConfig

# Compliance (M17)
GET    /admin/audit-log             Query: tenant_id, start, end, limit → [AuditEvent]
GET    /admin/compliance/report     Query: tenant_id, period → ComplianceReport
GET    /admin/compliance/violations Query: tenant_id, status → [ComplianceViolation]
```

---

## 11. DATA SOURCES

```
GET    /data-sources/configs                    Query: tenant_id → [SourceConfig]
POST   /data-sources/configs                    Body: SourceConfigCreate → SourceConfig
PATCH  /data-sources/configs/{config_id}        Body: partial → SourceConfig
DELETE /data-sources/configs/{config_id}        → 204
POST   /data-sources/sync/{config_id}           → SyncResult
POST   /data-sources/sync-all                   Query: tenant_id → [SyncResult]
GET    /data-sources/sync-status                Query: tenant_id → [SyncStatus]
GET    /data-sources/query/{source_name}        Query: tenant_id, date_from, date_to, limit → QueryResult
POST   /data-sources/import-delete/{config_id}  → SyncResult (sync + delete imported files)
GET    /data-sources/watch-status               Query: tenant_id → WatchStatus
```

**SourceConfig:**
```json
{
  "id": "uuid",
  "tenant_id": "aaop_company",
  "source_name": "medianova",
  "source_type": "local",
  "local_path": "/Users/.../aaop_company/medianova/",
  "s3_bucket": null,
  "s3_prefix": null,
  "enabled": true,
  "sync_interval_minutes": null,
  "last_sync_at": "2026-03-27T08:00:00",
  "last_sync_rows": 12400,
  "last_sync_error": null,
  "created_at": "2026-03-27T07:00:00"
}
```

---

## 12. MOCK DATA GEN (Dev/Test)

```
GET    /mock-data-gen/sources                        → [SourceInfo]
GET    /mock-data-gen/sources/{source}/schema        → SourceSchema
GET    /mock-data-gen/sources/{source}/fields        → [FieldDefinition]
POST   /mock-data-gen/generate                       Body: GenerateRequest → {job_id}
GET    /mock-data-gen/jobs/{job_id}                  → JobStatus
POST   /mock-data-gen/jobs/{job_id}/cancel           → {status: "cancelled"}
GET    /mock-data-gen/output/summary                 → OutputSummary
POST   /mock-data-gen/validate                       → ValidationResults
GET    /mock-data-gen/schemas                        → [ExportSchema]
POST   /mock-data-gen/schemas                        Body: ExportSchemaCreate → ExportSchema
GET    /mock-data-gen/schemas/{schema_id}            → ExportSchema
DELETE /mock-data-gen/schemas/{schema_id}            → 204
GET    /mock-data-gen/schemas/{schema_id}/export/sql → {sql: str}
```

**ExportSchemaCreate (request):**
```json
{
  "name": "CDN Bandwidth Analysis",
  "description": "Measures per-client bandwidth across CDN providers",
  "category": "CDN",
  "sources": [
    { "source_id": "medianova_cdn", "fields": ["timestamp", "client_ip", "bytes_sent", "cache_status"] },
    { "source_id": "origin_server", "fields": ["timestamp", "client_ip", "bytes_sent", "status_code"] }
  ]
}
```

**ExportSchema (response):**
```json
{
  "id": "uuid",
  "name": "CDN Bandwidth Analysis",
  "description": "...",
  "category": "CDN",
  "sources": [...],
  "join_keys": [
    { "type": "exact", "left": "medianova_cdn.client_ip", "right": "origin_server.client_ip", "note": "Same client, different CDN layer", "window_ms": null },
    { "type": "window", "left": "medianova_cdn.timestamp", "right": "origin_server.timestamp", "note": "±100ms (cache miss moment)", "window_ms": 100 }
  ],
  "insight": "client_ip başına toplam bandwidth hesaplanır, overlap window çıkarılır.",
  "created_at": "2026-03-26T14:00:00"
}
```

---

## 13. AI LAB, KNOWLEDGE BASE, DEVOPS ASSISTANT

```
# AI Lab (M10 + M14)
POST   /ai-lab/experiment           Body: ExperimentRequest → ExperimentJob
GET    /ai-lab/experiments          Query: tenant_id → [Experiment]
GET    /ai-lab/models               Query: tenant_id → [ModelRecord]
POST   /ai-lab/models/evaluate      Body: EvalRequest → EvalResult

# Knowledge Base (M15)
POST   /knowledge/search            Body: {query, tenant_id, top_k} → [KBResult]
POST   /knowledge/ingest            Body: Document → IngestJob
GET    /knowledge/documents         Query: tenant_id, limit → [KBDocument]

# DevOps Assistant (M08)
POST   /devops/assist               Body: {question, context, tenant_id} → AssistResult
GET    /devops/runbooks             Query: tenant_id, tag → [Runbook]
POST   /devops/diagnose             Body: DiagnosticRequest → DiagnosticResult
```

---

## 14. ORTAK RESPONSE MODELLERİ

```python
# Tüm agent kararları bu forma uyar
class AgentDecisionResult(BaseModel):
    decision_id: str
    tenant_id: str
    app: str
    action: str
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH']
    approval_required: bool        # HIGH risk ise True
    llm_model_used: str
    reasoning_summary: str
    tools_executed: list[str]
    confidence_score: float        # 0.0 - 1.0
    duration_ms: int
    timestamp: datetime

# Tüm hata yanıtları
class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: str | None
    request_id: str
    timestamp: datetime
```

---

## 15. WEBSOCKET PROTOKOLÜ

> ✅ **S-WS-01 ile implement edildi (Mart 2026).** Tüm 4 endpoint aktif. Native FastAPI WebSocket, per-tenant broadcast, auto-reconnect frontend.

```typescript
// Socket.IO events (client → server)
socket.emit('subscribe', { app: 'ops_center', tenant_id: 'bein_sports' })
socket.emit('unsubscribe', { app: 'ops_center' })
socket.emit('agent_chat', { app: 'ops_center', message: '...', tenant_id: '...' })

// Socket.IO events (server → client)
socket.on('incident_update', (data: IncidentEvent) => ...)
socket.on('alert_new', (data: Alert) => ...)
socket.on('agent_stream', (data: { chunk: string, done: boolean }) => ...)
socket.on('metric_update', (data: MetricUpdate) => ...)
```
