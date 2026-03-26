# mock_data_gen_spec.md — Mock Data Generator
> Kapsam: 13 log kaynağı, 91 gün (01.01–31.03.2026), S Sport Plus tenant
> Konum: apps/mock_data_gen/ | Veri çıktısı: aaop-mock-data/ (gitignore)
> Versiyon: 1.0 | Mart 2026 | Kritiklik: Development/Test

---

## 1. KULLANICI
Platform geliştirici — AAOP app'lerini (özellikle Log Analyzer, Viewer Experience,
Live Intelligence, Growth & Retention) gerçekçi OTT verisiyle test etmek için.

---

## 2. AMAÇ
- 11 AAOP app'i için korelasyonlu, deterministik mock data üretimi
- Takvim olaylarına (maç/kesinti/bayram) duyarlı spike/anomali üretimi
- Her log kaynağı için Log Analyzer sub-module ile uyumlu Pydantic schema
- Uygulama içinden tarih aralığı + kaynak seçerek on-demand üretim
- Schema browser: her kaynağın alan açıklamaları + kategori mapping UI

---

## 3. TENANT & PLATFORM PROFİLİ

```
tenant_id:           s_sport_plus
Servis bölgesi:      Türkiye (TR dominant %94)
Toplam abone:        485,000
  premium:           180,000 (%37)
  standard:          165,000 (%34)
  free:              140,000 (%29)
Dönem:               01.01.2026 — 31.03.2026 (91 gün)
Peak saatler:        20:00–23:00 TR (UTC+3) = 17:00–20:00 UTC
random.seed:         42 (deterministik — her run aynı çıktı)
```

### Coğrafya
```python
COUNTRY_DISTRIBUTION = {
    "TR": 0.94, "DE": 0.02, "CY": 0.015, "NL": 0.008, "OTHER": 0.007
}
TR_CITIES = {
    "İstanbul": 0.38, "Ankara": 0.14, "İzmir": 0.10, "Bursa": 0.05,
    "Antalya": 0.04, "Adana": 0.03, "Konya": 0.03, "Gaziantep": 0.02, "Diğer": 0.21
}
```

### Cihazlar
```python
DEVICE_DISTRIBUTION = {
    "android": 0.35, "ios": 0.22, "tizen_os": 0.14, "web_chrome": 0.08,
    "android_tv": 0.07, "webos": 0.06, "apple_tv": 0.04,
    "web_safari": 0.02, "web_firefox": 0.02
}
DRM_BY_DEVICE = {
    "android": "widevine", "android_tv": "widevine", "web_chrome": "widevine",
    "web_firefox": "widevine", "tizen_os": "widevine", "webos": "widevine",
    "ios": "fairplay", "apple_tv": "fairplay", "web_safari": "fairplay"
}
```

### Kanallar
```python
CHANNELS = {
    "s_sport_1":     {"display": "S Sport",   "type": "sport"},
    "s_sport_2":     {"display": "S Sport 2", "type": "sport"},
    "s_plus_live_1": {"display": "S+ Live 1", "type": "adhoc"},
    "s_plus_live_2": {"display": "S+ Live 2", "type": "adhoc"},
    "cnn_turk":      {"display": "CNN Türk",  "type": "news"},
    "trt_spor":      {"display": "TRT Spor",  "type": "sport"},
    "a_spor":        {"display": "A Spor",    "type": "sport"},
}
COMPETITIONS = {
    "football":    ["La Liga", "Serie A", "Bundesliga", "Türkiye Kupası"],
    "basketball":  ["EuroLeague", "NBA"],
    "ufc":         ["UFC"],
    "motorsport":  ["MotoGP"],
    "news":        ["breaking_news", "studio_show", "magazine"]
}
```

---

## 4. TAKVİM OLAYLARI (91 Gün)

| Tarih | Olay | Çarpan | Anomali |
|---|---|---|---|
| 05 Ocak | La Liga (Real Sociedad - Atletico) | x2.5 | — |
| 12 Ocak | EuroLeague (4 maç) | x1.8 | — |
| 19 Ocak | Serie A (Inter - Juventus) | x2.0 | — |
| 25 Ocak | UFC Fight Night | x1.8 | — |
| 04 Şubat | La Liga (Barcelona - Sevilla) | x2.5 | — |
| 11 Şubat | EuroLeague (6 maç) | x2.0 | — |
| 15 Şubat | MotoGP Portimao | x1.6 | — |
| 22 Şubat | Bundesliga (Bayern - Dortmund) | x2.8 | — |
| 28 Şubat 22:15-22:45 TR | CDN Kesintisi | — | cdn_outage |
| 01 Mart | Serie A (Milan - Napoli) | x2.2 | — |
| 04 Mart | ElClasico + UFC PPV | x10 | peak_event |
| 08 Mart | EuroLeague (8 maç) | x2.0 | — |
| 15 Mart | FairPlay Sertifika Sorunu | — | fairplay_cert_expired |
| 18 Mart | MotoGP Arjantin | x1.6 | — |
| 22 Mart | NBA (4 maç) | x1.5 | — |
| 29-31 Mart | Ramazan Bayramı | x0.6 | holiday |

