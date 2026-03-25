"""Seed data for Knowledge Base — comprehensive platform documentation."""
from __future__ import annotations
import structlog

logger = structlog.get_logger(__name__)

# ══════════ COLLECTION 1: incidents ══════════

INCIDENT_DOCS = [
    {"id": "inc-001", "title": "CDN Edge Failure Playbook", "content": "When CDN edge node fails: 1. Check BGP routes 2. Verify failover 3. Monitor cache hit ratio. Typical MTTR: 5 minutes."},
    {"id": "inc-002", "title": "DRM License Timeout Resolution", "content": "DRM timeout caused by connection pool exhaustion. Restart license server pods. Check Widevine key rotation schedule."},
    {"id": "inc-003", "title": "HLS 503 Spike Runbook", "content": "503 on HLS manifests indicates origin overload. Enable auto-scale, check origin CPU, verify CDN shield configuration."},
    {"id": "inc-004", "title": "Buffering Anomaly Investigation", "content": "High buffering ratio (>3%) investigation: Check CDN edge server load, ISP peering, client device capabilities."},
    {"id": "inc-005", "title": "Origin Overload Recovery", "content": "Origin overload: Scale horizontally, enable CDN shield caching, reduce origin fetch frequency. Monitor 5xx rate."},
    {"id": "inc-006", "title": "API Gateway 502 Troubleshooting", "content": "502 from API gateway: Check upstream health, connection pool, SSL certificate validity, DNS resolution."},
    {"id": "inc-007", "title": "Player SDK Crash Analysis", "content": "Analyze crash dumps, check DRM module compatibility, verify adaptive bitrate ladder configuration."},
    {"id": "inc-008", "title": "Authentication Service Latency", "content": "Auth latency >2s: Check Redis session store, JWT validation overhead, LDAP connection pool."},
    {"id": "inc-009", "title": "Multi-CDN Failover Procedure", "content": "When primary CDN degrades: 1. Verify health checks 2. Shift traffic via DNS 3. Monitor QoE during transition."},
    {"id": "inc-010", "title": "Transcoder Queue Backlog", "content": "Queue backlog recovery: Scale encoder instances, prioritize live over VOD, clear stale jobs."},
    {"id": "inc-011", "title": "Akamai DS2 Field Reference — 22 Fields",
     "content": "Complete field reference for DataStream 2 TSV log format. META: version (idx 0), cpCode (idx 1). TIMING: reqTimeSec (idx 2, unix epoch float), dnsLookupTimeMSec (idx 14), transferTimeMSec (idx 15, ms), turnAroundTimeMSec (idx 16, ms). BANDWIDTH: bytes (idx 3, actual transferred — USE THIS for bandwidth), clientBytes (idx 4), responseBodySize (idx 6, origin size — NOT for bandwidth). CONTENT: contentType (idx 5), reqPath (idx 9). CLIENT: userAgentHash (idx 7, SHA256 hashed), hostname (idx 8), clientIpHash (idx 11, SHA256 hashed), reqRange (idx 12). RESPONSE: statusCode (idx 10), errorCode (idx 17). CACHE: cacheHit (idx 18, binary 0/1 — USE THIS for cache hit rate), cacheStatus (idx 13, Akamai internal code — secondary). NETWORK: edgeIp (idx 19). GEO: country (idx 20, ISO 3166-1), city (idx 21). PII NOTE: clientIp and userAgent are PLAIN TEXT in raw logs — must hash with SHA256 before storage."},
    {"id": "inc-012", "title": "Akamai DS2 — Correct Metric Calculations",
     "content": "Verified calculations from real S Sport Plus data (14,930 rows, 16-17 Mar 2026). Bandwidth: sum(bytes field idx 3) / 1e9 — NOT responseBodySize. Cache Hit Rate: sum(cacheHit==1) / total * 100 — NOT cacheStatus==1. Correct: ~66.7% (NOT 55.8%). Error Rate: count(system errors only) / total * 100. SYSTEM: ERR_FIRST_BYTE_TIMEOUT, ERR_ZERO_SIZE_OBJECT, ERR_HTTP2_WIN_UPDATE_TIMEOUT. CLIENT ABORT (exclude): ERR_CLIENT_ABORT — user behavior. ACCESS DENIED (separate): ERR_ACCESS_DENIED — security. Correct: ~2.2% (NOT 7.7%). Transfer Time: mean(transferTimeMSec idx 15) / 1000 — correct ~0.36s (NOT 2.2s). Unique IPs: len(set(clientIpHash)) — labeled Unique Client IPs (NOT subscribers). HTTPS %: NOT available in DS2 22-field stream. Bandwidth Savings: (sum(responseBodySize) - sum(bytes)) / sum(responseBodySize) * 100."},
    {"id": "inc-013", "title": "Akamai DS2 — Available But Not Configured Fields",
     "content": "Fields that exist in Akamai DS2 but are NOT in our current 22-field stream. Can be added in Akamai Control Center: proto (HTTP/1.1, HTTP/2, QUIC → HTTPS %), reqMethod (GET/POST → method analysis), tlsVersion (TLSv1.3/QUIC → security), lastByte (range detection), timeToFirstByte (TTFB for QoE), throughput (kbps bandwidth rate), reqEndTimeMSec (request read time). CP Code: 60890. S3 bucket: ssport-datastream (eu-central-1). Path: logs/{cp_code}/{year}/{DD}/{MM}/{HH}/"},
    {"id": "inc-014", "title": "Akamai DS2 — Error Code Reference",
     "content": "ErrorCode field (idx 17) taxonomy. Format: ERR_TYPE|sub_reason. SYSTEM ERRORS (count toward error rate): ERR_FIRST_BYTE_TIMEOUT|before_resp_hdrs (origin not responding), ERR_ZERO_SIZE_OBJECT|httpReadReply (empty response), ERR_HTTP2_WIN_UPDATE_TIMEOUT (HTTP/2 flow control), ERR_DNS_FAIL (DNS resolution). CLIENT BEHAVIOR (exclude from error rate): ERR_CLIENT_ABORT|stream:cancel (user changed channel), ERR_CLIENT_ABORT|general (client disconnect). SECURITY (separate metric): ERR_ACCESS_DENIED|SHORT_TOKEN_INVALID (expired auth), ERR_ACCESS_DENIED|ptk_geo-blocking (geo restriction), ERR_ACCESS_DENIED|fwd_acl (ACL block). Real data S Sport Plus (14,930 rows): SHORT_TOKEN_INVALID 131 (0.88%), stream:cancel 67 (0.45%), before_resp_hdrs 49 (0.33%), ZERO_SIZE_OBJECT 9 (0.06%)."},
]

