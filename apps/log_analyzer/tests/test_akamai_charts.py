"""Tests for Akamai chart generation."""

from __future__ import annotations

import plotly.graph_objects as go

from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.charts import generate_all_charts
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry, AkamaiMetrics


def test_generate_all_charts(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    charts = generate_all_charts(metrics, normal_entries)
    assert len(charts) == 21
    for name, fig in charts.items():
        assert isinstance(fig, go.Figure), f"{name} is not a Figure"


def test_chart_names(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    charts = generate_all_charts(metrics, normal_entries)
    expected = {
        "error_rate_timeseries", "cache_hit_rate", "byte_transfer",
        "request_volume", "ttfb_histogram", "http_status_pie",
        "top_edges", "geo_distribution", "tls_version", "protocol_dist",
        "top_error_paths", "cache_status", "bandwidth_vs_error",
        "peak_hour_heatmap", "origin_vs_edge", "request_size_dist",
        "response_size_dist", "error_rate_by_edge", "ttfb_trend",
        "request_by_content_type", "anomaly_timeline",
    }
    assert set(charts.keys()) == expected


def test_charts_with_spike_data(analyzer: AkamaiAnalyzer, spike_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(spike_entries)
    charts = generate_all_charts(metrics, spike_entries)
    assert len(charts) == 21


def test_charts_empty_data():
    metrics = AkamaiMetrics()
    charts = generate_all_charts(metrics, [])
    assert len(charts) == 21
