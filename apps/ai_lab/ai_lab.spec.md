# ai_lab.spec.md — AI Lab
> Kapsam: M10 AI Experimentation + M14 ML Model Governance | Sprint: S08-A | Kritiklik: P2

## 1. KULLANICI
AI/ML Mühendisi, Data Scientist — Model denemesi, A/B testi, prompt optimizasyonu

## 2. TABS
Experiments | Model Registry | Prompt Lab | Evaluations | Cost Tracker

## 3. AGENT MİMARİSİ
```python
class ExperimentationAgent(BaseAgent):
    app_name = "ai_lab"
    # claude-sonnet-4-20250514
    # A/B test tasarımı + istatistiksel analiz (p-value, CI)

class ModelGovernanceAgent(BaseAgent):
    app_name = "ai_lab"
    # claude-haiku-4-5-20251001 (rutin metrik toplama)
    # LLM Gateway'den maliyet + latency toplar
    # token budget > %80 → uyarı
    # Model performans drift tespiti
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| create_experiment | LOW | auto |
| get_experiment_results | LOW | auto |
| analyze_statistical_significance | LOW | auto |
| get_llm_cost_metrics | LOW | auto |
| evaluate_model | LOW | auto |
| register_prompt_version | MEDIUM | auto+notify |
| update_model_config | HIGH | approval_required |
| switch_model_production | HIGH | approval_required |

## 5. API
```
prefix: /ai-lab
ref:    API_CONTRACTS.md → Bölüm 11
```

## 6. CROSS-APP
```
DuckDB OKUMA: shared_analytics.agent_decisions (tüm app'lerin model kullanımı)
```

## 7. LOKAL VERİ
### SQLite
```sql
CREATE TABLE model_registry (
    id TEXT PRIMARY KEY, model_name TEXT NOT NULL,
    version TEXT, config_json TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE prompt_versions (
    id TEXT PRIMARY KEY, app TEXT NOT NULL,
    prompt_type TEXT NOT NULL, version INTEGER NOT NULL,
    content TEXT NOT NULL, is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
```

## 8. TEST
```bash
pytest apps/ai_lab/tests/ -v --cov=apps/ai_lab --cov-fail-under=80
```

## Sprint Completion — S08 (2026-03-21)

### Files Created
- `apps/ai_lab/__init__.py`, `config.py`, `schemas.py`, `prompts.py`, `tools.py`, `agent.py`
- `apps/ai_lab/tests/` — conftest, test_agent (8), test_tools (14), test_schemas (6), test_config (2)
- `backend/routers/ai_lab.py` — /ai-lab prefix

### Hard Constraints Verified
- ✅ ExperimentationAgent AND ModelGovernanceAgent both implemented
- ✅ switch_model_production → approval_required=True
- ✅ update_model_config → approval_required=True
- ✅ token budget > 80% → warning logged (structlog)
- ✅ DuckDB reads: shared_analytics.agent_decisions (all apps' model usage)

### Deviations
- None. All spec constraints met.

---
## Sprint Completion — S22
- Date: Mart 2026
- seed.py: 10 experiments + 8 model registry entries
- 6 endpoints (dashboard, experiments CRUD, models list/detail)
- Frontend: 4 tabs
- Tests: 42 passed, 0 failures
- Status: ✅ Complete

---
## Sprint Completion — S-AGENT-05

- Date: 2026-03-29
- Tests: 8 passed (agent), 148 passed (platform), 0 failure
- ExperimentationAgent: BaseAgent 4-adım döngüsü aktif (statistical significance)
- ModelGovernanceAgent: BaseAgent 4-adım döngüsü aktif (budget warning + action mapping)
- Deviations: None
