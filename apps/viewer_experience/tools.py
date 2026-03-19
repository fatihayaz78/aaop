"""Viewer Experience tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog

from apps.viewer_experience.config import ViewerExperienceConfig
from apps.viewer_experience.schemas import Complaint, ComplaintAnalysis, QoEAnomaly, QoESession
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)

# In-memory session dedup tracker (swap to Redis in production)
_session_dedup: dict[str, float] = {}


def compute_qoe_score(session: QoESession) -> float:
    """Exact QoE score formula from spec Section 4 (0.0-5.0 scale)."""
    score = 5.0
    score -= session.buffering_ratio * 10.0
    score -= max(0, (session.startup_time_ms - 2000) / 1000)
    score -= len(session.errors) * 0.3
    if session.bitrate_avg < 1500:
        score -= (1500 - session.bitrate_avg) / 1000
    return max(0.0, min(5.0, round(score, 2)))


def is_session_deduped(session_id: str, window_seconds: int = 300) -> bool:
    """Check if session was already processed within dedup window."""
    now = time.monotonic()
    last_seen = _session_dedup.get(session_id)
    if last_seen and (now - last_seen) < window_seconds:
        return True
    _session_dedup[session_id] = now
    return False


def reset_session_dedup() -> None:
    """Reset dedup tracker (for testing)."""
    _session_dedup.clear()


# ── LOW risk tools ──────────────────────────────────────


async def score_qoe_session(tenant_id: str, session: QoESession) -> QoESession:
    """Calculate QoE score for a session. Risk: LOW."""
    session.quality_score = compute_qoe_score(session)
    logger.info("qoe_scored", tenant_id=tenant_id, session_id=session.session_id, score=session.quality_score)
    return session


async def get_session_context(tenant_id: str, session_id: str, redis: Any) -> dict | None:
    """Get session context from Redis cache. Risk: LOW."""
    key = f"ctx:{tenant_id}:qoe:session:{session_id}"
    return await redis.get_json(key)


async def detect_qoe_anomaly(tenant_id: str, session: QoESession) -> QoEAnomaly | None:
    """Detect QoE anomaly if score < threshold. Risk: LOW."""
    config = ViewerExperienceConfig()
    if session.quality_score < config.qoe_degradation_threshold:
        reason_parts = []
        if session.buffering_ratio > 0.05:
            reason_parts.append(f"buffering={session.buffering_ratio:.1%}")
        if session.startup_time_ms > 3000:
            reason_parts.append(f"startup={session.startup_time_ms}ms")
        if session.errors:
            reason_parts.append(f"errors={len(session.errors)}")
        if session.bitrate_avg < 1500:
            reason_parts.append(f"bitrate={session.bitrate_avg}kbps")
        reason = ", ".join(reason_parts) or "low_quality_score"

        severity = "P1" if session.quality_score < 1.5 else "P2"
        return QoEAnomaly(
            session_id=session.session_id,
            tenant_id=tenant_id,
            quality_score=session.quality_score,
            reason=reason,
            severity=severity,
        )
    return None


async def search_similar_issues(tenant_id: str, session: QoESession, chroma: Any) -> list[dict]:
    """Search ChromaDB for similar QoE issues. Risk: LOW."""
    query = f"buffering={session.buffering_ratio} startup={session.startup_time_ms} device={session.device_type}"
    results = chroma.query(collection_name="incidents", query_texts=[query], n_results=3)
    return results.get("documents", [[]])[0] if results else []


async def categorize_complaint(tenant_id: str, content: str) -> ComplaintAnalysis:
    """NLP categorize complaint (placeholder — real impl uses LLM). Risk: LOW."""
    content_lower = content.lower()
    if any(w in content_lower for w in ("buffer", "donma", "takıl")):
        category = "buffering"
    elif any(w in content_lower for w in ("kalite", "quality", "blur", "piksel")):
        category = "video_quality"
    elif any(w in content_lower for w in ("ses", "audio", "sound")):
        category = "audio"
    elif any(w in content_lower for w in ("login", "giriş", "şifre")):
        category = "login"
    else:
        category = "other"

    # Simple sentiment
    neg_words = ("kötü", "berbat", "rezalet", "terrible", "worst", "awful", "bad")
    pos_words = ("iyi", "güzel", "great", "good", "love")
    if any(w in content_lower for w in neg_words):
        sentiment = "negative"
    elif any(w in content_lower for w in pos_words):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    # Priority based on sentiment + category
    if sentiment == "negative" and category in ("buffering", "video_quality"):
        priority = "P2"
    elif sentiment == "negative":
        priority = "P3"
    else:
        priority = "P3"

    return ComplaintAnalysis(
        complaint_id="", category=category, sentiment=sentiment, priority=priority,
    )


async def find_related_complaints(tenant_id: str, content: str, chroma: Any) -> list[str]:
    """Search ChromaDB for similar past complaints. Risk: LOW."""
    config = ViewerExperienceConfig()
    results = chroma.query(
        collection_name=config.chroma_collection,
        query_texts=[content],
        n_results=config.similar_complaint_top_k,
    )
    ids = results.get("ids", [[]])[0] if results else []
    return ids


# ── MEDIUM risk tools ───────────────────────────────────


async def write_qoe_metrics(tenant_id: str, session: QoESession, db: Any) -> str:
    """Write QoE metrics to DuckDB. Risk: MEDIUM (auto+notify)."""
    db.execute(
        """INSERT INTO shared_analytics.qoe_metrics
        (metric_id, tenant_id, session_id, user_id_hash, content_id,
         device_type, region, buffering_ratio, startup_time_ms,
         bitrate_avg, quality_score, errors, event_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())""",
        [
            session.session_id, tenant_id, session.session_id,
            session.user_id_hash, session.content_id, session.device_type,
            session.region, session.buffering_ratio, session.startup_time_ms,
            session.bitrate_avg, session.quality_score, str(session.errors),
        ],
    )
    logger.info("qoe_metrics_written", tenant_id=tenant_id, session_id=session.session_id)
    return session.session_id


async def write_complaint(tenant_id: str, complaint: Complaint, db: Any) -> str:
    """Write complaint to SQLite. Risk: MEDIUM (auto+notify)."""
    await db.execute(
        """INSERT INTO complaints (id, tenant_id, source, category, sentiment, priority, status, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (complaint.id, tenant_id, complaint.source, complaint.category,
         complaint.sentiment, complaint.priority, complaint.status,
         hashlib.sha256(complaint.content.encode()).hexdigest()[:16]),
    )
    logger.info("complaint_written", tenant_id=tenant_id, complaint_id=complaint.id)
    return complaint.id


