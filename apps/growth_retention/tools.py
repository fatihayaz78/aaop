"""Growth & Retention tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

import re
from typing import Any

import structlog

from apps.growth_retention.config import GrowthRetentionConfig
from apps.growth_retention.schemas import (
    ChurnRiskResult,
    CustomerSegment,
    GrowthInsight,
    NLQueryResult,
    RetentionCampaign,
    RetentionScore,
)
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── LOW risk tools ──────────────────────────────────────


async def calculate_churn_risk(
    tenant_id: str,
    segment_id: str,
    qoe_avg: float,
    cdn_error_rate: float,
    retention_7d: float | None = None,
    retention_30d: float | None = None,
) -> ChurnRiskResult:
    """Calculate churn risk for a segment. Risk: LOW."""
    # Weighted risk formula
    risk = 0.0
    factors: dict[str, Any] = {}

    # QoE impact (0-5 scale, lower = higher risk)
    if qoe_avg < 3.5:
        qoe_risk = (3.5 - qoe_avg) / 3.5
        risk += qoe_risk * 0.4
        factors["low_qoe"] = {"score": qoe_avg, "weight": 0.4}

    # CDN error impact
    if cdn_error_rate > 0.03:
        cdn_risk = min(cdn_error_rate / 0.1, 1.0)
        risk += cdn_risk * 0.3
        factors["high_cdn_errors"] = {"rate": cdn_error_rate, "weight": 0.3}

    # Retention trend
    if retention_7d is not None and retention_30d is not None and retention_30d > 0:
        trend = retention_7d / retention_30d
        if trend < 0.9:
            trend_risk = (0.9 - trend) / 0.9
            risk += trend_risk * 0.3
            factors["declining_retention"] = {"trend": trend, "weight": 0.3}

    risk = min(risk, 1.0)

    recommendation = ""
    if risk > 0.7:
        recommendation = "High churn risk — immediate retention campaign recommended"
    elif risk > 0.3:
        recommendation = "Moderate risk — proactive engagement suggested"
    else:
        recommendation = "Low risk — continue monitoring"

    return ChurnRiskResult(
        tenant_id=tenant_id,
        segment_id=segment_id,
        churn_risk=round(risk, 4),
        factors=factors,
        recommendation=recommendation,
    )


async def get_qoe_correlation(tenant_id: str, db: Any) -> list[dict]:
    """Get QoE metrics correlated with retention. Risk: LOW."""
    return db.fetch_all(
        """SELECT user_id_hash, AVG(quality_score) as avg_qoe,
           COUNT(*) as session_count, AVG(buffering_ratio) as avg_buffer
           FROM shared_analytics.qoe_metrics
           WHERE tenant_id = ?
           GROUP BY user_id_hash
           ORDER BY avg_qoe ASC LIMIT 100""",
        [tenant_id],
    )


async def get_cdn_impact(tenant_id: str, db: Any) -> list[dict]:
    """Get CDN performance impact on viewers. Risk: LOW."""
    return db.fetch_all(
        """SELECT sub_module, AVG(error_rate) as avg_error_rate,
           AVG(cache_hit_rate) as avg_cache_hit, AVG(avg_ttfb_ms) as avg_ttfb
           FROM shared_analytics.cdn_analysis
           WHERE tenant_id = ?
           GROUP BY sub_module""",
        [tenant_id],
    )


async def segment_customers(
    tenant_id: str,
    criteria: dict[str, Any],
) -> CustomerSegment:
    """Segment customers based on criteria. Risk: LOW."""
    segment = CustomerSegment(
        tenant_id=tenant_id,
        name=criteria.get("name", "unnamed"),
        criteria=criteria,
        size=criteria.get("size", 0),
        avg_churn_risk=criteria.get("avg_churn_risk", 0.0),
        avg_qoe_score=criteria.get("avg_qoe_score", 0.0),
    )
    logger.info("segment_created", tenant_id=tenant_id, segment_id=segment.segment_id)
    return segment


def validate_sql_query(sql: str, config: GrowthRetentionConfig) -> tuple[bool, str]:
    """Validate generated SQL is read-only and targets allowed tables only."""
    sql_upper = sql.upper().strip()

    # Must be SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT statements allowed"

    # No write operations
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", sql_upper):
            return False, f"Write operation '{kw}' not allowed"

    # Must reference allowed schema
    for table in config.allowed_tables:
        if table.lower() in sql.lower():
            return True, "OK"

    return False, "Query must reference shared_analytics tables"


async def nl_to_sql_query(
    tenant_id: str, question: str, generated_sql: str, db: Any,
) -> NLQueryResult:
    """Execute NL-generated SQL query on DuckDB. Risk: LOW. Read-only only."""
    config = GrowthRetentionConfig()
    valid, reason = validate_sql_query(generated_sql, config)
    if not valid:
        return NLQueryResult(
            query=question,
            generated_sql=generated_sql,
            row_count=0,
        )

    import time
    start = time.monotonic()
    rows = db.fetch_all(generated_sql, [])
    duration = int((time.monotonic() - start) * 1000)

    columns = list(rows[0].keys()) if rows else []

    return NLQueryResult(
        query=question,
        generated_sql=generated_sql,
        columns=columns,
        rows=rows[:config.max_sql_results],
        row_count=len(rows),
        execution_time_ms=duration,
    )


async def get_growth_insights(tenant_id: str, data: dict[str, Any]) -> list[GrowthInsight]:
    """Generate growth insights from analysis data. Risk: LOW."""
    insights: list[GrowthInsight] = []

    churn_risk = data.get("churn_risk", 0.0)
    if churn_risk > 0.7:
        insights.append(GrowthInsight(
            tenant_id=tenant_id,
            category="retention",
            title="High churn risk detected",
            description=f"Segment churn risk is {churn_risk:.2f}",
            impact_score=churn_risk,
            suggested_action="Launch targeted retention campaign",
        ))

    avg_qoe = data.get("avg_qoe", 5.0)
    if avg_qoe < 3.0:
        insights.append(GrowthInsight(
            tenant_id=tenant_id,
            category="engagement",
            title="Low QoE affecting growth",
            description=f"Average QoE score is {avg_qoe:.1f}/5.0",
            impact_score=(5.0 - avg_qoe) / 5.0,
            suggested_action="Investigate CDN and buffering issues",
        ))

    return insights


# ── MEDIUM risk tools ───────────────────────────────────


async def write_analysis_result(
    tenant_id: str, score: RetentionScore, db: Any,
) -> str:
    """Write retention score to DuckDB. Risk: MEDIUM (auto+notify)."""
    db.execute(
        """INSERT INTO shared_analytics.retention_scores
        (score_id, tenant_id, segment_id, churn_risk, retention_7d, retention_30d, factors)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            score.score_id, tenant_id, score.segment_id, score.churn_risk,
            score.retention_7d, score.retention_30d,
            str(score.factors),
        ],
    )
    logger.info("retention_score_written", tenant_id=tenant_id, score_id=score.score_id)
    return score.score_id


