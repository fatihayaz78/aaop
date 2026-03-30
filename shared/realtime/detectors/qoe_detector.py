"""QoE Detector — viewer quality score degradation detection."""

from __future__ import annotations

import structlog

from shared.realtime.detectors.base_detector import AnomalyEvent, BaseDetector

logger = structlog.get_logger(__name__)


class QoEDetector(BaseDetector):
    name = "qoe_detector"
    poll_interval_seconds = 30
    window_minutes = 5

    async def check(self, tenant_id: str, schema: str) -> list[AnomalyEvent]:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")

            rows = _safe_query(db, tenant_id, f"""
                SELECT AVG(qoe_score) as avg_score, COUNT(*) as cnt
                FROM {t}.npaw_analytics_logs
                WHERE tenant_id = '{tenant_id}'
                  AND timestamp >= NOW() - INTERVAL {self.window_minutes} MINUTE
                  AND qoe_score IS NOT NULL
            """)

            if not rows or rows[0]["cnt"] == 0:
                return []

            avg = rows[0]["avg_score"]
            if avg < 1.5:
                return [AnomalyEvent(
                    tenant_id=tenant_id, detector=self.name, severity="P0",
                    metric="avg_qoe_score", current_value=round(avg, 2),
                    threshold=1.5, window_minutes=self.window_minutes,
                    source_table=f"{t}.npaw_analytics_logs",
                )]
            elif avg < 2.5:
                return [AnomalyEvent(
                    tenant_id=tenant_id, detector=self.name, severity="P1",
                    metric="avg_qoe_score", current_value=round(avg, 2),
                    threshold=2.5, window_minutes=self.window_minutes,
                    source_table=f"{t}.npaw_analytics_logs",
                )]
            return []
        except Exception as exc:
            logger.debug("qoe_detector_error", error=str(exc))
            return []
