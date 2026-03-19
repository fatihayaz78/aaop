# viewer_experience.spec.md — Viewer Experience
> Kapsam: M02 AI QoE Platform + M09 Complaint Analyzer | Sprint: S05 | Kritiklik: P1

## 1. KULLANICI
QoE Analist, Müşteri Deneyimi Ekibi — Video kalite izleme, şikayet analizi

## 2. TABS
| Tab | Veri |
|---|---|
| QoE Dashboard | DuckDB: qoe_metrics |
| Live Sessions | Redis + DuckDB |
| Anomaly Feed | DuckDB + Event Bus |
| Complaints | SQLite: complaints |
| Trends | DuckDB |
| Segments | DuckDB |

## 3. AGENT MİMARİSİ
```python
class QoEAgent(BaseAgent):
    app_name = "viewer_experience"
    # Anomali analizi → claude-sonnet-4-20250514
    # Toplu scoring   → claude-haiku-4-5-20251001
    # kalite skoru < 2.5 → qoe_degradation event
    # Dedup: aynı session 5 dakika window

class ComplaintAgent(BaseAgent):
    app_name = "viewer_experience"
    # claude-sonnet-4-20250514
    # NLP: kategori + duygu + öncelik
    # ChromaDB: benzer şikayetleri grupla
    # QoE verileriyle şikayeti ilişkilendir
```

## 4. QoE SKOR FORMÜLÜ (0.0 — 5.0)
```python
score = 5.0
score -= session.buffering_ratio * 10.0        # Her %1 buffering: -0.1
score -= max(0, (session.startup_time_ms - 2000) / 1000)  # 2s üzeri: -0.1/s
score -= len(session.errors) * 0.3             # Her hata: -0.3
if session.bitrate_avg < 1500:
    score -= (1500 - session.bitrate_avg) / 1000
return max(0.0, min(5.0, round(score, 2)))
```

## 5. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| score_qoe_session | LOW | auto |
| get_session_context | LOW | auto |
| detect_qoe_anomaly | LOW | auto |
| search_similar_issues | LOW | auto |
| categorize_complaint | LOW | auto |
| find_related_complaints | LOW | auto |
| write_qoe_metrics | MEDIUM | auto+notify |
| write_complaint | MEDIUM | auto+notify |
| trigger_qoe_alert | MEDIUM | auto+notify |
| escalate_complaint | HIGH | approval_required |

## 6. API
```
prefix:    /viewer
websocket: /ws/viewer/qoe
ref:       API_CONTRACTS.md → Bölüm 6
```

## 7. CROSS-APP
```
OUTPUT: qoe_degradation → ops_center, alert_center (skor < 2.5)
INPUT:  analysis_complete ← log_analyzer
        live_event_starting ← live_intelligence

DuckDB YAZMA: shared_analytics.qoe_metrics, agent_decisions
DuckDB OKUMA: shared_analytics.cdn_analysis, live_events
```

## 8. LOKAL VERİ
### SQLite
```sql
CREATE TABLE complaints (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    source TEXT, category TEXT, sentiment TEXT,
    priority TEXT, status TEXT DEFAULT 'open',
    content_hash TEXT, resolution TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```
### Redis
```
ctx:{tenant_id}:qoe:session:{id}      TTL: 1800s
ctx:{tenant_id}:qoe:active_anomalies  TTL: 120s
```

## 9. TEST
```bash
pytest apps/viewer_experience/tests/ -v --cov=apps/viewer_experience --cov-fail-under=80
```
Senaryolar: QoE anomaly (buffering>5% → event) | Complaint NLP | MATCH_DAY (yüksek concurrent)

---
## Sprint Completion — S05
- Date: Mart 2026
- Tests: 37 passed, 95% coverage
- ruff: clean
- Status: ✅ Complete
- Commit: 0fa4163

### Files Created
- apps/viewer_experience/config.py — ViewerExperienceConfig (QoE thresholds, dedup window, scoring weights)
- apps/viewer_experience/schemas.py — QoESession, QoEMetrics, QoEAnomaly, Complaint, ComplaintAnalysis
- apps/viewer_experience/prompts.py — system + QoE analysis + complaint NLP + escalation prompts
- apps/viewer_experience/tools.py — 10 tools (LOW/MEDIUM/HIGH risk)
  - score_qoe_session, get_session_context, detect_qoe_anomaly, search_similar_issues,
    categorize_complaint, find_related_complaints (LOW)
  - write_qoe_metrics, write_complaint, trigger_qoe_alert (MEDIUM)
  - escalate_complaint (HIGH — approval_required)
- apps/viewer_experience/agent.py — QoEAgent + ComplaintAgent (both extend BaseAgent)
  - QoEAgent: Sonnet for anomaly analysis, Haiku for batch session scoring
  - ComplaintAgent: Sonnet for NLP categorization + sentiment + priority
  - QoE formula: exact match to spec Section 4 (0.0–5.0 scale)
  - Session dedup: 5 min window via Redis
- backend/routers/viewer_experience.py — /viewer prefix, all endpoints + WebSocket /ws/viewer/qoe
- apps/viewer_experience/tests/test_tools.py — 22 tests
- apps/viewer_experience/tests/test_agent.py — 15 tests

### Cross-App Wired
- Subscribes: analysis_complete ← log_analyzer
             live_event_starting ← live_intelligence
- Publishes: qoe_degradation → ops_center, alert_center
- DuckDB reads: shared_analytics.cdn_analysis, live_events
- DuckDB writes: shared_analytics.qoe_metrics, agent_decisions
- ChromaDB: similar complaints searched before categorization

### Hard Constraints Verified
- QoE score formula exact match to spec ✅ (8 formula tests)
- score < 2.5 → qoe_degradation published ✅
- Session dedup 5 min window ✅
- escalate_complaint → approval_required ✅
- NLP: category + sentiment + priority on every complaint ✅
- ChromaDB similarity search wired ✅

### Deviations
- None