async def trigger_qoe_alert(tenant_id: str, anomaly: QoEAnomaly, event_bus: Any) -> None:
    """Publish qoe_degradation event. Risk: MEDIUM (auto+notify)."""
    from shared.event_bus import EventType
    from shared.schemas.base_event import BaseEvent

    severity = SeverityLevel(anomaly.severity) if anomaly.severity in ("P0", "P1", "P2", "P3") else SeverityLevel.P2
    event = BaseEvent(
        event_type=EventType.QOE_DEGRADATION,
        tenant_id=tenant_id,
        source_app="viewer_experience",
        severity=severity,
        payload={
            "session_id": anomaly.session_id,
            "quality_score": anomaly.quality_score,
            "reason": anomaly.reason,
        },
    )
    await event_bus.publish(event)
    logger.info("qoe_alert_triggered", tenant_id=tenant_id, score=anomaly.quality_score)


# ── HIGH risk tools ─────────────────────────────────────


async def escalate_complaint(tenant_id: str, complaint_id: str, reason: str) -> dict:
    """Escalate complaint to management. Risk: HIGH (approval_required)."""
    logger.warning("complaint_escalation_requested", tenant_id=tenant_id, complaint_id=complaint_id)
    return {"status": "approval_required", "complaint_id": complaint_id, "reason": reason}