async def trigger_churn_alert(
    tenant_id: str, segment_id: str, churn_risk: float, event_bus: Any,
) -> None:
    """Publish churn_risk_detected event. Risk: MEDIUM (auto+notify)."""
    event = BaseEvent(
        event_type=EventType.CHURN_RISK_DETECTED,
        tenant_id=tenant_id,
        source_app="growth_retention",
        severity=SeverityLevel.P2,
        payload={
            "segment_id": segment_id,
            "churn_risk": churn_risk,
        },
    )
    await event_bus.publish(event)
    logger.info(
        "churn_risk_detected_published",
        tenant_id=tenant_id, segment_id=segment_id, churn_risk=churn_risk,
    )


# ── HIGH risk tools ─────────────────────────────────────


async def send_retention_campaign(
    tenant_id: str, campaign: RetentionCampaign,
) -> dict:
    """Send retention campaign. Risk: HIGH (approval_required)."""
    logger.warning(
        "retention_campaign_requested",
        tenant_id=tenant_id, campaign_id=campaign.campaign_id,
        segment_id=campaign.segment_id,
    )
    return {
        "status": "approval_required",
        "campaign_id": campaign.campaign_id,
        "segment_id": campaign.segment_id,
        "campaign_type": campaign.campaign_type,
    }
