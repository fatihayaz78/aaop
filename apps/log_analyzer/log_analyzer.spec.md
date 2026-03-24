# log_analyzer.spec.md — Log Analyzer
> Kapsam: M07 + Akamai sub-module + genişletilebilir log kaynakları | Sprint: S02 | Kritiklik: P0

## 1. KULLANICI
CDN Mühendisi, Platform Analist — Log analizi, anomali tespiti, rapor üretimi
Temel özellik: İstenen kadar log kaynağı eklenebilir (sub-module mimarisi)

## 2. TABS
| Tab | Açıklama | Veri |
|---|---|---|
| Projects | Log projeleri CRUD, yeni proje oluşturma | SQLite: log_projects |
| Log Analyzer | Proje seçici + Akamai DataStream 2 sub-section, S3 fetch | S3 + DuckDB |
| Log Structure | S3 log örnekleme, field analizi, kategori mapping | S3 + SQLite: field_category_mappings |
| Settings | 3 accordion: Log Analyzer Settings / AWS Settings / GCP Settings | SQLite: settings |
| Analysis Results | Geçmiş analiz sonuçları tablosu | DuckDB: cdn_analysis |

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
    │   ├── analyzer.py      ← Korelasyon analizi, anomali tespiti (z-score, IQR)
    │   ├── bigquery_exporter.py ← 9 kategori BQ export
    │   ├── schemas.py       ← AkamaiLogEntry (22 DS2 alanı)
    │   ├── scheduler.py     ← AsyncIOScheduler, her 6 saatte S3 fetch
    │   ├── charts.py        ← 21 Plotly grafik — kaleido==0.2.1 (PIN'Lİ)
    │   └── reporter.py      ← python-docx DOCX rapor
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
CREATE TABLE settings (
    id TEXT PRIMARY KEY DEFAULT 'default',
    tenant_id TEXT NOT NULL,
    aws_access_key_id_enc TEXT,
    aws_secret_access_key_enc TEXT,
    s3_bucket TEXT DEFAULT 'ssport-datastream',
    s3_region TEXT DEFAULT 'eu-central-1',
    gcp_project_id TEXT,
    bq_dataset TEXT,
    gcp_credentials_enc TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE field_category_mappings (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(tenant_id, field_name)
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
encryption   → shared/utils/encryption.py — Fernet AES-256 (JWT_SECRET_KEY'den türetilir)
client_ip    → SHA256 hash (parser.py), asla LLM'e veya BigQuery'e gönderilmez
credentials  → SQLite settings tablosunda encrypted, response'da son 4 karakter masked
```

## 13. BIGQUERY KATEGORİ-ALAN EŞLEMESİ
| Kategori | Alanlar | PII Notu |
|---|---|---|
| meta | version, cp_code | — |
| timing | req_time_sec, dns_lookup_time_ms, transfer_time_ms, turn_around_time_ms | — |
| traffic | bytes, client_bytes, response_body_size | — |
| content | content_type, req_path | — |
| client | user_agent, req_range | client_ip EXCLUDED (PII) |
| network | hostname, edge_ip | — |
| response | status_code, error_code | — |
| cache | cache_status, cache_hit | — |
| geo | country, city | — |

## 14. SPRINT GEÇMİŞİ
### S15 — COMPLETE (commit: a54d0c0)
- AkamaiLogEntry 22 DS2 alanı (schemas.py)
- TSV parser + client_ip SHA256 hash (parser.py)
- 21 grafik — DS2 uyumlu, (figure, summary_df) tuple (charts.py)
- bigquery_exporter.py — 9 kategori export
- settings tablosu + Fernet encryption (shared/utils/encryption.py)
- 6 yeni endpoint: settings CRUD, fetch-range, bigquery export, test-connection
- Frontend: 5 tab (Projects/Akamai Analyzer/Analysis Results/Settings/BigQuery Export)
- Test: 451 passed, 0 failed

### S16-P1 — COMPLETE
- BUG FIX: POST /log-analyzer/projects 405 → POST handler eklendi
- BUG FIX: GET /log-analyzer/settings/test-connection 404 → route eklendi (s3 + bq)
- BUG FIX: POST /log-analyzer/bigquery/export GET→POST düzeltildi
- "Akamai Analyzer" tab → "Log Analyzer" olarak yeniden adlandırıldı
- Log Analyzer tab: proje seçici + Akamai DataStream 2 sub-section
- "BigQuery Export" tab kaldırıldı → Settings/GCP Settings altına taşındı
- Settings tab: 3 accordion (Log Analyzer Settings / AWS Settings / GCP Settings)
- frontend/src/components/ui/Accordion.tsx oluşturuldu
- Tests: 448 passed, 0 failed

### S16-P2 — COMPLETE
- POST /log-analyzer/structure/analyze — S3 örnekleme, field analizi, type inference
- POST /log-analyzer/structure/mappings — field→category upsert
- GET /log-analyzer/structure/mappings — tenant mapping listesi
- field_category_mappings SQLite tablosu eklendi
- _infer_type(): string/integer/float/timestamp/ip_hash/boolean
- Frontend: "Log Structure" tab — date picker, field analysis tablosu, category summary cards, Export Mappings JSON
- 13 yeni test (test_structure_analysis.py)
- Tests: 52 passed, 0 failed

### S16-P3 — COMPLETE
- S3 path yapısı düzeltildi: logs/{cp_code}/{year}/{DD}/{MM}/{HH}/
- Timezone fix: kullanıcı tarihi UTC+3, S3 path'leri UTC'ye çevrilir
- .gz dosya desteği: gzip.open() ile decompress
- cp_code: settings tablosuna eklendi, eksikse açık hata mesajı
- Frontend: "Akamai CP Code" input → Log Analyzer Settings accordion
- 5 yeni test (path generation, multi-day, gz parsing, cp_code validation)
- Tests: 57 passed, 0 failed
