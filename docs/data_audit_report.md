# DuckDB Data Audit Report
Generated: 2026-03-29 07:55:53 UTC

## 1. logs.duckdb — Table Structure

Total tables: 15

| Schema | Table |
|---|---|
| aaop_company | api_logs_logs |
| aaop_company | app_reviews_logs |
| aaop_company | billing_logs |
| aaop_company | crm_subscriber_logs |
| aaop_company | epg_logs |
| aaop_company | fairplay_drm_logs |
| aaop_company | medianova_logs |
| aaop_company | newrelic_apm_logs |
| aaop_company | npaw_analytics_logs |
| aaop_company | origin_server_logs |
| aaop_company | player_events_logs |
| aaop_company | push_notifications_logs |
| aaop_company | widevine_drm_logs |
| test_import_tenant | billing_logs |
| test_sync_tenant | app_reviews_logs |

## 2. Coverage Summary (aaop_company)

| Source | Rows | Min Date | Max Date | Day Span | Distinct Days | Avg Rows/Day |
|---|---|---|---|---|---|---|
| api_logs_logs | 8,098,799 | 2026-03-04 | 2026-03-31 | 27 | 18 | 299,956 |
| app_reviews_logs | 1,016 | 2026-03-04 | 2026-03-31 | 27 | 18 | 38 |
| billing_logs | 84,980 | 2026-03-04 | 2026-03-31 | 27 | 18 | 3,147 |
| crm_subscriber_logs | 552,900 | — | — | 0 | 0 | 0 |
| epg_logs | 4,423 | 2026-01-02 | 2026-03-31 | 88 | 19 | 50 |
| fairplay_drm_logs | 1,571,012 | 2026-03-04 | 2026-04-01 | 28 | 20 | 56,108 |
| medianova_logs | 0 | — | — | 0 | 0 | 0 |
| newrelic_apm_logs | 723,450 | 2026-03-04 | 2026-03-31 | 27 | 18 | 26,794 |
| npaw_analytics_logs | 1,443,792 | 2026-03-04 | 2026-04-01 | 28 | 20 | 51,564 |
| origin_server_logs | 858,798 | 2026-03-04 | 2026-03-31 | 27 | 18 | 31,807 |
| player_events_logs | 29,246,498 | 2026-03-04 | 2026-04-01 | 28 | 20 | 1,044,518 |
| push_notifications_logs | 141,594 | 2026-03-04 | 2026-03-31 | 27 | 18 | 5,244 |
| widevine_drm_logs | 2,923,401 | 2026-03-04 | 2026-04-01 | 28 | 20 | 104,407 |

**Toplam satır:** 45,650,663

## 3. Gap Analysis (Eksik Günler)

### api_logs_logs
Missing days (10):
- 2026-03-05
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### app_reviews_logs
Missing days (10):
- 2026-03-05
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### billing_logs
Missing days (10):
- 2026-03-05
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### epg_logs
Missing days (70):
- 2026-01-03
- 2026-01-04
- 2026-01-05
- 2026-01-06
- 2026-01-07
- 2026-01-08
- 2026-01-09
- 2026-01-10
- 2026-01-11
- 2026-01-12
- ... ve 60 gün daha

### fairplay_drm_logs
Missing days (9):
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### newrelic_apm_logs
Missing days (10):
- 2026-03-05
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### npaw_analytics_logs
Missing days (9):
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### origin_server_logs
Missing days (10):
- 2026-03-05
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### player_events_logs
Missing days (9):
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### push_notifications_logs
Missing days (10):
- 2026-03-05
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

### widevine_drm_logs
Missing days (9):
- 2026-03-06
- 2026-03-07
- 2026-03-08
- 2026-03-09
- 2026-03-10
- 2026-03-11
- 2026-03-12
- 2026-03-13
- 2026-03-14

## 4. Daily Volume Statistics (Son 7 Gün)

**api_logs_logs:**
  2026-03-31: 101,988 rows
  2026-03-30: 101,988 rows
  2026-03-29: 101,988 rows
  2026-03-28: 449,995 rows
  2026-03-27: 279,987 rows
  2026-03-26: 279,987 rows
  2026-03-25: 279,987 rows

**app_reviews_logs:**
  2026-03-31: 9 rows
  2026-03-30: 8 rows
  2026-03-29: 10 rows
  2026-03-28: 21 rows
  2026-03-27: 20 rows
  2026-03-26: 28 rows
  2026-03-25: 18 rows

**billing_logs:**
  2026-03-31: 1,464 rows
  2026-03-30: 1,464 rows
  2026-03-29: 1,453 rows
  2026-03-28: 1,460 rows
  2026-03-27: 1,455 rows
  2026-03-26: 1,467 rows
  2026-03-25: 1,436 rows

**epg_logs:**
  2026-03-31: 234 rows
  2026-03-30: 237 rows
  2026-03-29: 232 rows
  2026-03-28: 233 rows
  2026-03-27: 225 rows
  2026-03-26: 236 rows
  2026-03-25: 227 rows

## 5. analytics.duckdb — Table Summary

| Schema | Table | Rows |
|---|---|---|
| main | fetch_job_history | 20 |
| main | log_fetch_cache | 4 |
| shared_analytics | agent_decisions | 50 |
| shared_analytics | alerts_sent | 0 |
| shared_analytics | capacity_metrics | 168 |
| shared_analytics | cdn_analysis | 0 |
| shared_analytics | experiments | 10 |
| shared_analytics | incidents | 50 |
| shared_analytics | live_events | 15 |
| shared_analytics | model_registry | 8 |
| shared_analytics | qoe_metrics | 200 |
| shared_analytics | retention_scores | 100 |
| shared_analytics | token_usage | 200 |

## 6. Issues Found

- **medianova_logs**: Hiç veri yok
