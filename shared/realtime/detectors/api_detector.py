"""API Detector — API gateway error rate and latency spike detection."""

from __future__ import annotations

import structlog

from shared.realtime.detectors.base_detector import AnomalyEvent, BaseDetector

logger = structlog.get_logger(__name__)


class APIDetector(BaseDetector):
    name = "api_detector"
    poll_interval_seconds = 30
    window_minutes = 5

    async def check(self, tenant_id: str, schema: str) -> list[AnomalyEvent]:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")
            anomalies = []

            rows = _safe_query(db, tenant_id, f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors,
                       PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99
                FROM {t}.api_logs_logs
                WHERE tenant_id = '{tenant_id}'
                  AND timestamp >= NOW() - INTERVAL {self.window_minutes} MINUTE
            """)

            if not rows or rows[0]["total"] == 0:
                return anomalies

            error_rate = rows[0]["errors"] / rows[0]["total"]
            p99 = rows[0]["p99"] or 0

            if error_rate > 0.05:
                anomalies.append(AnomalyEvent(
                    tenant_id=tenant_id, detector=self.name, severity="P2",
                    metric="error_rate", current_value=round(error_rate, 4),
                    threshold=0.05, window_minutes=self.window_minutes,
                    source_table=f"{t}.api_logs_logs",
                ))

            if p99 > 2000:
                anomalies.append(AnomalyEvent(
                    tenant_id=tenant_id, detector=self.name, severity="P2",
                    metric="p99_latency_ms", current_value=round(p99, 1),
                    threshold=2000.0, window_minutes=self.window_minutes,
                    source_table=f"{t}.api_logs_logs",
                ))

            return anomalies
        except Exception as exc:
            logger.debug("api_detector_error", error=str(exc))
            return []
