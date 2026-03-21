"""Tests for Akamai analyzer — metrics calculation and anomaly detection."""

from __future__ import annotations

from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry, AkamaiMetrics


def test_calculate_metrics_normal(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    assert metrics.total_requests == 10
    assert metrics.error_rate == 0.0  # all 200/304
    assert metrics.cache_hit_rate > 0.5  # mostly HITs
    assert metrics.total_bytes > 0
    assert len(metrics.status_breakdown) > 0
    assert len(metrics.geo_breakdown) > 0
    assert len(metrics.edge_breakdown) > 0


def test_calculate_metrics_spike(analyzer: AkamaiAnalyzer, spike_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(spike_entries)
    assert metrics.total_requests == 10
    assert metrics.error_rate == 0.7  # 7 errors out of 10
    assert metrics.cache_hit_rate < 0.5  # mostly MISSes
    assert len(metrics.top_errors) > 0


def test_calculate_metrics_empty(analyzer: AkamaiAnalyzer):
    metrics = analyzer.calculate_metrics([])
    assert metrics.total_requests == 0
    assert metrics.error_rate == 0.0


def test_detect_anomalies_normal(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    anomalies = analyzer.detect_anomalies(metrics)
    # Normal data: error_rate=0, cache_hit>0.6 → may get low_cache_hit or not
    high_error = [a for a in anomalies if a.anomaly_type == "high_error_rate"]
    assert len(high_error) == 0


def test_detect_anomalies_spike(analyzer: AkamaiAnalyzer, spike_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(spike_entries)
    anomalies = analyzer.detect_anomalies(metrics)
    # Spike data has 70% error rate, low cache hits
    types = [a.anomaly_type for a in anomalies]
    assert "high_error_rate" in types
    assert "low_cache_hit" in types

    # Check severity
    error_anomaly = next(a for a in anomalies if a.anomaly_type == "high_error_rate")
    assert error_anomaly.severity == "P1"
    assert error_anomaly.value == 0.7


def test_detect_anomalies_high_ttfb(analyzer: AkamaiAnalyzer):
    metrics = AkamaiMetrics(
        total_requests=100,
        error_rate=0.01,
        cache_hit_rate=0.9,
        avg_ttfb_ms=2500,
        p99_ttfb_ms=5000,
    )
    anomalies = analyzer.detect_anomalies(metrics)
    types = [a.anomaly_type for a in anomalies]
    assert "high_ttfb" in types


def test_get_period(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    start, end = analyzer.get_period(normal_entries)
    assert start < end


def test_get_period_empty(analyzer: AkamaiAnalyzer):
    start, end = analyzer.get_period([])
    assert start == end


def test_metrics_content_type_breakdown(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    # content_type may be empty for old CSV data but dict should exist
    assert isinstance(metrics.content_type_breakdown, dict)


def test_metrics_city_breakdown(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    assert len(metrics.city_breakdown) > 0
    assert all("city" in c and "requests" in c for c in metrics.city_breakdown)


def test_metrics_peak_hours(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    assert len(metrics.peak_hours) > 0
    assert all("hour" in p and "requests" in p for p in metrics.peak_hours)
