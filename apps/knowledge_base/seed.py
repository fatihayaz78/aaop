"""Seed mock data for Knowledge Base — ChromaDB collections."""
from __future__ import annotations
import structlog

logger = structlog.get_logger(__name__)

# Mock documents — stored in-memory since ChromaDB may not be available
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
]

RUNBOOK_DOCS = [
    {"id": "rb-001", "title": "Pre-Scale Checklist", "content": "1. Verify expected viewer count 2. Scale CDN edge capacity 3. Pre-warm cache 4. Alert NOC team 5. Enable DRM license pre-fetch"},
    {"id": "rb-002", "title": "Akamai Purge Procedure", "content": "1. Identify affected CP codes 2. Submit purge via API 3. Verify propagation 4. Confirm cache miss rate returns to normal"},
    {"id": "rb-003", "title": "P0 Incident Response", "content": "1. Acknowledge in 2 min 2. Assemble war room 3. Identify blast radius 4. Execute remediation 5. Post-mortem within 24h"},
    {"id": "rb-004", "title": "DRM Fallback Activation", "content": "1. Detect DRM failure 2. Switch to backup license server 3. Verify key delivery 4. Monitor player errors"},
    {"id": "rb-005", "title": "CDN Token Auth Debug", "content": "1. Check token expiry config 2. Verify edge server clock sync 3. Test token generation 4. Check CDN config propagation"},
    {"id": "rb-006", "title": "QoE Threshold Calibration", "content": "1. Review 7-day QoE distribution 2. Adjust z-score threshold 3. Validate with historical data 4. Deploy updated config"},
    {"id": "rb-007", "title": "SSL Certificate Rotation", "content": "1. Generate new cert 2. Deploy to staging 3. Verify chain 4. Rolling deploy to production edges"},
    {"id": "rb-008", "title": "Database Failover Procedure", "content": "1. Detect primary failure 2. Promote replica 3. Update DNS 4. Verify application connectivity"},
]

PLATFORM_DOCS = [
    {"id": "plt-001", "title": "Architecture Overview", "content": "AAOP is an 11-app AI-powered OTT platform. FastAPI backend, Next.js frontend, DuckDB analytics, SQLite metadata, Redis cache, ChromaDB vector store."},
    {"id": "plt-002", "title": "API Reference Summary", "content": "11 app routers mounted on FastAPI. Auth via JWT. Tenant context via X-Tenant-ID header. All analytics in DuckDB shared_analytics schema."},
    {"id": "plt-003", "title": "Alert Routing Logic", "content": "P0→Slack+PagerDuty, P1→Slack, P2→Slack, P3→Email. Dedup 900s window. Storm detection >10 alerts/5min. Suppression via maintenance windows."},
    {"id": "plt-004", "title": "Agent Decision Framework", "content": "4-step agent loop: Context→Reasoning→Tool Execution→Memory Update. Risk levels: LOW(auto), MEDIUM(notify), HIGH(approval)."},
    {"id": "plt-005", "title": "Tenant Onboarding Guide", "content": "1. Create tenant in admin 2. Configure modules 3. Set API keys 4. Seed initial data 5. Verify health endpoints"},
]

_ALL_DOCS = {
    "incidents": INCIDENT_DOCS,
    "runbooks": RUNBOOK_DOCS,
    "platform": PLATFORM_DOCS,
}

def get_all_docs() -> dict[str, list[dict]]:
    return _ALL_DOCS

def search_docs(query: str, collection: str | None = None, limit: int = 5) -> list[dict]:
    """Simple text search across documents."""
    q_lower = query.lower()
    results = []
    collections = [collection] if collection else list(_ALL_DOCS.keys())
    for coll in collections:
        for doc in _ALL_DOCS.get(coll, []):
            score = 0
            for word in q_lower.split():
                if word in doc["title"].lower():
                    score += 2
                if word in doc["content"].lower():
                    score += 1
            if score > 0:
                results.append({**doc, "collection": coll, "score": score, "content_preview": doc["content"][:100]})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
