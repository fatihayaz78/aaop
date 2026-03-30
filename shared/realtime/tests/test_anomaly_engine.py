"""Tests for real-time anomaly engine and detectors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.realtime.anomaly_engine import AnomalyEngine
from shared.realtime.detectors.api_detector import APIDetector
from shared.realtime.detectors.base_detector import AnomalyEvent
from shared.realtime.detectors.cdn_detector import CDNDetector
from shared.realtime.detectors.drm_detector import DRMDetector
from shared.realtime.detectors.qoe_detector import QoEDetector


def _mock_safe_query(return_value):
    """Create a mock for _safe_query that returns given data."""
    return MagicMock(return_value=return_value)


def _mock_logs_db():
    return MagicMock()


# ── CDN Detector ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_cdn_high_error_rate():
    d = CDNDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"total": 1000, "errors": 200}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 1
    assert events[0].severity == "P0"


@pytest.mark.asyncio
async def test_cdn_medium_error_rate():
    d = CDNDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"total": 1000, "errors": 80}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 1
    assert events[0].severity == "P1"


@pytest.mark.asyncio
async def test_cdn_normal():
    d = CDNDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"total": 1000, "errors": 20}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 0


# ── DRM Detector ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_drm_failure_spike():
    d = DRMDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"total": 500, "failures": 60}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) >= 1
    assert events[0].severity == "P1"


# ── QoE Detector ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_qoe_critical():
    d = QoEDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"avg_score": 1.2, "cnt": 100}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 1
    assert events[0].severity == "P0"


@pytest.mark.asyncio
async def test_qoe_degraded():
    d = QoEDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"avg_score": 2.0, "cnt": 100}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 1
    assert events[0].severity == "P1"


@pytest.mark.asyncio
async def test_qoe_normal():
    d = QoEDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"avg_score": 4.2, "cnt": 100}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 0


# ── API Detector ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_error_spike():
    d = APIDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"total": 1000, "errors": 80, "p99": 500}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 1
    assert events[0].metric == "error_rate"


@pytest.mark.asyncio
async def test_api_latency_spike():
    d = APIDetector()
    with patch("shared.ingest.log_queries._safe_query", return_value=[{"total": 1000, "errors": 10, "p99": 3500}]), \
         patch("shared.ingest.log_queries._get_logs_db", return_value=_mock_logs_db()):
        events = await d.check("t1", "sport_stream")
    assert len(events) == 1
    assert events[0].metric == "p99_latency_ms"


# ── Engine ───────────────────────────────────────────────

def test_engine_status():
    engine = AnomalyEngine(tenant_id="t1", schema="sport_stream")
    status = engine.get_status()
    assert status["running"] is False
    assert len(status["detectors"]) == 4


def test_engine_toggle():
    engine = AnomalyEngine()
    assert engine.toggle_detector("cdn_detector", False) is True
    assert engine.detectors[0].enabled is False
    assert engine.toggle_detector("nonexistent", False) is False


def test_anomaly_event_model():
    e = AnomalyEvent(
        tenant_id="t1", detector="cdn_detector", severity="P0",
        metric="error_rate", current_value=0.20, threshold=0.15,
    )
    assert e.severity == "P0"
    assert e.event_id


def test_engine_get_recent():
    engine = AnomalyEngine()
    assert engine.get_recent(60) == []
