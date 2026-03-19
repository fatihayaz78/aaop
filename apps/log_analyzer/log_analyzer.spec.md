# log_analyzer.spec.md — Log Analyzer
> Kapsam: M07 + Akamai sub-module + genişletilebilir log kaynakları | Sprint: S02 | Kritiklik: P0

## 1. KULLANICI
CDN Mühendisi, Platform Analist — Log analizi, anomali tespiti, rapor üretimi
Temel özellik: İstenen kadar log kaynağı eklenebilir (sub-module mimarisi)

## 2. TABS
| Tab | Açıklama | Veri |
|---|---|---|
| Overview | Aktif projeler, son analizler | DuckDB: cdn_analysis |
| Projects | Log projeleri CRUD | SQLite: log_projects |
| Akamai Analyzer | DataStream 2 analizi | S3 + DuckDB |
| Medianova | Placeholder | — |
| Add Source | Yeni log kaynağı ekle | SQLite: log_sources |
| Reports | DOCX rapor geçmişi + download | DuckDB + dosya sistemi |
| Agent Chat | Log Analyzer AI asistanı | LLM Gateway |

## 3. AGENT MİMARİSİ
```python
class LogAnalyzerAgent(BaseAgent):
    app_name = "log_analyzer"
    # Anomali/özet     → claude-sonnet-4-20250514
    # Batch processing → claude-haiku-4-5-20251001
    # Kritik CDN P0    → claude-opus-4-20250514
    # memory_update:
    #   DuckDB: cdn_analysis YAZ
    #   Event Bus: cdn_anomaly_detected (error_rate > threshold)
    #   Event Bus: analysis_complete (her başarılı analizde)
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| list_log_projects | LOW | auto |
| get_analysis_history | LOW | auto |
| search_similar_anomalies | LOW | auto |
| fetch_s3_logs | LOW | auto |
| parse_akamai_logs | LOW | auto |
| calculate_error_metrics | LOW | auto |
| detect_anomalies | LOW | auto |
| generate_charts | LOW | auto |
| write_analysis_to_db | MEDIUM | auto+notify |
| generate_docx_report | MEDIUM | auto+notify |
| trigger_cdn_alert | MEDIUM | auto+notify |
| purge_cdn_cache | HIGH | approval_required |

## 5. KLASÖR YAPISI
```
apps/log_analyzer/
├── log_analyzer.spec.md
├── agent.py
├── tools.py / schemas.py / prompts.py / config.py
└── sub_modules/
    ├── __init__.py          ← SubModuleRegistry: {"akamai": ..., "medianova": ...}
    ├── base_sub_module.py   ← BaseSubModule (configure/fetch_logs/analyze/generate_report)
    ├── akamai/
    │   ├── parser.py        ← DataStream 2 CSV (21 alan)
    │   ├── scheduler.py     ← AsyncIOScheduler, her 6 saatte S3 fetch
    │   ├── analyzer.py      ← Anomali tespiti, error rate
    │   ├── charts.py        ← 21 Plotly grafik — kaleido==0.2.1 (PIN'Lİ)
    │   ├── reporter.py      ← python-docx DOCX rapor
    │   └── schemas.py
    └── medianova/
        └── __init__.py      ← Stub placeholder
```

## 6. AKAMAI — 21 GRAFİK LİSTESİ
```
1. Error Rate zaman serisi    8. Coğrafi dağılım          15. Origin vs Edge ratio
2. Cache Hit Rate             9. TLS version dağılımı     16. Request size dağılımı
3. Byte transfer volume       10. Protocol dağılımı        17. Response size dağılımı
4. Request volume             11. Top 20 error path        18. Error rate by edge
5. TTFB histogram             12. Cache status breakdown   19. TTFB trend (7d avg)
6. HTTP status code pie       13. Bandwidth vs error       20. Request rate by content type
7. Top 10 edge server         14. Peak hour heatmap        21. Anomaly timeline
```

## 7. DOCX RAPOR YAPISI
```
Kapak | Yönetici Özeti (LLM-TR) | Temel Metrikler Tablosu |
Anomali Bulguları | Grafik Galerisi (21 grafik) |
Öneri Maddeleri (LLM) | Teknik Detaylar
```

## 8. SUB-MODULE EXTENSION PATTERN
```python
class YeniKaynakSubModule(BaseSubModule):
    name = "yeni_kaynak"
    display_name = "Yeni Kaynak Analyzer"

    async def configure(self, config: dict) -> None: ...
    async def fetch_logs(self, params) -> list[LogEntry]: ...
    async def analyze(self, logs) -> AnalysisResult: ...
    async def generate_report(self, result) -> str: ...  # dosya yolu

# Kayıt: sub_modules/__init__.py → REGISTRY'e ekle → otomatik UI'da görünür
```

## 9. API
```
prefix: /log-analyzer
ref:    API_CONTRACTS.md → Bölüm 4
```

## 10. CROSS-APP
```
OUTPUT (publish):
  cdn_anomaly_detected → ops_center, alert_center
  analysis_complete    → growth_retention, viewer_experience

INPUT (subscribe):
  live_event_starting  ← live_intelligence (yoğun analiz modu)

DuckDB YAZMA: shared_analytics.cdn_analysis, agent_decisions
DuckDB OKUMA: shared_analytics.live_events
```

## 11. LOKAL VERİ
### SQLite
```sql
CREATE TABLE log_projects (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    name TEXT NOT NULL, sub_module TEXT NOT NULL,
    config_json TEXT, is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE log_sources (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
    source_type TEXT NOT NULL, config_json TEXT,
    last_fetch TEXT, status TEXT DEFAULT 'idle'
);
```
### Redis
```
ctx:{tenant_id}:cdn:latest_analysis   TTL: 300s
ctx:{tenant_id}:cdn:active_anomalies  TTL: 120s
log:job:{job_id}:status               TTL: 3600s
```

## 12. KRİTİK NOTLAR
```
kaleido==0.2.1  → PIN'Lİ — asla 1.x yükseltme (Chrome bağımlılığı)
APScheduler     → AsyncIOScheduler (sync değil)
S3 credentials  → .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET
Log cache       → data/logs/ (haftalık temizle)
DOCX raporlar   → data/reports/{tenant_id}/
```
