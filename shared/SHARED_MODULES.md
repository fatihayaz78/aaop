# shared/SHARED_MODULES.md — Shared Modüller Spec
> Her sprint başında ilgili bölümler okunur.
> Versiyon: 1.0 | 30 Mart 2026
> KOD KAYNAKLI — kaynak kodu değişirse bu dosya da güncellenir.

---

## İÇİNDEKİLER
1. agents/ — BaseAgent (LangGraph)
2. event_bus.py — Cross-App Event Bus
3. llm_gateway.py — LLM Routing & Cache
4. schemas/ — Ortak Veri Modelleri
5. models/ — Tenant & Service Modelleri
6. middleware/ — ServiceContextMiddleware
7. clients/ — DB & Cache Client'lar
8. utils/ — Settings & PII Scrubber
9. ingest/ — Log Ingest Pipeline
10. realtime/ — Anomali Motoru
11. nl_query/ — NL→SQL Motoru
12. slo/ — SLA/SLO Hesaplama

---

## 1. agents/base_agent.py — BaseAgent (LangGraph 4-Step Cycle)

```
Dosya:       shared/agents/base_agent.py
Amaç:        Tüm 22 app agent'ın ortak 4-adım LangGraph döngüsü
Kullananlar: Tüm 11 app (agent.py dosyaları)
```

### AgentState (TypedDict, total=False)
| Alan | Tip | Açıklama |
|---|---|---|
| tenant_id | str | |
| tenant_context | dict[str, Any] | |
| input | dict[str, Any] | invoke() input_data |
| context | dict[str, Any] | Redis → DuckDB → ChromaDB |
| reasoning | dict[str, Any] | LLM JSON parse sonucu |
| tool_results | dict[str, Any] | Tool execution output |
| output | dict[str, Any] | Final output |
| approval_required | bool | HIGH risk → True |
| error | str \| None | |

### BaseAgent Sınıfı
```python
class BaseAgent:
    app_name: str = "base"

    def __init__(self, llm_gateway: LLMGateway | None = None, event_bus: EventBus | None = None) -> None

    # ── Abstract (subclass MUST override) ──
    @abstractmethod def get_tools(self) -> list[dict[str, Any]]
    @abstractmethod def get_system_prompt(self) -> str
    @abstractmethod def get_llm_model(self, severity: str | None = None) -> str

    # ── Public ──
    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]
    async def run(self, tenant_context: TenantContext, input_data: dict[str, Any] | None = None) -> AgentState

    # ── Override noktaları (4-step cycle) ──
    async def _context_loader_node(self, state: AgentState) -> AgentState   # Redis → DuckDB → ChromaDB
    async def _reasoning_node(self, state: AgentState) -> AgentState        # LLM call + JSON parse
    async def _tool_execution_node(self, state: AgentState) -> AgentState   # Risk-level gating
    async def _memory_update_node(self, state: AgentState) -> AgentState    # DuckDB + Redis write
```

### Tool Definition Format
```python
{"name": "tool_name", "risk_level": "LOW"|"MEDIUM"|"HIGH", "func": async_callable}
```

### Risk-Level Gating
- **LOW** → auto execute
- **MEDIUM** → auto execute + EventBus notify
- **HIGH** → `approval_required=True`, execution skipped → END

### Kullanım
```python
class MyAgent(BaseAgent):
    app_name = "my_app"
    def get_tools(self): return [...]
    def get_system_prompt(self): return "..."
    def get_llm_model(self, severity=None): return "claude-sonnet-4-20250514"
```

### Kritik Kurallar
- AgentState alanları değişirse TÜM 22 agent etkilenir
- `_memory_update_node` override edilen en yaygın nokta (app-specific output)
- `invoke()` override: erken dönüş (no-data, dedup, gate)

---

## 2. event_bus.py — Cross-App Event Bus

```
Dosya:       shared/event_bus.py
Amaç:        asyncio.Queue tabanlı 9 event type, 8 agent subscribe
Kullananlar: 8 agent + backend/main.py lifespan
```

### EventType (StrEnum — 9 tip)
| EventType | Publisher | Subscribers |
|---|---|---|
| CDN_ANOMALY_DETECTED | log_analyzer | ops_center, alert_center |
| INCIDENT_CREATED | ops_center | alert_center, knowledge_base |
| RCA_COMPLETED | ops_center | knowledge_base, alert_center |
| QOE_DEGRADATION | viewer_experience | ops_center, alert_center |
| LIVE_EVENT_STARTING | live_intelligence | ops_center, log_analyzer, alert_center |
| EXTERNAL_DATA_UPDATED | live_intelligence | ops_center, growth_retention |
| CHURN_RISK_DETECTED | growth_retention | alert_center |
| SCALE_RECOMMENDATION | capacity_cost | ops_center, alert_center |
| ANALYSIS_COMPLETE | log_analyzer | growth_retention, viewer_experience |

