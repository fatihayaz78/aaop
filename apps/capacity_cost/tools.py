"""Capacity & Cost tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.capacity_cost.config import CapacityCostConfig
from apps.capacity_cost.schemas import (
    AutomationJob,
    CapacityForecast,
    CostReport,
    ScaleAction,
    ThresholdBreach,
)
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── LOW risk tools ──────────────────────────────────────


async def get_current_metrics(tenant_id: str, db: Any) -> list[dict]:
    """Get current capacity metrics. Risk: LOW."""
    return db.fetch_all(
        """SELECT event_name, expected_viewers, peak_viewers, status
           FROM shared_analytics.live_events
           WHERE tenant_id = ? AND status = 'live'""",
        [tenant_id],
    )


async def forecast_capacity(
    tenant_id: str,
    metric: str,
    current_pct: float,
    trend: str = "stable",
    horizon_hours: int = 24,
) -> CapacityForecast:
    """Forecast capacity usage. Risk: LOW."""
    config = CapacityCostConfig()

    # Simple trend-based projection
    if trend == "growing":
        growth_rate = 0.5  # % per hour
        predicted_pct = min(current_pct + growth_rate * horizon_hours, 100.0)
    elif trend == "declining":
        predicted_pct = max(current_pct - 0.3 * horizon_hours, 0.0)
    else:
        predicted_pct = current_pct

    breach_hours = None
    if trend == "growing" and predicted_pct >= config.crit_threshold_pct:
        remaining = config.crit_threshold_pct - current_pct
        breach_hours = max(int(remaining / growth_rate), 1) if remaining > 0 else 0

    confidence = 0.85 if trend == "stable" else 0.65

    return CapacityForecast(
        tenant_id=tenant_id,
        metric=metric,
        current_pct=round(current_pct, 2),
        predicted_pct=round(predicted_pct, 2),
        horizon_hours=horizon_hours,
        trend=trend,
        breach_estimated_hours=breach_hours,
        confidence=confidence,
    )


async def calculate_cost(
    tenant_id: str,
    period: str = "daily",
    breakdown: dict[str, float] | None = None,
    total_viewers: int = 0,
) -> CostReport:
    """Calculate cost report. Risk: LOW."""
    if breakdown is None:
        breakdown = {}
    total = sum(breakdown.values())
    cpv = total / total_viewers if total_viewers > 0 else 0.0

    return CostReport(
        tenant_id=tenant_id,
        period=period,
        total_cost=round(total, 2),
        breakdown=breakdown,
        cost_per_viewer=round(cpv, 6),
    )


async def detect_threshold_breach(
    tenant_id: str,
    metric: str,
    current_pct: float,
) -> ThresholdBreach | None:
    """Detect if metric breaches warn/crit threshold. Risk: LOW."""
    config = CapacityCostConfig()

    if current_pct >= config.crit_threshold_pct:
        return ThresholdBreach(
            tenant_id=tenant_id,
            metric=metric,
            current_pct=round(current_pct, 2),
            threshold_pct=config.crit_threshold_pct,
            level="critical",
            message=f"{metric} at {current_pct:.1f}% — CRITICAL threshold ({config.crit_threshold_pct}%)",
        )
    if current_pct >= config.warn_threshold_pct:
        return ThresholdBreach(
            tenant_id=tenant_id,
            metric=metric,
            current_pct=round(current_pct, 2),
            threshold_pct=config.warn_threshold_pct,
            level="warn",
            message=f"{metric} at {current_pct:.1f}% — WARN threshold ({config.warn_threshold_pct}%)",
        )
    return None


# ── MEDIUM risk tools ───────────────────────────────────


async def write_forecast(tenant_id: str, forecast: CapacityForecast, db: Any) -> str:
    """Write forecast to DuckDB agent_decisions. Risk: MEDIUM (auto+notify)."""
    import json
    from uuid import uuid4

    decision_id = f"DEC-{uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO shared_analytics.agent_decisions
        (decision_id, tenant_id, app, action, risk_level, approval_required,
         llm_model_used, reasoning_summary, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            decision_id, tenant_id, "capacity_cost", "forecast_capacity", "LOW", False,
            "claude-sonnet-4-20250514",
            json.dumps(forecast.model_dump(), default=str),
            forecast.confidence,
        ],
    )
    logger.info("forecast_written", tenant_id=tenant_id, decision_id=decision_id)
    return decision_id


async def publish_scale_recommendation(
    tenant_id: str,
    metric: str,
    current_pct: float,
    scale_factor: float,
    reason: str,
    event_bus: Any,
) -> None:
    """Publish scale_recommendation event. Risk: MEDIUM (auto+notify)."""
    event = BaseEvent(
        event_type=EventType.SCALE_RECOMMENDATION,
        tenant_id=tenant_id,
        source_app="capacity_cost",
        severity=SeverityLevel.P2,
        payload={
            "metric": metric,
            "current_pct": current_pct,
            "scale_factor": scale_factor,
            "reason": reason,
        },
    )
    await event_bus.publish(event)
    logger.info(
        "scale_recommendation_published",
        tenant_id=tenant_id, metric=metric, factor=scale_factor,
    )


# ── HIGH risk tools ─────────────────────────────────────


async def create_automation_job(
    tenant_id: str, job: AutomationJob,
) -> dict:
    """Create automation job. Risk: HIGH (approval_required)."""
    logger.warning(
        "automation_job_requested",
        tenant_id=tenant_id, job_id=job.job_id, job_type=job.job_type,
    )
    return {
        "status": "approval_required",
        "job_id": job.job_id,
        "job_type": job.job_type,
    }


async def execute_scale_action(
    tenant_id: str, action: ScaleAction,
) -> dict:
    """Execute scale action. Risk: HIGH (approval_required)."""
    logger.warning(
        "scale_action_requested",
        tenant_id=tenant_id, action_id=action.action_id,
        resource=action.resource, factor=action.scale_factor,
    )
    return {
        "status": "approval_required",
        "action_id": action.action_id,
        "resource": action.resource,
        "scale_factor": action.scale_factor,
        "reason": action.reason,
    }
