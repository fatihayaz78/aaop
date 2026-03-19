# docs/SPRINT_PLAN.md — Sprint Yönetimi
> Claude Code bu dosyayı her sprint'te okur.
> Sprint bitince: biten sprint CHANGELOG.md'ye taşınır, bu dosya güncellenir.
> Versiyon: 2.0 | Mart 2026

---

## AKTİF SPRINT: S03 — Ops Center (M01 + M06)

**Hedef:** Ops Center app — Incident management, RCA agent, Event Bus subscribe
**Bitti Kriteri:** `pytest apps/ops_center/tests/` yeşil | `/ops` API 200 | Incident create/resolve flow
**Test Komutu:**
```bash
source ~/.venvs/aaop/bin/activate
pytest apps/ops_center/tests/ -v --cov=apps/ops_center --cov-report=term-missing
curl http://localhost:8000/ops/dashboard
```

---

## SPRINT SIRASI TABLOSU

| Sprint | Kapsam | Bağımlılıklar | Tahmini Süre |
|---|---|---|---|
| **S01** | Foundation Layer | — | ✅ Tamamlandı (2026-03-19) |
| **S02** | Log Analyzer (Akamai sub-module + agent) | S01 | ✅ Tamamlandı (2026-03-19) |
| **S03** | Ops Center (M01 + M06) | S01, S02 (event bus) | 4-5 gün |
| **S04** | Alert Center (M13) | S01, S03 | 2-3 gün |
| **S05** | Viewer Experience (M02 + M09) | S01 | 3-4 gün |
| **S06** | Live Intelligence (M05 + M11) | S01, S03 | 4-5 gün |
| **S07** | Growth & Retention + Capacity & Cost | S01, S05 | 4-5 gün |
| **S08** | AI Lab + Knowledge Base + DevOps + Admin | S01 | 4-5 gün |
| **S09** | Cross-app integrations + Full Frontend + E2E | S01–S08 | 5-7 gün |

---

## SPRINT KAPANIŞ PROTOKOLÜ (Her Sprint İçin Aynı)

Claude Code şu adımları sırayla uygular:

```
1. pytest tests/ -v --cov=. --cov-fail-under=80   → yeşil olmalı
2. ruff check .                                     → hata yok
3. mypy . --ignore-missing-imports                  → hata yok
4. CHANGELOG.md güncelle (sprint özeti ekle)
5. docs/SPRINT_PLAN.md güncelle (biten sprint ✅, aktif sprint → sonraki)
6. git add -A
7. git commit -m "chore(sprint): close S0X — <özet>"
8. git push
```

---

## TAMAMLANAN SPRINTLER

### S01 — Foundation Layer (2026-03-19)

**Sonuç:** 86 test yeşil | 96% coverage (shared + backend) | ruff + mypy sıfır hata

Tamamlanan adımlar (22/22):
- `pyproject.toml`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`
- `shared/` — settings, schemas (BaseEvent, AgentDecision), 4 client (SQLite, DuckDB, ChromaDB, Redis)
- `shared/event_bus.py` — 9 EventType, asyncio.Queue pub/sub
- `shared/llm_gateway.py` — severity routing (Haiku/Sonnet/Opus), tenacity retry, Redis cache
- `shared/utils/pii_scrubber.py` — regex PII temizleme
- `shared/agents/base_agent.py` — LangGraph 4-adim StateGraph
- `backend/` — FastAPI main + auth (JWT) + dependencies + middleware (rate_limit, tenant_context) + WebSocket manager
- SQLite init (tenants, users, module_configs, audit_log) + DuckDB init (6 shared_analytics tablosu)
- `tests/conftest.py` + 14 unit test dosyasi
- `frontend/` — Next.js 14 + TypeScript + Tailwind + 11 app page stubs + design tokens

### S02 — Log Analyzer (2026-03-19)

**Sonuç:** 36 test yeşil | 80% coverage | ruff sıfır hata | 86 S01 test regresyon yok

Tamamlanan:
- `apps/log_analyzer/config.py` — LogAnalyzerConfig (S3, thresholds, paths)
- `apps/log_analyzer/schemas.py` — LogProject, LogSource, FetchJob, AnalysisResult, SubModuleStatus
- `apps/log_analyzer/sub_modules/base_sub_module.py` — BaseSubModule ABC
- `apps/log_analyzer/sub_modules/__init__.py` — SubModuleRegistry
- `apps/log_analyzer/sub_modules/akamai/` — tam Akamai DataStream 2 implementasyonu:
  - `schemas.py` — AkamaiLogEntry (21 alan), AkamaiConfig, AkamaiMetrics, AkamaiAnomaly
  - `parser.py` — CSV/JSON/NDJSON parser, PII scrub (cliIP + UA SHA256 hash)
  - `analyzer.py` — metrics hesaplama + 3 anomaly detection (error_rate, cache_hit, ttfb)
  - `charts.py` — 21 Plotly dark-theme chart (kaleido==0.2.1)
  - `reporter.py` — python-docx DOCX rapor (cover, summary, metrics table, anomalies, chart gallery)
  - `scheduler.py` — APScheduler AsyncIOScheduler
- `apps/log_analyzer/tools.py` — 12 tool (LOW/MEDIUM/HIGH risk tagged)
- `apps/log_analyzer/prompts.py` — system + analysis prompts
- `apps/log_analyzer/agent.py` — LogAnalyzerAgent(BaseAgent) + Event Bus publish (cdn_anomaly_detected, analysis_complete)
- `backend/routers/log_analyzer.py` — /log-analyzer prefix, health, sub-modules, projects, results
- `apps/log_analyzer/sub_modules/medianova/` — placeholder stub
- Test fixtures: sample_akamai_normal.csv, sample_akamai_spike.csv

---

## MOCK DATA SENARYOLARI (Test için)

| Senaryo | Açıklama | Hangi Sprint'te Kullanılır |
|---|---|---|
| `NORMAL_WEEKDAY` | Rutin gün, düşük trafik | S01-S09 (smoke) |
| `MATCH_DAY_DERBY` | Galatasaray-Fenerbahçe, yüksek trafik | S03, S06, S09 |
| `DRM_OUTAGE` | Widevine servisi down | S04, S06 |
| `CDN_SPIKE` | Akamai error rate spike | S02, S03 |
| `CHURN_RISK` | Retention düşüşü senaryosu | S07 |
| `CAPACITY_BREACH` | Kaynak limitine yaklaşma | S07 |

> Mock data: `github.com/fatihayaz78/aaop-mock-data-gen` reposundan çekil
> Lokal konum: `tests/integration/scenarios/`
