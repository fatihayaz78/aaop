"""Pre-built query helpers for logs.duckdb — used by all P0 modules.

All functions use the LogsDuckDBClient directly for performance.
Every query filters by tenant_id. Returns sensible defaults on empty tables.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from shared.clients.logs_duckdb_client import LogsDuckDBClient

logger = structlog.get_logger(__name__)


def _get_logs_db() -> LogsDuckDBClient:
    """Get or create a LogsDuckDBClient singleton."""
    if not hasattr(_get_logs_db, "_instance"):
        _get_logs_db._instance = LogsDuckDBClient()
    return _get_logs_db._instance


def _safe_query(db: LogsDuckDBClient, tenant_id: str, sql: str) -> list[dict]:
    """Execute query, return [] on error."""
    try:
        return db.query(tenant_id, sql)
    except Exception as exc:
        logger.warning("log_query_error", sql=sql[:120], error=str(exc))
        return []


def _hours_ago(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


# ══════════════════════════════════════════════════════════════════════


def get_cdn_metrics(tenant_id: str, hours: int = 24) -> dict:
    """CDN metrics from medianova_logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.medianova_logs"
    since = _hours_ago(hours)

    total_row = _safe_query(db, tenant_id,
        f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    total = total_row[0]["cnt"] if total_row else 0
    if total == 0:
        return {"total_requests": 0, "error_rate_pct": 0, "cache_hit_rate_pct": 0,
                "avg_response_time_ms": 0, "bandwidth_gb": 0, "top_errors": [],
                "requests_by_hour": [], "status_code_distribution": {}}

    err_row = _safe_query(db, tenant_id,
        f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND status_code >= 400")
    errors = err_row[0]["cnt"] if err_row else 0

    cache_row = _safe_query(db, tenant_id,
        f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND cache_hit = 1")
    cache_hits = cache_row[0]["cnt"] if cache_row else 0

    agg = _safe_query(db, tenant_id,
        f"SELECT AVG(response_time_ms) as avg_rt, SUM(bytes_sent) as total_bytes FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    avg_rt = round(agg[0]["avg_rt"] or 0, 1) if agg else 0
    bw_gb = round((agg[0]["total_bytes"] or 0) / 1e9, 2) if agg else 0

    top_err = _safe_query(db, tenant_id,
        f"SELECT error_code, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND error_code IS NOT NULL GROUP BY error_code ORDER BY cnt DESC LIMIT 10")

    hourly = _safe_query(db, tenant_id,
        f"SELECT EXTRACT(HOUR FROM timestamp) as hr, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' GROUP BY hr ORDER BY hr")

    status_dist = _safe_query(db, tenant_id,
        f"SELECT status_code, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' GROUP BY status_code ORDER BY cnt DESC")

    return {
        "total_requests": total,
        "error_rate_pct": round(errors / total * 100, 2) if total else 0,
        "cache_hit_rate_pct": round(cache_hits / total * 100, 2) if total else 0,
        "avg_response_time_ms": avg_rt,
        "bandwidth_gb": bw_gb,
        "top_errors": [{"error_code": r["error_code"], "count": r["cnt"]} for r in top_err],
        "requests_by_hour": [{"hour": int(r["hr"]), "count": r["cnt"]} for r in hourly],
        "status_code_distribution": {str(r["status_code"]): r["cnt"] for r in status_dist},
    }


def get_cdn_anomalies(tenant_id: str, hours: int = 24) -> list[dict]:
    """Detect CDN anomalies: error_rate > 5% in 5-min windows."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.medianova_logs"
    since = _hours_ago(hours)

    rows = _safe_query(db, tenant_id, f"""
        SELECT time_bucket(INTERVAL '5 minutes', timestamp) as bucket,
               COUNT(*) as total,
               SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
        FROM {table}
        WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'
        GROUP BY bucket
        HAVING errors * 100.0 / total > 5
        ORDER BY bucket
    """)

    return [{"timestamp": str(r["bucket"]), "error_rate_pct": round(r["errors"] / r["total"] * 100, 1),
             "total_requests": r["total"]} for r in rows]


def get_drm_status(tenant_id: str, hours: int = 24) -> dict:
    """DRM status from widevine + fairplay logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    since = _hours_ago(hours)

    result = {"widevine": {"total": 0, "error_rate_pct": 0, "top_errors": []},
              "fairplay": {"total": 0, "error_rate_pct": 0, "top_errors": []},
              "affected_devices": []}

    for drm, tbl in [("widevine", f"{t}.widevine_drm_logs"), ("fairplay", f"{t}.fairplay_drm_logs")]:
        total_row = _safe_query(db, tenant_id,
            f"SELECT COUNT(*) as cnt FROM {tbl} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
        total = total_row[0]["cnt"] if total_row else 0

        err_row = _safe_query(db, tenant_id,
            f"SELECT COUNT(*) as cnt FROM {tbl} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND status != 'success'")
        errs = err_row[0]["cnt"] if err_row else 0

        top_err = _safe_query(db, tenant_id,
            f"SELECT error_code, COUNT(*) as cnt FROM {tbl} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND error_code IS NOT NULL GROUP BY error_code ORDER BY cnt DESC LIMIT 5")

        result[drm] = {
            "total": total,
            "error_rate_pct": round(errs / total * 100, 2) if total else 0,
            "top_errors": [{"error_code": r["error_code"], "count": r["cnt"]} for r in top_err],
        }

    # Affected devices
    dev_rows = _safe_query(db, tenant_id, f"""
        SELECT device_type, COUNT(*) as cnt FROM {t}.widevine_drm_logs
        WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND status != 'success'
        GROUP BY device_type ORDER BY cnt DESC LIMIT 10""")
    result["affected_devices"] = [{"device_type": r["device_type"], "error_count": r["cnt"]} for r in dev_rows]

    return result


def get_api_health(tenant_id: str, hours: int = 24) -> dict:
    """API gateway health from api_logs_logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.api_logs_logs"
    since = _hours_ago(hours)

    total_row = _safe_query(db, tenant_id,
        f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    total = total_row[0]["cnt"] if total_row else 0
    if total == 0:
        return {"total_requests": 0, "error_rate_pct": 0, "avg_response_time_ms": 0,
                "p99_response_time_ms": 0, "top_endpoints": [], "status_distribution": {}}

    err_row = _safe_query(db, tenant_id,
        f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND status_code >= 400")
    errors = err_row[0]["cnt"] if err_row else 0

    agg = _safe_query(db, tenant_id,
        f"SELECT AVG(response_time_ms) as avg_rt, PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99 FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    avg_rt = round(agg[0]["avg_rt"] or 0, 1) if agg else 0
    p99 = round(agg[0]["p99"] or 0, 1) if agg else 0

    top_ep = _safe_query(db, tenant_id, f"""
        SELECT endpoint, COUNT(*) as cnt,
               SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as err_rate
        FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'
        GROUP BY endpoint ORDER BY cnt DESC LIMIT 10""")

    status = _safe_query(db, tenant_id,
        f"SELECT status_code, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' GROUP BY status_code ORDER BY cnt DESC")

    return {
        "total_requests": total,
        "error_rate_pct": round(errors / total * 100, 2) if total else 0,
        "avg_response_time_ms": avg_rt,
        "p99_response_time_ms": p99,
        "top_endpoints": [{"endpoint": r["endpoint"], "count": r["cnt"], "error_rate": round(r["err_rate"], 1)} for r in top_ep],
        "status_distribution": {str(r["status_code"]): r["cnt"] for r in status},
    }


def get_infrastructure_health(tenant_id: str, hours: int = 24) -> dict:
    """Infrastructure health from newrelic_apm_logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.newrelic_apm_logs"
    since = _hours_ago(hours)

    rows = _safe_query(db, tenant_id, f"""
        SELECT service_name,
               AVG(apdex_score) as avg_apdex,
               AVG(error_rate) as avg_error_rate,
               AVG(throughput) as avg_throughput,
               AVG(cpu_pct) as avg_cpu,
               AVG(response_time_ms) as avg_mem
        FROM {table}
        WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND service_name IS NOT NULL
        GROUP BY service_name""")

    services = [{"service_name": r["service_name"],
                 "apdex_score": round(r["avg_apdex"] or 0, 3),
                 "error_rate": round(r["avg_error_rate"] or 0, 4),
                 "throughput": round(r["avg_throughput"] or 0, 0),
                 "cpu_pct": round(r["avg_cpu"] or 0, 1),
                 "memory_mb": round(r["avg_mem"] or 0, 1)} for r in rows]

    avg_apdex = round(sum(s["apdex_score"] for s in services) / max(1, len(services)), 3) if services else 0
    critical = [s["service_name"] for s in services if s["apdex_score"] < 0.7]

    return {"services": services, "avg_apdex": avg_apdex, "critical_services": critical}


def get_player_qoe(tenant_id: str, hours: int = 24) -> dict:
    """Player QoE from player_events_logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.player_events_logs"
    since = _hours_ago(hours)

    agg = _safe_query(db, tenant_id, f"""
        SELECT COUNT(DISTINCT session_id) as sessions,
               AVG(qoe_score) as avg_qoe,
               AVG(bitrate_kbps) as avg_br,
               AVG(buffer_ratio) as avg_buf
        FROM {table}
        WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'""")

    if not agg or not agg[0].get("sessions"):
        return {"avg_qoe_score": 0, "sessions_total": 0, "error_sessions_pct": 0,
                "avg_bitrate_kbps": 0, "avg_buffer_ratio": 0, "qoe_by_device": [], "qoe_by_hour": []}

    a = agg[0]
    err_row = _safe_query(db, tenant_id,
        f"SELECT COUNT(DISTINCT session_id) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND error_code IS NOT NULL")

    by_device = _safe_query(db, tenant_id, f"""
        SELECT device_type, AVG(qoe_score) as avg_qoe FROM {table}
        WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND device_type IS NOT NULL
        GROUP BY device_type ORDER BY avg_qoe""")

    by_hour = _safe_query(db, tenant_id, f"""
        SELECT EXTRACT(HOUR FROM timestamp) as hr, AVG(qoe_score) as avg_qoe FROM {table}
        WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'
        GROUP BY hr ORDER BY hr""")

    sessions = a["sessions"] or 0
    err_sessions = err_row[0]["cnt"] if err_row else 0

    return {
        "avg_qoe_score": round(a["avg_qoe"] or 0, 2),
        "sessions_total": sessions,
        "error_sessions_pct": round(err_sessions / sessions * 100, 1) if sessions else 0,
        "avg_bitrate_kbps": int(a["avg_br"] or 0),
        "avg_buffer_ratio": round(a["avg_buf"] or 0, 4),
        "qoe_by_device": [{"device_type": r["device_type"], "avg_qoe": round(r["avg_qoe"] or 0, 2)} for r in by_device],
        "qoe_by_hour": [{"hour": int(r["hr"]), "avg_qoe": round(r["avg_qoe"] or 0, 2)} for r in by_hour],
    }


def detect_incidents_from_logs(tenant_id: str, hours: int = 1) -> list[dict]:
    """Detect anomalies across multiple sources using threshold rules."""
    incidents: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    cdn = get_cdn_metrics(tenant_id, hours)
    if cdn["error_rate_pct"] > 15:
        incidents.append({"severity": "P0", "type": "cdn_outage", "error_rate": cdn["error_rate_pct"],
                          "affected_sources": ["medianova"], "detected_at": now})
    elif cdn["error_rate_pct"] > 5:
        incidents.append({"severity": "P1", "type": "cdn_error_spike", "error_rate": cdn["error_rate_pct"],
                          "affected_sources": ["medianova"], "detected_at": now})

    drm = get_drm_status(tenant_id, hours)
    for drm_name in ["widevine", "fairplay"]:
        if drm[drm_name]["error_rate_pct"] > 10:
            incidents.append({"severity": "P1", "type": "drm_degradation",
                              "error_rate": drm[drm_name]["error_rate_pct"],
                              "affected_sources": [drm_name], "detected_at": now})

    api = get_api_health(tenant_id, hours)
    if api["p99_response_time_ms"] > 2000:
        incidents.append({"severity": "P2", "type": "api_latency",
                          "p99_ms": api["p99_response_time_ms"],
                          "affected_sources": ["api_logs"], "detected_at": now})

    infra = get_infrastructure_health(tenant_id, hours)
    if infra["critical_services"]:
        incidents.append({"severity": "P2", "type": "service_degradation",
                          "critical_services": infra["critical_services"],
                          "affected_sources": ["newrelic"], "detected_at": now})

    qoe = get_player_qoe(tenant_id, hours)
    if qoe["avg_qoe_score"] > 0 and qoe["avg_qoe_score"] < 2.5:
        incidents.append({"severity": "P1", "type": "qoe_degradation",
                          "avg_qoe": qoe["avg_qoe_score"],
                          "affected_sources": ["player_events"], "detected_at": now})

    return incidents


# ══════════════════════════════════════════════════════════════════════
# P1/P2 MODULE QUERY HELPERS
# ══════════════════════════════════════════════════════════════════════


def get_app_reviews(tenant_id: str, hours: int = 168) -> dict:
    """App review summary from app_reviews_logs (default 7 days)."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.app_reviews_logs"
    since = _hours_ago(hours)

    total_row = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    total = total_row[0]["cnt"] if total_row else 0
    if total == 0:
        return {"total_reviews": 0, "avg_rating": 0, "sentiment_breakdown": {}, "top_categories": []}

    avg_row = _safe_query(db, tenant_id, f"SELECT AVG(rating) as avg_r FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    avg_rating = round(avg_row[0]["avg_r"] or 0, 2) if avg_row else 0

    sent = _safe_query(db, tenant_id, f"SELECT sentiment, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' GROUP BY sentiment")
    cats = _safe_query(db, tenant_id, f"SELECT category, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' GROUP BY category ORDER BY cnt DESC LIMIT 5")

    return {
        "total_reviews": total, "avg_rating": avg_rating,
        "sentiment_breakdown": {r["sentiment"]: r["cnt"] for r in sent},
        "top_categories": [{"category": r["category"], "count": r["cnt"]} for r in cats],
    }


def get_epg_schedule(tenant_id: str) -> dict:
    """EPG schedule summary from epg_logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.epg_logs"

    total_row = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}'")
    total = total_row[0]["cnt"] if total_row else 0

    channels = _safe_query(db, tenant_id, f"SELECT channel, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' GROUP BY channel ORDER BY cnt DESC")
    live = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND event_type = 'live_sport'")
    pre_scale = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND pre_scale_required = 1")

    return {
        "total_programs": total,
        "channels": [{"channel": r["channel"], "programs": r["cnt"]} for r in channels],
        "live_sport_count": live[0]["cnt"] if live else 0,
        "pre_scale_needed": pre_scale[0]["cnt"] if pre_scale else 0,
    }


def get_churn_metrics(tenant_id: str) -> dict:
    """CRM churn metrics from crm_subscriber_logs."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.crm_subscriber_logs"

    total_row = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}'")
    total = total_row[0]["cnt"] if total_row else 0
    if total == 0:
        return {"total_subscribers": 0, "avg_churn_risk": 0, "at_risk_count": 0, "tier_breakdown": {}}

    avg_row = _safe_query(db, tenant_id, f"SELECT AVG(churn_risk) as avg_cr FROM {table} WHERE tenant_id = '{tenant_id}'")
    at_risk = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND churn_risk > 0.7")
    tiers = _safe_query(db, tenant_id, f"SELECT subscription_tier, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' GROUP BY subscription_tier")

    return {
        "total_subscribers": total,
        "avg_churn_risk": round(avg_row[0]["avg_cr"] or 0, 3) if avg_row else 0,
        "at_risk_count": at_risk[0]["cnt"] if at_risk else 0,
        "tier_breakdown": {r["subscription_tier"]: r["cnt"] for r in tiers},
    }


def get_billing_summary(tenant_id: str, hours: int = 720) -> dict:
    """Billing summary from billing_logs (default 30 days)."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    table = f"{t}.billing_logs"
    since = _hours_ago(hours)

    total_row = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}'")
    total = total_row[0]["cnt"] if total_row else 0
    if total == 0:
        return {"total_transactions": 0, "total_revenue_tl": 0, "failed_count": 0, "event_types": {}}

    rev = _safe_query(db, tenant_id, f"SELECT SUM(amount) as total FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND payment_status = 'success'")
    failed = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' AND payment_status = 'failed'")
    types = _safe_query(db, tenant_id, f"SELECT event_type, COUNT(*) as cnt FROM {table} WHERE tenant_id = '{tenant_id}' AND timestamp >= '{since}' GROUP BY event_type ORDER BY cnt DESC")

    return {
        "total_transactions": total,
        "total_revenue_tl": round(rev[0]["total"] or 0, 2) if rev else 0,
        "failed_count": failed[0]["cnt"] if failed else 0,
        "event_types": {r["event_type"]: r["cnt"] for r in types},
    }


def get_data_source_stats(tenant_id: str) -> dict:
    """Row counts per table in logs.duckdb for admin dashboard."""
    db = _get_logs_db()
    t = tenant_id.replace("-", "_")
    sources = [
        "medianova", "origin_server", "widevine_drm", "fairplay_drm",
        "player_events", "npaw_analytics", "api_logs", "newrelic_apm",
        "crm_subscriber", "epg", "billing", "push_notifications", "app_reviews",
    ]
    stats: dict[str, int] = {}
    total = 0
    for src in sources:
        rows = _safe_query(db, tenant_id, f"SELECT COUNT(*) as cnt FROM {t}.{src}_logs")
        cnt = rows[0]["cnt"] if rows else 0
        stats[src] = cnt
        total += cnt
    return {"sources": stats, "total_rows": total}