---

## 5. 13 LOG KAYNAĞI

| # | Kaynak | Format | Çıktı Yolu | Generator |
|---|---|---|---|---|
| 1 | Medianova CDN | JSONL.gz | medianova/YYYY/MM/DD/{channel}/{YYYY-MM-DD-HH-MM}.jsonl.gz | medianova/generator.py |
| 2 | Origin Server | JSONL.gz | origin_logs/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz | origin_logs/generator.py |
| 3 | Widevine DRM | JSONL.gz | drm_widevine/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz | drm_widevine/generator.py |
| 4 | FairPlay DRM | JSONL.gz | drm_fairplay/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz | drm_fairplay/generator.py |
| 5 | Player Events | JSONL.gz | player_events/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz | player_events/generator.py |
| 6 | NPAW Analytics | JSONL.gz | npaw/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz | npaw/generator.py |
| 7 | API Logs | JSONL.gz | api_logs/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz | api_logs/generator.py |
| 8 | New Relic APM | JSONL.gz | newrelic/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz | newrelic/generator.py |
| 9 | CRM/Subscriber | CSV+JSONL.gz | crm/subscribers_base.csv + crm/daily_updates/... | crm/generator.py |
| 10 | EPG | JSON | epg/YYYY/MM/DD/{YYYY-MM-DD}.json | epg/generator.py |
| 11 | Billing | JSONL.gz | billing/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz | billing/generator.py |
| 12 | Push Notif. | JSONL.gz | push_notifications/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz | push_notifications/generator.py |
| 13 | App Reviews | JSON | app_reviews/YYYY/MM/{YYYY-MM-DD}.json | app_reviews/generator.py |

---

## 6. KRİTİK KORELASYONLAR

```
Medianova MISS        →  Origin cdn_miss (medianova_req_id eşleşmesi)
Player buffer events  →  NPAW rebuffering_ratio (±%5 tolerans)
Player session_end    →  NPAW qoe_score (±0.1 tolerans)
Billing failed        →  CRM churn_risk_score artışı (+0.10–0.30)
API /content/stream   →  Player session_start (request_id zinciri)
DRM license_request   →  Player session_start (session_id zinciri)
EPG expected_viewers  →  pre_scale_required (>50K → True)
CDN kesintisi (28 Şb) →  Medianova error spike + API 503 + Push system_alert
ElClasico (04 Mart)   →  Tüm kaynaklar x10 + App Review negatif spike
FairPlay (15 Mart)    →  Sadece ios/apple_tv/web_safari etkilenir
Bayram (29-31 Mart)   →  x0.6 trafik, mobile dominant, VOD ağırlıklı
```

---

## 7. KLASÖR YAPISI

```
apps/mock_data_gen/
├── mock_data_gen_spec.md       ← Bu dosya
├── __init__.py
├── run_all.py                  ← Tüm generator'ları sıralı çalıştırır
├── validate.py                 ← Korelasyon kontrolleri
├── requirements.txt
├── tests/
│   ├── __init__.py
│   ├── test_base_infra.py
│   ├── test_medianova.py
│   ├── test_origin.py
│   ├── test_drm.py
│   ├── test_player_events.py
│   ├── test_npaw.py
│   └── test_correlations.py
└── generators/
    ├── __init__.py
    ├── base_generator.py       ← BaseGenerator, sha256, user_agent, output util
    ├── calendar_events.py      ← 91 gün takvim, get_traffic_multiplier()
    ├── subscriber_pool.py      ← 485K abone, lazy load, memory-efficient
    ├── medianova/
    │   ├── __init__.py
    │   ├── schemas.py          ← MedianovaLogEntry (32 alan, 8 kategori)
    │   └── generator.py
    ├── origin_logs/
    │   ├── __init__.py
    │   ├── schemas.py          ← OriginLogEntry (4 event_type)
    │   └── generator.py
    ├── drm_widevine/
    │   ├── __init__.py
    │   ├── schemas.py          ← WidevineLogEntry (4 event_type)
    │   └── generator.py
    ├── drm_fairplay/
    │   ├── __init__.py
    │   ├── schemas.py          ← FairPlayLogEntry (certificate_status)
    │   └── generator.py
    ├── player_events/
    │   ├── __init__.py
    │   ├── schemas.py          ← PlayerEventEntry (7 event_type)
    │   └── generator.py
    ├── npaw/
    │   ├── __init__.py
    │   ├── schemas.py          ← NPAWSessionEntry (QoE agregat)
    │   └── generator.py
    ├── api_logs/
    │   ├── __init__.py
    │   ├── schemas.py          ← APILogEntry (6 endpoint)
    │   └── generator.py
    ├── newrelic/
    │   ├── __init__.py
    │   ├── schemas.py          ← NewRelicAPMEntry (3 event_type)
    │   └── generator.py
    ├── crm/
    │   ├── __init__.py
    │   ├── schemas.py          ← SubscriberProfile + SubscriberDailyDelta
    │   └── generator.py
    ├── epg/
    │   ├── __init__.py
    │   ├── schemas.py          ← EPGProgram
    │   └── generator.py
    ├── billing/
    │   ├── __init__.py
    │   ├── schemas.py          ← BillingLogEntry (8 event_type)
    │   └── generator.py
    ├── push_notifications/
    │   ├── __init__.py
    │   ├── schemas.py          ← PushNotificationEntry (10 notification_type)
    │   └── generator.py
    └── app_reviews/
        ├── __init__.py
        ├── schemas.py          ← AppReviewEntry
        └── generator.py
```

