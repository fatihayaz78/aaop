"""DRM Detector — Widevine/FairPlay failure spike detection."""

from __future__ import annotations

import structlog

from shared.realtime.detectors.base_detector import AnomalyEvent, BaseDetector

logger = structlog.get_logger(__name__)


class DRMDetector(BaseDetector):
    name = "drm_detector"
    poll_interval_seconds = 30
    window_minutes = 5

    async def check(self, tenant_id: str, schema: str) -> list[AnomalyEvent]:
        try:
            from shared.ingest.log_queries import _get_logs_db, _safe_query
            db = _get_logs_db()
            t = schema.replace("-", "_")
            anomalies = []

            for table in [f"{t}.widevine_drm_logs", f"{t}.fairplay_drm_logs"]:
                rows = _safe_query(db, tenant_id, f"""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN status = 'error' OR error_code != '' THEN 1 ELSE 0 END) as failures
                    FROM {table}
                    WHERE tenant_id = '{tenant_id}'
                      AND timestamp >= NOW() - INTERVAL {self.window_minutes} MINUTE
                """)
                if not rows or rows[0]["total"] == 0:
                    continue

                failure_rate = rows[0]["failures"] / rows[0]["total"]
                if failure_rate > 0.10:
                    anomalies.append(AnomalyEvent(
                        tenant_id=tenant_id, detector=self.name, severity="P1",
                        metric="failure_rate", current_value=round(failure_rate, 4),
                        threshold=0.10, window_minutes=self.window_minutes,
                        source_table=table,
                    ))

            return anomalies
        except Exception as exc:
            logger.debug("drm_detector_error", error=str(exc))
            return []