### API
```python
class EventBus:
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None
    async def publish(self, event: BaseEvent) -> None
    async def start(self) -> None      # asyncio.Task — 1s timeout poll
    async def stop(self) -> None

def get_event_bus() -> EventBus       # singleton
```

### Kritik Kurallar
- `start()` yeni Queue oluşturur (cross-loop safety)
- EventType eklenmesi tüm subscriber'ları etkilemez ama EVENT_ROUTING güncellenmeli
- Handler exception'lar yutulur (log only), uygulamayı çökertmez

---

## 3. llm_gateway.py — LLM Routing & Cache

```
Dosya:       shared/llm_gateway.py
Amaç:        Severity-based model routing, Redis cache, retry, PII scrub
Kullananlar: Tüm agent reasoning node'ları
```

### Model Routing
| Severity | Model |
|---|---|
| P0 | claude-opus-4-20250514 |
| P1 | claude-opus-4-20250514 |
| P2 | claude-sonnet-4-20250514 |
| P3 | claude-haiku-4-5-20251001 |
| None | claude-sonnet-4-20250514 (DEFAULT) |

### API
```python
class LLMGateway:
    def __init__(self, redis_client: RedisClient | None = None) -> None
    def select_model(self, severity: SeverityLevel | None = None) -> str
    async def invoke(self, prompt: str, severity: SeverityLevel | None = None,
                     model: str | None = None, system_prompt: str | None = None,
                     max_tokens: int = 4096, use_cache: bool = True) -> dict[str, Any]
    # Returns: {content, model, input_tokens, output_tokens, stop_reason}
```

### Sabitler
- Cache TTL: 86400s (24 saat)
- Retry: 3 attempt, exponential backoff (1–10s)
- PII scrub: `scrub(prompt)` + `scrub(system_prompt)` her çağrıda

---

## 4. schemas/ — Ortak Veri Modelleri

### base_event.py
- `SeverityLevel(StrEnum)`: P0, P1, P2, P3
- `RiskLevel(StrEnum)`: LOW, MEDIUM, HIGH
- `TenantContext(BaseModel)`: tenant_id, user_id?, role?
- `BaseEvent(BaseModel)`: event_id (auto UUID), event_type, tenant_id, source_app, severity, payload, correlation_ids, created_at

### agent_decision.py
- `AgentDecision(BaseModel)`: decision_id, tenant_id, app, action, risk_level, approval_required, llm_model_used, reasoning_summary, tools_executed, confidence_score, duration_ms, created_at

---

## 5. models/tenant_models.py

- `TenantBase`: id, name, sector, status
- `ServiceBase`: id, tenant_id, name, duckdb_schema, sector_override?, status
- `TenantWithServices`: TenantBase + services: list[ServiceBase]

---

## 6. middleware/service_context.py

JWT → service_id → duckdb_schema resolution. 5dk in-memory cache.
Fallback: `sport_stream` (token yoksa/geçersizse).

---

## 7. clients/ — DB & Cache Client'lar

### SQLiteClient
```python
async connect() → disconnect() → execute(sql, params) → fetch_all() → fetch_one()
init_tables()  # tenants, users, module_configs, services, audit_log, settings
```

### DuckDBClient (analytics.duckdb)
```python
connect() → disconnect() → execute(sql, params) → fetch_all() → fetch_one()
init_tables()  # shared_analytics: cdn_analysis, incidents, qoe_metrics, live_events, agent_decisions, alerts_sent
```

### LogsDuckDBClient (logs.duckdb)
```python
get_connection() → disconnect()
ensure_tenant_schema(tenant_id, *, schema_name=None)
ensure_source_table(tenant_id, source, create_sql, *, schema_name=None)
query(tenant_id, sql, params=None) -> list[dict]
insert_batch(tenant_id, source, records, *, schema_name=None) -> int
delete_older_than(tenant_id, source, days=30, *, schema_name=None) -> int
```

### RedisClient
```python
async connect() → disconnect() → get(key) → set(key, value, ttl?)
async get_json(key) → set_json(key, value, ttl?) → delete(key) → exists(key)
```

