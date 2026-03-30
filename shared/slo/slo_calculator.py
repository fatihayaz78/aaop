"""SLO Calculator — measures actual values against SLO targets.

Supports 5 metrics: availability, qoe_score, cdn_error_rate, api_p99, incident_mttr.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class SLODefinition(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    tenant_id: str
    name: str
    description: str = ""
    metric: str  # availability, qoe_score, cdn_error_rate, api_p99, incident_mttr
    target: float
    operator: str  # gte, lte
    window_days: int = 30
    is_active: bool = True


class SLOMeasurement(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    slo_id: str
    tenant_id: str
    period_start: str
    period_end: str
    measured_value: float
    target: float
    is_met: bool
    error_budget_pct: float = 0.0
    measured_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SLOStatus(BaseModel):
    slo_id: str
    name: str
    metric: str
    target: float
    operator: str
    current_value: float
    is_met: bool
    error_budget_remaining_pct: float
    trend: str = "stable"  # improving, degrading, stable
    period_days: int = 30


class SLOCalculator:
    """Calculates SLO metrics from DuckDB data."""

    def _is_met(self, value: float, target: float, operator: str) -> bool:
        return value >= target if operator == "gte" else value <= target

    def _error_budget(self, value: float, target: float, operator: str) -> float:
        if operator == "gte":
            if value >= target:
                return min(100.0, 100.0 * (value - target) / max(1 - target, 0.001) + 100)
            return max(0.0, 100.0 * (1 - (target - value) / max(target, 0.001)))
        else:  # lte
            if value <= target:
                return min(100.0, 100.0 * (target - value) / max(target, 0.001) + 100)
            return max(0.0, 100.0 * (1 - (value - target) / max(target, 0.001)))

    async def calculate(self, slo: SLODefinition, tenant_id: str,
                        schema: str, period_days: int = 30) -> SLOMeasurement:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=period_days)).isoformat()
        end = now.isoformat()

        value = await self._measure_metric(slo.metric, tenant_id, schema, period_days)
        met = self._is_met(value, slo.target, slo.operator)
        budget = self._error_budget(value, slo.target, slo.operator)

        return SLOMeasurement(
            slo_id=slo.id, tenant_id=tenant_id,
            period_start=start[:10], period_end=end[:10],
            measured_value=round(value, 6), target=slo.target,
            is_met=met, error_budget_pct=round(min(budget, 100), 1),
        )

    async def calculate_all(self, definitions: list[SLODefinition],
                            tenant_id: str, schema: str) -> list[SLOMeasurement]:
        results = []
        for slo in definitions:
            if slo.is_active:
                m = await self.calculate(slo, tenant_id, schema, slo.window_days)
                results.append(m)
        return results

    async def _measure_metric(self, metric: str, tenant_id: str, schema: str, days: int) -> float:
        try:
            if metric == "availability":
                return self._calc_availability(tenant_id, days)
            elif metric == "qoe_score":
                return self._calc_qoe_score(tenant_id, schema)
            elif metric == "cdn_error_rate":
                return self._calc_cdn_error_rate(tenant_id, schema)
            elif metric == "api_p99":
                return self._calc_api_p99(tenant_id, schema)
            elif metric == "incident_mttr":
                return self._calc_mttr(tenant_id, days)
        except Exception as exc:
            logger.warning("slo_metric_error", metric=metric, error=str(exc))
        return 0.0

    def _calc_availability(self, tenant_id: str, days: int) -> float:
        try:
            from backend.dependencies import _duckdb
            if not _duckdb:
                return 1.0
            rows = _duckdb.fetch_all(
                "SELECT COUNT(*) as cnt FROM shared_analytics.incidents "
                "WHERE tenant_id = ? AND severity IN ('P0') AND created_at >= CURRENT_DATE - INTERVAL ? DAY",
                [tenant_id, days],
            )
            p0_count = rows[0]["cnt"] if rows else 0
            total_minutes = days * 24 * 60
            downtime_minutes = p0_count * 30  # assume 30 min per P0
            return 1.0 - (downtime_minutes / total_minutes)
        except Exception:
            return 1.0

    def _calc_qoe_score(self, tenant_id: str, schema: str) -> float:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")
            rows = _safe_query(db, tenant_id,
                f"SELECT AVG(qoe_score) as avg_score FROM {t}.npaw_analytics_logs "
                f"WHERE tenant_id = '{tenant_id}' AND timestamp >= CURRENT_DATE - INTERVAL 30 DAY")
            return round(rows[0]["avg_score"] or 3.5, 2) if rows else 3.5
        except Exception:
            return 3.5

    def _calc_cdn_error_rate(self, tenant_id: str, schema: str) -> float:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")
            rows = _safe_query(db, tenant_id,
                f"SELECT COUNT(*) as total, "
                f"SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors "
                f"FROM {t}.medianova_logs "
                f"WHERE tenant_id = '{tenant_id}' AND timestamp >= CURRENT_DATE - INTERVAL 30 DAY")
            if rows and rows[0]["total"] > 0:
                return round(rows[0]["errors"] / rows[0]["total"], 6)
            return 0.0
        except Exception:
            return 0.0

    def _calc_api_p99(self, tenant_id: str, schema: str) -> float:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")
            rows = _safe_query(db, tenant_id,
                f"SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99 "
                f"FROM {t}.api_logs_logs "
                f"WHERE tenant_id = '{tenant_id}' AND timestamp >= CURRENT_DATE - INTERVAL 30 DAY")
            return round(rows[0]["p99"] or 0, 1) if rows else 0.0
        except Exception:
            return 0.0

    def _calc_mttr(self, tenant_id: str, days: int) -> float:
        try:
            from backend.dependencies import _duckdb
            if not _duckdb:
                return 0.0
            rows = _duckdb.fetch_all(
                "SELECT AVG(mttr_seconds) / 60.0 as avg_mttr FROM shared_analytics.incidents "
                "WHERE tenant_id = ? AND status = 'resolved' AND created_at >= CURRENT_DATE - INTERVAL ? DAY",
                [tenant_id, days],
            )
            return round(rows[0]["avg_mttr"] or 0, 1) if rows else 0.0
        except Exception:
            return 0.0
