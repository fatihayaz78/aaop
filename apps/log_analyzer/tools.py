"""Log Analyzer tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.log_analyzer.config import LogAnalyzerConfig
from apps.log_analyzer.schemas import AnalysisResult
from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.charts import generate_all_charts
from apps.log_analyzer.sub_modules.akamai.parser import parse_auto
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry, AkamaiMetrics

logger = structlog.get_logger(__name__)

# Risk levels: LOW = auto, MEDIUM = auto+notify, HIGH = approval_required


# ── LOW risk tools ──────────────────────────────────────


async def list_log_projects(tenant_id: str, db: Any) -> list[dict]:
    """List all log projects for a tenant. Risk: LOW."""
    rows = await db.fetch_all("SELECT * FROM log_projects WHERE tenant_id = ?", (tenant_id,))
    return rows


async def get_analysis_history(tenant_id: str, db: Any, limit: int = 20) -> list[dict]:
    """Get recent analysis results. Risk: LOW."""
    return db.fetch_all(
        "SELECT * FROM shared_analytics.cdn_analysis WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
        [tenant_id, limit],
    )


async def fetch_s3_logs(tenant_id: str, bucket: str, prefix: str) -> list[AkamaiLogEntry]:
    """Fetch logs from S3. Risk: LOW."""
    import boto3

    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=100)
    entries: list[AkamaiLogEntry] = []
    for obj in response.get("Contents", []):
        body = s3.get_object(Bucket=bucket, Key=obj["Key"])
        content = body["Body"].read().decode("utf-8")
        entries.extend(parse_auto(content))
    logger.info("s3_logs_fetched", tenant_id=tenant_id, count=len(entries))
    return entries


async def parse_akamai_logs(tenant_id: str, content: str) -> list[AkamaiLogEntry]:
    """Parse raw log content. Risk: LOW."""
    entries = parse_auto(content)
    logger.info("akamai_logs_parsed", tenant_id=tenant_id, count=len(entries))
    return entries


async def calculate_error_metrics(tenant_id: str, logs: list[AkamaiLogEntry]) -> AkamaiMetrics:
    """Calculate metrics from parsed logs. Risk: LOW."""
    config = LogAnalyzerConfig()
    analyzer = AkamaiAnalyzer(config)
    metrics = analyzer.calculate_metrics(logs)
    logger.info("metrics_calculated", tenant_id=tenant_id, total_requests=metrics.total_requests)
    return metrics


async def detect_anomalies(tenant_id: str, metrics: AkamaiMetrics) -> list[dict]:
    """Detect anomalies from metrics. Risk: LOW."""
    config = LogAnalyzerConfig()
    analyzer = AkamaiAnalyzer(config)
    anomalies = analyzer.detect_anomalies(metrics)
    logger.info("anomalies_detected", tenant_id=tenant_id, count=len(anomalies))
    return [a.model_dump() for a in anomalies]


async def generate_charts(tenant_id: str, metrics: AkamaiMetrics, logs: list[AkamaiLogEntry]) -> dict:
    """Generate all 21 charts. Risk: LOW."""
    charts = generate_all_charts(metrics, logs)
    logger.info("charts_generated", tenant_id=tenant_id, count=len(charts))
    return charts


async def search_similar_anomalies(tenant_id: str, anomaly_type: str, db: Any) -> list[dict]:
    """Search DuckDB for similar past anomalies. Risk: LOW."""
    return db.fetch_all(
        """SELECT * FROM shared_analytics.cdn_analysis
        WHERE tenant_id = ? AND anomalies::VARCHAR LIKE ?
        ORDER BY created_at DESC LIMIT 10""",
        [tenant_id, f"%{anomaly_type}%"],
    )


# ── MEDIUM risk tools ───────────────────────────────────


async def write_analysis_to_db(tenant_id: str, result: AnalysisResult, db: Any) -> str:
    """Write analysis to DuckDB cdn_analysis. Risk: MEDIUM (auto+notify)."""
    db.execute(
        """INSERT INTO shared_analytics.cdn_analysis
        (analysis_id, tenant_id, project_id, sub_module, analysis_time,
         period_start, period_end, total_requests, error_rate, cache_hit_rate,
         avg_ttfb_ms, p99_ttfb_ms, top_errors, edge_breakdown, anomalies,
         agent_summary, report_path)
        VALUES (?, ?, ?, ?, NOW(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            result.analysis_id, tenant_id, result.project_id, result.sub_module,
            result.period_start.isoformat() if result.period_start else None,
            result.period_end.isoformat() if result.period_end else None,
            result.total_requests, result.error_rate, result.cache_hit_rate,
            result.avg_ttfb_ms, result.p99_ttfb_ms,
            str(result.top_errors), str(result.edge_breakdown),
            str(result.anomalies), result.agent_summary, result.report_path,
        ],
    )
    logger.info("analysis_written_to_db", tenant_id=tenant_id, analysis_id=result.analysis_id)
    return result.analysis_id


async def generate_docx_report(
    tenant_id: str,
    metrics: AkamaiMetrics,
    anomalies: list[dict],
    charts: dict | None = None,
    agent_summary: str | None = None,
) -> str:
    """Generate DOCX report. Risk: MEDIUM (auto+notify)."""
    from apps.log_analyzer.sub_modules.akamai.reporter import AkamaiReporter
    from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiAnomaly

    config = LogAnalyzerConfig()
    reporter = AkamaiReporter(config)
    anomaly_objs = [AkamaiAnomaly(**a) for a in anomalies]
    path = reporter.generate(
        tenant_id=tenant_id,
        metrics=metrics,
        anomalies=anomaly_objs,
        charts=charts,
        agent_summary=agent_summary,
    )
    logger.info("docx_report_generated", tenant_id=tenant_id, path=path)
    return path


async def trigger_cdn_alert(tenant_id: str, anomalies: list[dict], event_bus: Any) -> None:
    """Publish cdn_anomaly_detected event. Risk: MEDIUM (auto+notify)."""
    from shared.event_bus import EventType
    from shared.schemas.base_event import BaseEvent, SeverityLevel

    severity = SeverityLevel.P2
    for a in anomalies:
        if a.get("severity") == "P1":
            severity = SeverityLevel.P1
        if a.get("severity") == "P0":
            severity = SeverityLevel.P0

    event = BaseEvent(
        event_type=EventType.CDN_ANOMALY_DETECTED,
        tenant_id=tenant_id,
        source_app="log_analyzer",
        severity=severity,
        payload={"anomalies": anomalies},
    )
    await event_bus.publish(event)
    logger.info("cdn_alert_triggered", tenant_id=tenant_id, severity=severity)


# ── HIGH risk tools ─────────────────────────────────────


async def purge_cdn_cache(tenant_id: str, paths: list[str]) -> dict:
    """Purge CDN cache for given paths. Risk: HIGH (approval_required)."""
    logger.warning("purge_cdn_cache_requested", tenant_id=tenant_id, paths=paths)
    return {"status": "approval_required", "tenant_id": tenant_id, "paths": paths}
