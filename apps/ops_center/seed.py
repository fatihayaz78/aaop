"""Seed mock data for Ops Center — 50 incidents + 50 agent decisions."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

from shared.clients.duckdb_client import DuckDBClient

logger = structlog.get_logger(__name__)

_TITLES = [
    "CDN Edge Node Failure - Frankfurt",
    "HLS Manifest 503 Spike",
    "Buffering Rate Anomaly - Galatasaray vs Fenerbahce",
    "DRM License Server Timeout",
    "Origin Shield Overload - Champions League",
    "QoE Score Drop - Istanbul Region",
    "Akamai Token Auth Failure",
    "Live Stream Interruption - beIN Sports 1",
    "Cache Purge Delay - Akamai",
    "DNS Resolution Spike - cdn.ssportplus.com",
    "SSL Certificate Warning - Edge Cluster EU",
    "API Gateway 502 - /api/v2/streams",
    "Player SDK Crash Rate Spike - Android",
    "Bandwidth Throttle - Peak Hours",
    "Origin 5xx Rate > 3% - VOD Assets",
    "CDN Traffic Redirect Loop - Ankara Region",
    "Live Event Pre-Scale Failure",
    "Transcoder Queue Backlog",
    "Multi-CDN Failover Triggered",
    "Authentication Service Latency > 2s",
]

_SUMMARIES_TR = [
    "Frankfurt edge sunucularında yüksek hata oranı tespit edildi. Canlı yayın akışı etkileniyor.",
    "HLS manifest isteklerinde 503 hatası patlaması. CDN origin'e yük aktarıldı.",
    "Galatasaray-Fenerbahçe maçında buffering oranı %8'i aştı. Kullanıcı deneyimi ciddi etkilendi.",
    "DRM lisans sunucusu 5 saniyeden uzun yanıt süresi veriyor. VOD ve canlı yayın etkilendi.",
    "Şampiyonlar Ligi maçı sırasında origin shield aşırı yüklendi. Cache hit oranı %40'a düştü.",
    "İstanbul bölgesinde QoE skoru 3.2'ye düştü. Buffering ve başlatma süresi arttı.",
    "Akamai token doğrulama hatası. Bazı kullanıcılar içeriğe erişemiyor.",
    "beIN Sports 1 canlı yayında kesinti. Encoder çıkışı 30 saniye kayboldu.",
    "Cache temizleme işlemi 15 dakikadır tamamlanmadı. Eski içerik sunuluyor.",
    "DNS çözümleme süresi 500ms'yi aştı. Yeni kullanıcılar bağlanamıyor.",
]

_DETAILS_EN = [
    "Edge node eu-fra-01 reporting 90% packet loss. BGP route withdrawn at 14:23 UTC. Failover to eu-fra-02 in progress.",
    "Origin returning 503 for /live/manifest.m3u8 at 450 req/s. Origin CPU at 98%. Auto-scale triggered.",
    "Buffering ratio 8.2% (threshold: 3%). Correlated with CDN cache miss spike in IST region.",
    "DRM license API p99 latency: 5.2s (SLA: 1s). Connection pool exhausted. 3 replicas restarting.",
    "Origin shield requests: 12K/s (normal: 2K/s). Cache hit ratio dropped from 92% to 41%. Miss storm detected.",
    "QoE score: 3.2 (baseline: 4.5). Startup time p95: 8.2s. Rebuffer frequency: 4.1/hour.",
    "Token validation returning 403 for 12% of requests. Key rotation suspected. Investigating CDN config.",
    "Encoder output gap: 30s starting at 19:45:12 UTC. Redundant encoder activated at 19:45:42.",
    "Cache purge job stuck in PENDING state. 2.3M objects queued. API rate limit may be exceeded.",
    "DNS p95 resolution: 523ms. Authoritative nameserver eu-dns-03 not responding.",
]

_SERVICES = ["cdn", "origin", "drm", "player", "api", "encoder", "dns", "cache"]

_TOOLS = [
    "get_incident_history", "get_cdn_analysis", "get_qoe_metrics",
    "correlate_events", "create_incident_record", "update_incident_status",
    "trigger_rca", "send_slack_notification",
]


def seed_ops_center_mock_data(duck: DuckDBClient, tenant_id: str = "s_sport_plus") -> None:
    """Seed 50 incidents and 50 agent decisions. Idempotent — skips if >= 10 rows exist."""
    # Check if already seeded
    try:
        row = duck.fetch_one(
            "SELECT COUNT(*) as cnt FROM shared_analytics.incidents WHERE tenant_id = ?",
            [tenant_id],
        )
        if row and row.get("cnt", 0) >= 10:
            logger.info("ops_seed_skipped", tenant_id=tenant_id, existing=row["cnt"])
            return
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    incidents = []

    # P0: 5 incidents
    for i in range(5):
        incidents.append(_make_incident(
            tenant_id, "P0", random.choice(["resolved"]),
            mttr=random.randint(180, 290), hours_ago=random.randint(1, 168), now=now,
        ))

    # P1: 15 incidents
    for i in range(15):
        incidents.append(_make_incident(
            tenant_id, "P1", random.choice(["resolved", "investigating"]),
            mttr=random.randint(200, 600), hours_ago=random.randint(1, 168), now=now,
        ))

    # P2: 20 incidents
    for i in range(20):
        incidents.append(_make_incident(
            tenant_id, "P2", random.choice(["resolved", "open"]),
            mttr=random.randint(300, 1800) if random.random() > 0.3 else None,
            hours_ago=random.randint(1, 168), now=now,
        ))

    # P3: 10 incidents
    for i in range(10):
        incidents.append(_make_incident(
            tenant_id, "P3", random.choice(["resolved", "open"]),
            mttr=random.randint(600, 3600) if random.random() > 0.5 else None,
            hours_ago=random.randint(1, 168), now=now,
        ))

    # Insert incidents
    for inc in incidents:
        try:
            duck.execute(
                """INSERT INTO shared_analytics.incidents
                   (incident_id, tenant_id, severity, title, status, source_app,
                    correlation_ids, affected_svcs, metrics_at_time, rca_id,
                    mttr_seconds, resolved_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [inc["incident_id"], inc["tenant_id"], inc["severity"], inc["title"],
                 inc["status"], inc["source_app"],
                 json.dumps(inc["correlation_ids"]), json.dumps(inc["affected_svcs"]),
                 json.dumps(inc["metrics_at_time"]), inc["rca_id"],
                 inc["mttr_seconds"], inc["resolved_at"],
                 inc["created_at"], inc["updated_at"]],
            )
        except Exception as exc:
            logger.warning("ops_seed_incident_error", error=str(exc))

    # Seed 50 agent decisions
    for i in range(50):
        tool = random.choice(_TOOLS)
        risk = "LOW" if tool.startswith("get_") or tool == "correlate_events" else "MEDIUM"
        try:
            duck.execute(
                """INSERT INTO shared_analytics.agent_decisions
                   (decision_id, tenant_id, app, action, risk_level, approval_required,
                    llm_model_used, reasoning_summary, tools_executed,
                    confidence_score, duration_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [f"DEC-{uuid4().hex[:12]}", tenant_id, "ops_center", tool, risk,
                 risk == "HIGH",
                 random.choice(["claude-opus-4-20250514", "claude-sonnet-4-20250514"]),
                 f"Executed {tool} for incident analysis",
                 json.dumps([tool]),
                 round(random.uniform(0.7, 0.99), 2),
                 random.randint(200, 5000),
                 (now - timedelta(hours=random.randint(0, 168))).isoformat()],
            )
        except Exception:
            pass

    logger.info("ops_seed_complete", tenant_id=tenant_id, incidents=len(incidents), decisions=50)


def _make_incident(
    tenant_id: str,
    severity: str,
    status: str,
    mttr: int | None,
    hours_ago: int,
    now: datetime,
) -> dict:
    title = random.choice(_TITLES)
    created = now - timedelta(hours=hours_ago)
    resolved = (created + timedelta(seconds=mttr)) if mttr and status == "resolved" else None
    svcs = random.sample(_SERVICES, k=random.randint(1, 3))

    return {
        "incident_id": f"INC-{uuid4().hex[:12]}",
        "tenant_id": tenant_id,
        "severity": severity,
        "title": title,
        "status": status,
        "source_app": random.choice(["log_analyzer", "viewer_experience", "alert_center", "ops_center"]),
        "correlation_ids": [f"corr-{uuid4().hex[:8]}"],
        "affected_svcs": svcs,
        "metrics_at_time": {"error_rate": round(random.uniform(0.01, 0.15), 3), "cache_hit": round(random.uniform(0.3, 0.95), 2)},
        "rca_id": f"RCA-{uuid4().hex[:8]}" if severity in ("P0", "P1") and status == "resolved" else None,
        "mttr_seconds": mttr,
        "resolved_at": resolved.isoformat() if resolved else None,
        "created_at": created.isoformat(),
        "updated_at": (resolved or created).isoformat(),
    }
