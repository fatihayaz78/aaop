# devops_assistant.spec.md — DevOps Assistant
> Kapsam: M08 AI DevOps Assistant | Sprint: S08-C | Kritiklik: P2
> Not: Terminal-like UX, teknik kullanıcı

## 1. KULLANICI
Platform Mühendisi, DevOps Mühendisi — Deployment, tanılama, runbook çalıştırma

## 2. TABS
| Tab | Açıklama |
|---|---|
| Assistant | Ana sohbet + komut öneri (terminal-like) |
| Diagnostics | Servis sağlık kontrolü |
| Deployments | Deployment geçmişi ve durum |
| Runbooks | Runbook listesi ve çalıştırma |

## 3. AGENT MİMARİSİ
```python
class DevOpsAssistantAgent(BaseAgent):
    app_name = "devops_assistant"
    # claude-sonnet-4-20250514 (teknik Q&A)
    # Bağlam: platform durumu + aktif incident + deployment geçmişi
    # Komut önerisi: güvenli → öner, tehlikeli → işaretle
    # Knowledge Base'den runbook ara (ChromaDB)
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| check_service_health | LOW | auto |
| get_deployment_history | LOW | auto |
| search_runbooks | LOW | auto |
| get_platform_metrics | LOW | auto |
| suggest_command | LOW | auto |
| create_deployment_record | MEDIUM | auto+notify |
| execute_runbook | HIGH | approval_required |
| restart_service | HIGH | approval_required |

## 5. API
```
prefix: /devops
ref:    API_CONTRACTS.md → Bölüm 11
```

## 6. CROSS-APP
```
DuckDB OKUMA: shared_analytics.incidents, agent_decisions
ChromaDB OKUMA: 'runbooks' collection (knowledge_base'den)
```

## 7. LOKAL VERİ
### SQLite
```sql
CREATE TABLE deployments (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    service TEXT NOT NULL, version TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    deployed_by TEXT, notes TEXT,
    started_at TEXT, completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

## 8. TEST
```bash
pytest apps/devops_assistant/tests/ -v --cov=apps/devops_assistant --cov-fail-under=80
```

## Sprint Completion — S08 (2026-03-21)

### Files Created
- `apps/devops_assistant/__init__.py`, `config.py`, `schemas.py`, `prompts.py`, `tools.py`, `agent.py`
- `apps/devops_assistant/tests/` — conftest, test_agent (7), test_tools (10), test_schemas (5), test_config (2)
- `backend/routers/devops_assistant.py` — /devops prefix

### Hard Constraints Verified
- ✅ restart_service → approval_required=True
- ✅ execute_runbook → approval_required=True
- ✅ Reads ChromaDB 'runbooks' collection (knowledge_base's collection)
- ✅ DuckDB reads: shared_analytics.incidents, agent_decisions

### Deviations
- None. All spec constraints met.

---
## Sprint Completion — S22
- Date: Mart 2026
- seed.py: reads from knowledge_base collections
- 4 endpoints (dashboard, chat with danger detection, runbooks, search)
- Frontend: 3 tabs (Chat as default)
- Tests: 36 passed, 0 failures
- Status: ✅ Complete

---
## Sprint Progress — S-DI-04 (2026-03-28)
### logs.duckdb Entegrasyonu
- GET /devops/dashboard: infra_health (newrelic_apm_logs), api_health (api_logs_logs)
- DuckDB OKUMA: logs.duckdb aaop_company schema (newrelic_apm_logs, api_logs_logs)
