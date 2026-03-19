"""Tests for Akamai DOCX report generation."""

from __future__ import annotations

from pathlib import Path

from apps.log_analyzer.config import LogAnalyzerConfig
from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.reporter import AkamaiReporter
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiAnomaly, AkamaiLogEntry, AkamaiMetrics


def test_generate_report(log_analyzer_config: LogAnalyzerConfig, analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    anomalies = analyzer.detect_anomalies(metrics)
    reporter = AkamaiReporter(log_analyzer_config)
    path = reporter.generate(tenant_id="test_tenant", metrics=metrics, anomalies=anomalies)
    assert Path(path).exists()
    assert path.endswith(".docx")


def test_generate_report_with_anomalies(log_analyzer_config: LogAnalyzerConfig):
    metrics = AkamaiMetrics(
        total_requests=1000,
        error_rate=0.08,
        cache_hit_rate=0.45,
        avg_ttfb_ms=1500,
        p99_ttfb_ms=4000,
        top_errors=[{"code": "ERR_CONNECT_FAIL", "count": 80, "pct": 8.0}],
    )
    anomalies = [
        AkamaiAnomaly(anomaly_type="high_error_rate", severity="P1", value=0.08, threshold=0.05, description="Error rate 8%"),
        AkamaiAnomaly(anomaly_type="low_cache_hit", severity="P2", value=0.45, threshold=0.60, description="Low cache"),
    ]
    reporter = AkamaiReporter(log_analyzer_config)
    path = reporter.generate(tenant_id="bein_sports", metrics=metrics, anomalies=anomalies, agent_summary="Critical CDN issue detected.")
    assert Path(path).exists()


def test_generate_report_no_anomalies(log_analyzer_config: LogAnalyzerConfig):
    metrics = AkamaiMetrics(total_requests=500, error_rate=0.01, cache_hit_rate=0.95)
    reporter = AkamaiReporter(log_analyzer_config)
    path = reporter.generate(tenant_id="test_tenant", metrics=metrics, anomalies=[])
    assert Path(path).exists()


def test_report_in_tenant_dir(log_analyzer_config: LogAnalyzerConfig):
    metrics = AkamaiMetrics(total_requests=100)
    reporter = AkamaiReporter(log_analyzer_config)
    path = reporter.generate(tenant_id="my_tenant", metrics=metrics, anomalies=[])
    assert "my_tenant" in path