### ChromaClient
```python
connect() → get_or_create_collection(name) → init_collections()
add_documents(collection, documents, ids, metadatas?) → query(collection, query_texts, n_results=5)
```

### GCP Geçiş
| Lokal | GCP | Dosya |
|---|---|---|
| SQLite | Cloud Spanner | sqlite_client.py |
| DuckDB | BigQuery | duckdb_client.py |
| ChromaDB | Vertex AI VS | chroma_client.py |
| Redis | Memorystore | redis_client.py |

---

## 8. utils/

### settings.py
`Settings(BaseSettings)` — .env'den okur. Önemli: `anthropic_api_key`, `jwt_secret_key`, `sqlite_path`, `duckdb_path`, `redis_host`.
`get_settings()` — `@lru_cache` singleton.

### pii_scrubber.py
5 regex pattern: Email, Phone, IPv4, TC_KIMLIK, Credit Card → `[EMAIL]`, `[PHONE]`, `[IP]`, `[TC_KIMLIK]`, `[CARD]`
- `scrub(text: str) -> str`
- `scrub_dict(data: dict, fields: list[str]?) -> dict`

---

## 9. ingest/ — Log Ingest Pipeline

### log_queries.py — 12 Query Helper
| Fonksiyon | Kaynak | Window |
|---|---|---|
| get_cdn_metrics | medianova_logs | 24h |
| get_cdn_anomalies | medianova_logs | 24h |
| get_drm_status | widevine+fairplay | 24h |
| get_api_health | api_logs_logs | 24h |
| get_infrastructure_health | newrelic_apm_logs | 24h |
| get_player_qoe | npaw+player_events | 24h |
| detect_incidents_from_logs | multi-source | 1h |
| get_app_reviews | app_reviews_logs | 168h |
| get_epg_schedule | epg_logs | all |
| get_churn_metrics | crm_subscriber | all |
| get_billing_summary | billing_logs | 720h |
| get_data_source_stats | all sources | all |

### log_schemas.py — 13 DuckDB DDL
medianova, origin_server, widevine_drm, fairplay_drm, player_events, npaw_analytics, api_logs, newrelic_apm, crm_subscriber, epg, billing, push_notifications, app_reviews

### sync_engine.py
`SyncEngine(sqlite, logs_duckdb)` → `sync_source()` → `sync_all()`
mtime-based upsert, delete_after_import, ingestion_log tracking.

### jsonl_parser.py
`parse_jsonl_gz(file, source, tenant) → list[dict]` — 13 source field mapping.
`scan_source_directory(path, source) → list[str]`

---

## 10. realtime/ — Anomali Motoru

```
Dosya:       shared/realtime/anomaly_engine.py
Amaç:        30s polling, 4 detector, EventBus publish
Kullananlar: backend/main.py lifespan, /realtime/ router
```

### Detector Eşikleri
| Detector | Metric | Eşik | Severity |
|---|---|---|---|
| CDNDetector | error_rate | >0.05 / >0.15 | P1 / P0 |
| DRMDetector | failure_rate | >0.10 | P1 |
| QoEDetector | avg_score | <2.5 / <1.5 | P1 / P0 |
| APIDetector | error_rate / p99_ms | >0.05 / >2000 | P2 |

### AnomalyEvent (Pydantic)
event_id, tenant_id, detector, severity, metric, current_value, threshold, window_minutes, detected_at, source_table

### API
```python
class AnomalyEngine:
    async start() → stop()
    get_recent(minutes=60) → list[AnomalyEvent]
    get_status() → dict
    toggle_detector(name, enabled) → bool

def get_anomaly_engine() → AnomalyEngine   # singleton
```

---

## 11. nl_query/ — NL→SQL Motoru

```
Dosya:       shared/nl_query/nl_engine.py
Amaç:        Doğal dil → güvenli SQL, PII korumalı
Kullananlar: /nl-query/ router, growth_retention DataAnalystAgent
```

### NLQueryResult (Pydantic)
natural_language, generated_sql, rows, row_count, execution_ms, columns, warnings, error

### SchemaRegistry — 18 Sorgulanabilir Tablo
6 analytics (incidents, qoe_metrics, cdn_analysis, live_events, agent_decisions, alerts_sent) +
12 logs ({schema}.medianova_logs, player_events_logs, api_logs_logs, npaw_analytics_logs, newrelic_apm_logs, crm_subscriber_logs, billing_logs, epg_logs + 4 more)