# ══════════ COLLECTION 2: runbooks ══════════

RUNBOOK_DOCS = [
    {"id": "rb-001", "title": "Pre-Scale Checklist", "content": "1. Verify expected viewer count 2. Scale CDN edge capacity 3. Pre-warm cache 4. Alert NOC team 5. Enable DRM license pre-fetch"},
    {"id": "rb-002", "title": "Akamai Purge Procedure", "content": "1. Identify affected CP codes 2. Submit purge via API 3. Verify propagation 4. Confirm cache miss rate returns to normal"},
    {"id": "rb-003", "title": "P0 Incident Response", "content": "1. Acknowledge in 2 min 2. Assemble war room 3. Identify blast radius 4. Execute remediation 5. Post-mortem within 24h"},
    {"id": "rb-004", "title": "DRM Fallback Activation", "content": "1. Detect DRM failure 2. Switch to backup license server 3. Verify key delivery 4. Monitor player errors"},
    {"id": "rb-005", "title": "CDN Token Auth Debug", "content": "1. Check token expiry config 2. Verify edge server clock sync 3. Test token generation 4. Check CDN config propagation"},
    {"id": "rb-006", "title": "QoE Threshold Calibration", "content": "1. Review 7-day QoE distribution 2. Adjust z-score threshold 3. Validate with historical data 4. Deploy updated config"},
    {"id": "rb-007", "title": "SSL Certificate Rotation", "content": "1. Generate new cert 2. Deploy to staging 3. Verify chain 4. Rolling deploy to production edges"},
    {"id": "rb-008", "title": "Database Failover Procedure", "content": "1. Detect primary failure 2. Promote replica 3. Update DNS 4. Verify application connectivity"},
    {"id": "rb-009", "title": "Log Analyzer — Metric Interpretation Guide",
     "content": "How to read AAOP Log Analyzer dashboard. Total GB: sum of bytes field / 1e9 (actual transferred, not origin size). Cache Hit: percentage of requests with cacheHit=1 (binary flag). Error Rate: counts ONLY system errors (ERR_FIRST_BYTE_TIMEOUT etc.), NOT client aborts. Avg Latency: mean of transferTimeMSec field. Countries: distinct country codes. Anomaly Timeline: z-score >2.5 on hourly avg latency flags anomalous hours. Bandwidth by Hour: shows all 24 UTC hours with 0-fill for missing data."},
    {"id": "rb-010", "title": "PII Handling in CDN Logs — AAOP Policy",
     "content": "client_ip and userAgent are plain text in Akamai DS2 raw logs. AAOP policy: SHA256 hash applied at parse time, before any storage. Hash: hashlib.sha256(value.encode()).hexdigest()[:16]. Stored as clientIpHash, userAgentHash. Never stored: raw IP addresses, raw User-Agent strings. All other 20 fields safe to store unmodified. Parser applies hash in parse_tsv() and _build_entry() functions."},
]

