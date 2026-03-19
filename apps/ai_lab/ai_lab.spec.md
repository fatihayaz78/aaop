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
