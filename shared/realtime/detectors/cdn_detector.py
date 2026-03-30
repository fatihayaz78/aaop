"""CDN Detector — Medianova error rate spike detection."""

from __future__ import annotations

import structlog

from shared.realtime.detectors.base_detector import AnomalyEvent, BaseDetector

logger = structlog.get_logger(__name__)


class CDNDetector(BaseDetector):
    name = "cdn_detector"
    poll_interval_seconds = 30
    window_minutes = 5

    async def check(self, tenant_id: str, schema: str) -> list[AnomalyEvent]:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")

            rows = _safe_query(db, tenant_id, f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
                FROM {t}.medianova_logs
                WHERE tenant_id = '{tenant_id}'
                  AND timestamp >= NOW() - INTERVAL {self.window_minutes} MINUTE
            """)

            if not rows or rows[0]["total"] == 0:
                return []

            error_rate = rows[0]["errors"] / rows[0]["total"]
            anomalies = []

            if error_rate > 0.15:
                anomalies.append(AnomalyEvent(
                    tenant_id=tenant_id, detector=self.name, severity="P0",
                    metric="error_rate", current_value=round(error_rate, 4),
                    threshold=0.15, window_minutes=self.window_minutes,
                    source_table=f"{t}.medianova_logs",
                ))
            elif error_rate > 0.05:
                anomalies.append(AnomalyEvent(
                    tenant_id=tenant_id, detector=self.name, severity="P1",
                    metric="error_rate", current_value=round(error_rate, 4),
                    threshold=0.05, window_minutes=self.window_minutes,
                    source_table=f"{t}.medianova_logs",
                ))

            return anomalies
        except Exception as exc:
            logger.debug("cdn_detector_error", error=str(exc))
            return []