# ══════════ COLLECTION 3: platform ══════════

PLATFORM_DOCS = [
    {"id": "plt-001", "title": "AAOP Architecture Overview",
     "content": "AAOP (Captain logAR) is an 11-app AI-powered OTT observability platform. Stack: FastAPI backend (port 8000), Next.js 14 frontend (port 3000), Python 3.12. Data: SQLite (metadata), DuckDB (analytics), ChromaDB (vector search), Redis (cache). AI: LangGraph 4-step agent loop (Context→Reasoning→Tool Execution→Memory Update). LLM: 3-model routing (Haiku/Sonnet/Opus). Architecture: Adaptor pattern for future GCP migration (Spanner, BigQuery, Pub/Sub). Event Bus: asyncio.Queue with 9 cross-app event types."},
    {"id": "plt-002", "title": "AAOP — 11 Apps Module Guide",
     "content": "Ops Center (M01+M06): Incident detection + RCA, P0/P1→Opus, publishes incident_created/rca_completed. Log Analyzer (M07): Akamai DS2 ingestion, 13 charts, scheduled tasks, anomaly rules, Captain logAR chat. Alert Center (M13): Dedup (900s), storm detection (>10/5min), P0→Slack+PagerDuty, P3→Email. Viewer Experience (M02+M09): QoE scoring (0-5), complaint NLP, score<2.5 triggers alert. Live Intelligence (M05+M11): Pre-scale 30min before kickoff, DRM/SportRadar/EPG. Growth & Retention (M18+M03): Churn risk, NL→SQL, retention campaigns. Capacity & Cost (M16+M04): 70%/90% thresholds, 7d forecast, automation jobs. Admin & Governance (M12+M17): Tenant management, compliance checks, audit log, token usage. AI Lab (M10+M14): A/B experiments, model registry, governance. Knowledge Base (M15): Semantic search across incidents/runbooks/platform/akamai_ds2. DevOps Assistant (M08): Dangerous command detection, RAG from runbooks."},
    {"id": "plt-003", "title": "AAOP Event Bus — 9 Cross-App Events",
     "content": "cdn_anomaly_detected: log_analyzer → ops_center, alert_center. incident_created: ops_center → alert_center, knowledge_base. rca_completed: ops_center → knowledge_base, alert_center. qoe_degradation: viewer_experience → ops_center, alert_center. live_event_starting: live_intelligence → ops_center, log_analyzer, alert_center. external_data_updated: live_intelligence → ops_center, growth_retention. churn_risk_detected: growth_retention → alert_center. scale_recommendation: capacity_cost → ops_center, alert_center. analysis_complete: log_analyzer → growth_retention, viewer_experience."},
    {"id": "plt-004", "title": "AAOP API Quick Reference",
     "content": "106 endpoints across 11 apps. Prefixes: /ops (8), /log-analyzer (41), /alerts (11), /viewer (7), /live (7), /growth (6), /capacity (6), /admin (9), /ai-lab (7), /knowledge (6), /devops (5). Auth: JWT Bearer token via POST /auth/login. Tenant: X-Tenant-ID header required. WebSocket: /ws/ops/incidents, /ws/alerts/stream, /ws/viewer/qoe. Risk levels: LOW (auto), MEDIUM (auto+notify), HIGH (approval_required). Health: GET /health, GET /health/detailed, GET /{prefix}/health per app."},
    {"id": "plt-005", "title": "AAOP LLM Routing Strategy",
     "content": "3-model strategy: Haiku (claude-haiku-4-5-20251001) for batch processing, routing decisions, P3 events, admin ops — ~10x cheaper than Sonnet. Sonnet (claude-sonnet-4-20250514) for default, P2 events, chat, NL→SQL, analysis — balanced cost/quality. Opus (claude-opus-4-20250514) for P0/P1 incidents ONLY, RCA — highest quality, highest cost, justified by criticality. Cost: Haiku $0.25/$1.25 per 1M tokens, Sonnet $3/$15, Opus $15/$75. Monthly estimate for S Sport Plus: ~$2,400 (CDN $1,200, Encoding $600, Storage $300, API $200, Other $100)."},
]

