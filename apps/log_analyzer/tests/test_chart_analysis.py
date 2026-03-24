"""Tests for chart analysis aggregation functions."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.routers.log_analyzer import _run_analysis


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample DataFrame mimicking parsed Akamai log entries."""
    return pd.DataFrame([
        {"status_code": 200, "cache_hit": 1, "bytes": 50000, "client_bytes": 40000,
         "transfer_time_ms": 120, "country": "TR", "content_type": "video/mp4",
         "cache_status": 1, "req_time_sec": 1711000000.0, "req_path": "/live/stream.m3u8"},
        {"status_code": 200, "cache_hit": 1, "bytes": 60000, "client_bytes": 55000,
         "transfer_time_ms": 80, "country": "TR", "content_type": "video/mp4",
         "cache_status": 1, "req_time_sec": 1711003600.0, "req_path": "/live/stream.m3u8"},
        {"status_code": 404, "cache_hit": 0, "bytes": 500, "client_bytes": 500,
         "transfer_time_ms": 5, "country": "DE", "content_type": "text/html",
         "cache_status": 0, "req_time_sec": 1711007200.0, "req_path": "/missing.html"},
        {"status_code": 503, "cache_hit": 0, "bytes": 200, "client_bytes": 200,
         "transfer_time_ms": 2000, "country": "US", "content_type": "text/html",
         "cache_status": 0, "req_time_sec": 1711010800.0, "req_path": "/api/health"},
    ])


def test_analysis_summary(sample_df: pd.DataFrame):
    """Summary metrics are calculated correctly."""
    result = _run_analysis(sample_df)
    s = result["summary"]

    assert s["total_rows"] == 4
    assert s["error_rate_pct"] == 50.0  # 2 errors out of 4
    assert s["cache_hit_pct"] == 50.0   # 2 hits out of 4
    assert s["unique_countries"] == 3   # TR, DE, US
    assert s["avg_latency_ms"] > 0


def test_analysis_charts_present(sample_df: pd.DataFrame):
    """All 10 chart types are generated."""
    result = _run_analysis(sample_df)
    charts = result["charts"]

    expected_charts = [
        "status_code_distribution", "cache_hit_ratio", "bandwidth_by_hour",
        "top_error_paths", "latency_percentiles", "geo_distribution",
        "content_type_breakdown", "cache_status_breakdown", "error_rate_trend",
        "bytes_vs_client",
    ]
    for chart_key in expected_charts:
        assert chart_key in charts, f"Missing chart: {chart_key}"
        assert len(charts[chart_key]) > 0, f"Empty chart: {chart_key}"


def test_analysis_empty_df():
    """Empty DataFrame returns empty summary and charts."""
    result = _run_analysis(pd.DataFrame())
    assert result["summary"] == {}
    assert result["charts"] == {}


def test_latency_percentiles(sample_df: pd.DataFrame):
    """Latency percentiles are ordered correctly."""
    result = _run_analysis(sample_df)
    percs = result["charts"]["latency_percentiles"]

    assert len(percs) == 4
    labels = [p["percentile"] for p in percs]
    assert labels == ["p50", "p75", "p95", "p99"]
    # p99 should be >= p50
    assert percs[3]["ms"] >= percs[0]["ms"]
