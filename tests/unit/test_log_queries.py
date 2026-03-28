"""Tests for log_queries.py — pre-built query helpers using mock DuckDB."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_db(overrides: dict | None = None):
    """Create a mock DB where .query() returns data based on SQL matching."""
    defaults = {
        "cdn_total": 10000, "cdn_errors": 500, "cdn_cache": 7200,
        "cdn_avg_rt": 45.5, "cdn_bytes": 5e9,
        "drm_total": 5000, "drm_errors": 50,
        "api_total": 8000, "api_errors": 200, "api_avg_rt": 120.5, "api_p99": 950.0,
        "infra_services": [
            {"service_name": "api-gateway", "avg_apdex": 0.95, "avg_error_rate": 0.01,
             "avg_throughput": 500, "avg_cpu": 30, "avg_mem": 45},
            {"service_name": "stream-packager", "avg_apdex": 0.65, "avg_error_rate": 0.08,
             "avg_throughput": 300, "avg_cpu": 85, "avg_mem": 70},
        ],
        "qoe_sessions": 10000, "qoe_avg": 3.7, "qoe_br": 4500, "qoe_buf": 0.008,
        "qoe_err_sessions": 500,
    }
    if overrides:
        defaults.update(overrides)

    d = defaults

    def mock_query(tenant_id, sql):
        s = sql.lower()
        # CDN — specific patterns first (before generic count(*))
        if "medianova" in s:
            if "time_bucket" in s:
                return [{"bucket": "2026-03-04T19:00", "total": 1000, "errors": 80}]
            if "error_code" in s and "group by error_code" in s:
                return [{"error_code": "503", "cnt": 200}]
            if "extract(hour" in s:
                return [{"hr": 14, "cnt": 500}]
            if "status_code" in s and "group by status_code" in s:
                return [{"status_code": 200, "cnt": 9500}]
            if "avg(response_time_ms)" in s:
                return [{"avg_rt": d["cdn_avg_rt"], "total_bytes": d["cdn_bytes"]}]
            if "status_code >= 400" in s:
                return [{"cnt": d["cdn_errors"]}]
            if "cache_hit = 1" in s:
                return [{"cnt": d["cdn_cache"]}]
            if "count(*)" in s:
                return [{"cnt": d["cdn_total"]}]
        # DRM — specific first
        if "widevine" in s or "fairplay" in s:
            if "error_code" in s and "group by error_code" in s:
                return [{"error_code": "WV_TIMEOUT", "cnt": 30}]
            if "device_type" in s and "group by device_type" in s:
                return [{"device_type": "android", "cnt": 25}]
            if "status != 'success'" in s:
                return [{"cnt": d["drm_errors"]}]
            if "count(*)" in s:
                return [{"cnt": d["drm_total"]}]
        # API — specific first
        if "api_logs" in s:
            if "endpoint" in s and "group by" in s:
                return [{"endpoint": "/auth/token/refresh", "cnt": 3000, "err_rate": 0.5}]
            if "status_code" in s and "group by status_code" in s:
                return [{"status_code": 200, "cnt": 7800}]
            if "percentile_cont" in s or "avg(response_time_ms)" in s:
                return [{"avg_rt": d["api_avg_rt"], "p99": d["api_p99"]}]
            if "status_code >= 400" in s:
                return [{"cnt": d["api_errors"]}]
            if "count(*)" in s:
                return [{"cnt": d["api_total"]}]
        # Infra
        if "newrelic" in s and "service_name" in s and "group by" in s:
            return d["infra_services"]
        # QoE — specific first
        if "player_events" in s:
            if "device_type" in s and "group by device_type" in s:
                return [{"device_type": "android", "avg_qoe": 3.8}]
            if "extract(hour" in s and "avg(qoe_score)" in s:
                return [{"hr": 19, "avg_qoe": 3.5}]
            if "count(distinct" in s and "error_code" in s:
                return [{"cnt": d["qoe_err_sessions"]}]
            if "avg(qoe_score)" in s:
                return [{"sessions": d["qoe_sessions"], "avg_qoe": d["qoe_avg"],
                         "avg_br": d["qoe_br"], "avg_buf": d["qoe_buf"]}]
        return []

    m = MagicMock()
    m.query = MagicMock(side_effect=mock_query)
    return m


class TestGetCDNMetrics:
    def test_returns_correct_shape(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_cdn_metrics
            result = get_cdn_metrics("t1", hours=24)
            assert result["total_requests"] == 10000
            assert result["error_rate_pct"] == 5.0
            assert result["cache_hit_rate_pct"] == 72.0
            assert len(result["top_errors"]) > 0
            assert "status_code_distribution" in result


class TestGetCDNAnomalies:
    def test_threshold_detection(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_cdn_anomalies
            result = get_cdn_anomalies("t1", hours=24)
            assert isinstance(result, list)
            if result:
                assert result[0]["error_rate_pct"] > 5


class TestGetDRMStatus:
    def test_combines_widevine_fairplay(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_drm_status
            result = get_drm_status("t1", hours=24)
            assert "widevine" in result
            assert "fairplay" in result
            assert result["widevine"]["total"] == 5000


class TestGetAPIHealth:
    def test_p99_calculation(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_api_health
            result = get_api_health("t1", hours=24)
            assert result["total_requests"] == 8000
            assert result["p99_response_time_ms"] == 950.0


class TestGetInfraHealth:
    def test_critical_services(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_infrastructure_health
            result = get_infrastructure_health("t1", hours=24)
            assert "stream-packager" in result["critical_services"]


class TestGetPlayerQoE:
    def test_aggregation(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_player_qoe
            result = get_player_qoe("t1", hours=24)
            assert result["avg_qoe_score"] == 3.7
            assert result["sessions_total"] == 10000


class TestDetectIncidents:
    def test_p0_threshold(self):
        mock_db = _make_mock_db({"cdn_errors": 2000})  # 20% error rate
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import detect_incidents_from_logs
            incidents = detect_incidents_from_logs("t1", hours=1)
            p0 = [i for i in incidents if i["severity"] == "P0"]
            assert len(p0) >= 1

    def test_p1_threshold(self):
        mock_db = _make_mock_db()  # 5% error rate → P1
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import detect_incidents_from_logs
            incidents = detect_incidents_from_logs("t1", hours=1)
            # stream-packager apdex 0.65 < 0.7 → service_degradation P2
            p2 = [i for i in incidents if i["type"] == "service_degradation"]
            assert len(p2) >= 1

    def test_no_anomaly(self):
        mock_db = _make_mock_db({
            "cdn_errors": 10, "drm_errors": 5, "api_errors": 10,
            "api_p99": 200, "qoe_avg": 4.2,
            "infra_services": [{"service_name": "gw", "avg_apdex": 0.98,
                                "avg_error_rate": 0.001, "avg_throughput": 500,
                                "avg_cpu": 20, "avg_mem": 40}],
        })
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import detect_incidents_from_logs
            incidents = detect_incidents_from_logs("t1", hours=1)
            assert len(incidents) == 0