# ══════════ COLLECTION 4: akamai_ds2 ══════════

AKAMAI_DS2_DOCS = [
    {"id": "ds2-001", "title": "DS2 Field Index — Complete 22-Field Reference",
     "content": "Akamai DataStream 2 TSV format, 22 tab-separated fields per line, no header row. Field 0: version (int, log format version). Field 1: cpCode (string, content provider code — S Sport Plus: 60890). Field 2: reqTimeSec (float, Unix epoch). Field 3: bytes (int, actual bytes transferred to client — USE FOR BANDWIDTH). Field 4: clientBytes (int, bytes from client request). Field 5: contentType (string, MIME type). Field 6: responseBodySize (int, origin object size — NOT for bandwidth calc). Field 7: userAgent (string, PLAIN TEXT — MUST SHA256 HASH). Field 8: hostname (string, requested hostname). Field 9: reqPath (string, URL path). Field 10: statusCode (int, HTTP response code). Field 11: clientIp (string, PLAIN TEXT — MUST SHA256 HASH). Field 12: reqRange (string, HTTP Range header). Field 13: cacheStatus (int, Akamai internal cache code). Field 14: dnsLookupTimeMSec (int, DNS resolution ms). Field 15: transferTimeMSec (int, transfer duration ms). Field 16: turnAroundTimeMSec (int, edge turnaround ms). Field 17: errorCode (string, pipe-separated ERR_TYPE|reason). Field 18: cacheHit (int, binary 0/1 — USE FOR CACHE HIT RATE). Field 19: edgeIp (string, Akamai edge server IP). Field 20: country (string, ISO 3166-1 alpha-2). Field 21: city (string, city name)."},
    {"id": "ds2-002", "title": "DS2 Cache Status Codes",
     "content": "cacheStatus field (idx 13) Akamai internal codes: 0=TCP_MISS (cache miss, fetched from origin), 1=TCP_HIT (served from cache), 2=TCP_IMS_HIT (revalidated, still fresh), 3=TCP_STALE_HIT (served stale while revalidating), 4=TCP_SYNTHETIC (generated by edge), 5=TCP_BW_OPTIMIZED (bandwidth optimized), 6=TCP_PREFETCH (prefetched), 7=TCP_REMOTE_HIT (from peer cache), 8=TCP_SURE_HIT (certain cache hit), 9=TCP_NON_CACHEABLE (not cacheable). IMPORTANT: For primary Cache Hit Rate KPI, use cacheHit field (idx 18) binary 0/1, NOT cacheStatus. cacheStatus is useful for detailed cache behavior analysis only."},
    {"id": "ds2-003", "title": "DS2 Error Code Taxonomy",
     "content": "errorCode field (idx 17) format: ERR_TYPE|sub_reason (pipe-separated). SYSTEM ERRORS (platform issues, count toward error rate): ERR_FIRST_BYTE_TIMEOUT|before_resp_hdrs (origin timeout), ERR_ZERO_SIZE_OBJECT|httpReadReply (empty response), ERR_HTTP2_WIN_UPDATE_TIMEOUT (H2 flow control), ERR_DNS_FAIL (DNS failure), ERR_CONNECT_FAIL (connection failure). CLIENT BEHAVIOR (normal, EXCLUDE from error rate): ERR_CLIENT_ABORT|stream:cancel (user action), ERR_CLIENT_ABORT|general (client disconnect). SECURITY (separate metric): ERR_ACCESS_DENIED|SHORT_TOKEN_INVALID (expired token), ERR_ACCESS_DENIED|ptk_geo-blocking (geo block), ERR_ACCESS_DENIED|fwd_acl (ACL block)."},
    {"id": "ds2-004", "title": "DS2 Content Type Analysis",
     "content": "Common contentType values in S Sport Plus DS2 logs: video/mp4 (HLS/DASH video segments, .m4s files — majority of bandwidth), application/x-mpegURL (HLS manifests, .m3u8 — small but frequent), application/dash+xml (DASH manifests, .mpd), image/jpeg and image/png (thumbnails, posters), application/json (API responses), text/html (error pages). Segment type detection from reqPath: .m4s → video segment, .m3u8 → HLS manifest, .mpd → DASH manifest, other → asset/static."},
    {"id": "ds2-005", "title": "DS2 Geo Data — S Sport Plus Distribution",
     "content": "country field (idx 20, ISO 3166-1 alpha-2). Primary market: TR (Turkey, ~85-92% of traffic). Secondary: DE (Germany, Turkish diaspora ~3%), NL (Netherlands ~2%), GB (UK ~1%), US (~1%), AE (UAE ~1%). city field (idx 21): Top cities Istanbul (~40%), Ankara (~15%), Izmir (~8%), Bursa (~4%), Antalya (~3%). Note: Geo accuracy depends on Akamai's IP geolocation database. VPN users may show incorrect country."},
    {"id": "ds2-006", "title": "DS2 Performance Metrics Interpretation",
     "content": "transferTimeMSec (idx 15): Total transfer duration in milliseconds. Normal range: 50-500ms for cached content, 200-2000ms for origin fetches. High values (>2000ms) indicate origin latency or network congestion. turnAroundTimeMSec (idx 16): Time between edge receiving request and first byte from origin. Normal: 10-100ms for cache hits, 100-500ms for origin. dnsLookupTimeMSec (idx 14): DNS resolution time. Normal: <10ms (cached), 50-200ms (cold lookup). Avg transfer for S Sport Plus: ~360ms (normal traffic), spikes during live events to 800-1200ms."},
    {"id": "ds2-007", "title": "DS2 PII Fields and Hashing Policy",
     "content": "CRITICAL: Two fields contain personally identifiable information (PII). Field 7 (userAgent): Contains full browser/device User-Agent string. Field 11 (clientIp): Contains real client IP address. AAOP Policy: SHA256 hash applied at parse time, BEFORE any storage (DuckDB, SQLite, Redis, logs). Hash function: hashlib.sha256(value.encode()).hexdigest()[:16] (first 16 chars). Stored field names: client_ip (hashed), user_agent (hashed). Raw values exist ONLY in memory during current parse iteration. All other 20 fields are safe to store unmodified."},
    {"id": "ds2-008", "title": "DS2 Available But Unconfigured Fields",
     "content": "Akamai DS2 supports 100+ fields. Our stream uses 22. Fields available to add via Akamai Control Center (no code change needed): proto (HTTP/1.1, HTTP/2, HTTP/3 → enables real HTTPS % metric), reqMethod (GET/POST/PUT → method analysis), tlsVersion (TLSv1.2, TLSv1.3, QUIC → security audit), lastByte (0/1 → range request detection), timeToFirstByte (ms → true TTFB metric for QoE), throughput (kbps → real-time bandwidth rate), reqEndTimeMSec (ms → request read time), objectSize (bytes → original object size before compression). To add: Akamai Control Center → DataStream 2 → Stream Config → Edit Fields."},
]

_ALL_DOCS = {
    "incidents": INCIDENT_DOCS,
    "runbooks": RUNBOOK_DOCS,
    "platform": PLATFORM_DOCS,
    "akamai_ds2": AKAMAI_DS2_DOCS,
}


def get_all_docs() -> dict[str, list[dict]]:
    return _ALL_DOCS


def search_docs(query: str, collection: str | None = None, limit: int = 5) -> list[dict]:
    """Simple text search across documents."""
    q_lower = query.lower()
    results = []
    collections = [collection] if collection and collection != "all" else list(_ALL_DOCS.keys())
    for coll in collections:
        for doc in _ALL_DOCS.get(coll, []):
            score = 0
            for word in q_lower.split():
                if len(word) < 2:
                    continue
                if word in doc["title"].lower():
                    score += 3
                if word in doc["content"].lower():
                    score += 1
            if score > 0:
                results.append({**doc, "collection": coll, "score": score, "content_preview": doc["content"][:150]})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