---

## 8. ÇALIŞTIRMA

```bash
cd /Users/fatihayaz/Documents/Projects/AAOP
source ~/.venvs/aaop/bin/activate

# Tüm kaynaklar — 91 gün
python -m apps.mock_data_gen.run_all

# Tek kaynak
python -m apps.mock_data_gen.generators.medianova.generator

# Belirli tarih aralığı
python -m apps.mock_data_gen.run_all --start 2026-03-04 --end 2026-03-04

# Belirli kaynaklar
python -m apps.mock_data_gen.run_all --sources medianova,drm_widevine,player_events

# Korelasyon doğrulama
python -m apps.mock_data_gen.validate

# Testler
pytest apps/mock_data_gen/tests/ -v --cov=apps/mock_data_gen
```

---

## 9. TEKNİK KURALLAR

```
random.seed(42)     → Deterministik — her run identical output
OUTPUT_ROOT         → /Users/fatihayaz/Documents/Projects/AAOP/aaop-mock-data/
Max dosya boyutu    → 50MB sıkıştırılmamış (aşarsa part-N ile böl)
PII kuralı          → remote_addr / device_id / user_id / email / phone → SHA256 hash
Python              → 3.12 (proje standardı)
Logging             → structlog (print yasak)
Test coverage       → ≥ 80%
```

---

## 10. UI (UYGULAMA İÇİ PANEL)

Mock data generator, AAOP frontend'inde iki panel olarak görünür:

### Panel A — Generator
- Kaynak seçici (checkboxlar: Medianova, Widevine, FairPlay, ...)
- Tarih aralığı picker (start / end)
- "Generate" butonu → progress bar
- Üretilen dosya listesi (kaynak / tarih / boyut)

### Panel B — Schema Browser
- Kaynak dropdown
- Alan tablosu: Field Name / Type / Kategori / Açıklama / Sample Value
- Kategori filtresi (Akamai DS2'deki gibi)
- Export Mappings JSON butonu

---

## 11. SPRINT PLANI

| Sprint | Kapsam | Durum |
|---|---|---|
| S-MDG-01 | base_generator + calendar + subscriber_pool | ✅ Tamamlandı |
| S-MDG-02 | Medianova + Origin generator | ✅ Tamamlandı |
| S-MDG-03 | Widevine + FairPlay generator | ✅ Tamamlandı |
| S-MDG-04 | Player Events + NPAW generator | ✅ Tamamlandı |
| S-MDG-05 | API Logs + New Relic generator | ✅ Tamamlandı |
| S-MDG-06 | CRM + EPG + Billing generator | ✅ Tamamlandı |
| S-MDG-07 | Push Notifications + App Reviews generator | ⏳ |
| S-MDG-08 | run_all.py + validate.py + Frontend UI | ⏳ |

---

## 12. ONAYLANAN SCHEMA'LAR

| # | Kaynak | Durum |
|---|---|---|
| 1 | Medianova CDN | ✅ Onaylandı |
| 2 | Origin Server | ✅ Onaylandı |
| 3 | Widevine DRM | ✅ Onaylandı |
| 4 | FairPlay DRM | ✅ Onaylandı |
| 5 | Player Events | ✅ Onaylandı |
| 6 | NPAW Analytics | ✅ Onaylandı |
| 7 | API Logs | ✅ Onaylandı |
| 8 | New Relic APM | ✅ Onaylandı |
| 9 | CRM/Subscriber | ✅ Onaylandı |
| 10 | EPG | ✅ Onaylandı |
| 11 | Billing | ✅ Onaylandı |
| 12 | Push Notifications | ✅ Onaylandı |
| 13 | App Reviews | ✅ Onaylandı |

---

## 13. GELECEK (Backlog)

- EPG: Harici EPG provider import (XML/JSON feed) → generator bypass
- Kanal genişletme: beIN Sports, DAZN entegrasyonu senaryoları
- Multi-tenant: Tivibu, D-Smart tenant profilleri
- S3 upload: Üretilen veriyi S3'e otomatik yükle (Akamai ile aynı bucket yapısı)