### SQLValidator — 6 Güvenlik Kontrolü
1. SELECT-only (INSERT/UPDATE/DELETE/DROP yasak)
2. tenant_id filter zorunlu
3. PII columns (client_ip, subscriber_id) yasak
4. Sadece QUERYABLE_TABLES
5. LIMIT zorunlu (max 1000)
6. Write keyword regex

---

## 12. slo/ — SLA/SLO Hesaplama

```
Dosya:       shared/slo/slo_calculator.py
Amaç:        5 metrik SLO tanım + ölçüm + error budget
Kullananlar: /slo/ router, admin-governance SLO tab
```

### 5 Metrik
| Metric | Kaynak | Hesaplama | Default Target |
|---|---|---|---|
| availability | incidents (P0) | 1 - (P0_count × 30min / total_min) | ≥ 99.9% |
| qoe_score | npaw_analytics_logs | AVG(qoe_score) | ≥ 3.5 |
| cdn_error_rate | medianova_logs | errors/total | ≤ 5% |
| api_p99 | api_logs_logs | PERCENTILE_CONT(0.99) | ≤ 1000ms |
| incident_mttr | incidents (resolved) | AVG(mttr_seconds)/60 | ≤ 60 min |

### Pydantic Models
- `SLODefinition`: id, tenant_id, name, metric, target, operator (gte/lte), window_days
- `SLOMeasurement`: slo_id, measured_value, target, is_met, error_budget_pct
- `SLOStatus`: current_value, is_met, error_budget_remaining_pct, trend

---

## Cross-Module Bağımlılık Haritası

| Modül | Kullanan App'ler |
|---|---|
| base_agent | ops_center, log_analyzer, alert_center, viewer_experience, live_intelligence, growth_retention, capacity_cost, admin_governance, ai_lab, knowledge_base, devops_assistant |
| event_bus | ops_center(5), alert_center(7), viewer_experience(2), growth_retention(2), capacity_cost(1), knowledge_base(2) |
| llm_gateway | Tüm 22 agent (reasoning node) |
| logs_duckdb_client | log_queries, realtime detectors, nl_query executor |
| duckdb_client | base_agent memory_update, slo_calculator, growth tools |
| sqlite_client | auth, admin_governance, slo definitions, service_context |
| redis_client | llm_gateway cache, alert dedup, live_intelligence cache |
| chroma_client | knowledge_base, viewer_experience, devops_assistant |
| pii_scrubber | llm_gateway (her çağrıda), nl_engine (NL input) |
| log_queries | 7 P0/P1 router, realtime detectors, slo_calculator |

---

## Kırılma Noktaları (Breaking Change Uyarıları)

| Değişiklik | Etki | Risk |
|---|---|---|
| AgentState alan ekleme/silme | 22 agent + integration tests | YÜKSEK |
| EventType enum değeri ekleme | Zararsız (ama EVENT_ROUTING güncelle) | DÜŞÜK |
| EventType enum silme | Subscribe eden agent'lar bozulur | YÜKSEK |
| LLM model ID değişikliği | Tüm agent reasoning etkilenir | ORTA |
| DuckDB schema adı değişikliği | logs_duckdb, log_queries, nl_query | YÜKSEK |
| BaseAgent._memory_update_node imzası | 11 agent override | YÜKSEK |
| QUERYABLE_TABLES değişikliği | nl_query validator + LLM prompt | ORTA |
| AnomalyEvent alan değişikliği | realtime router + frontend | DÜŞÜK |
| SLODefinition metric ekleme | slo_calculator._measure_metric | DÜŞÜK |

---

## Test Gereksinimleri

```bash
# base_agent değişirse:
pytest tests/unit/test_base_agent.py tests/integration/test_event_flows.py

# event_bus değişirse:
pytest tests/unit/test_event_bus.py tests/integration/test_event_flows.py

# llm_gateway değişirse:
pytest tests/unit/test_llm_gateway.py

# log_queries değişirse:
pytest tests/unit/test_log_queries.py tests/unit/test_log_queries_p1.py

# clients değişirse:
pytest tests/unit/test_sqlite_client.py tests/unit/test_duckdb_client.py
pytest tests/unit/test_redis_client.py tests/unit/test_chroma_client.py

# realtime değişirse:
pytest shared/realtime/tests/

# nl_query değişirse:
pytest shared/nl_query/tests/

# slo değişirse:
pytest shared/slo/tests/

# pii_scrubber değişirse:
pytest tests/unit/test_pii_scrubber.py

# FULL SUITE (her sprint sonunda):
pytest tests/ shared/slo/tests/ shared/nl_query/tests/ shared/realtime/tests/ -q
```
