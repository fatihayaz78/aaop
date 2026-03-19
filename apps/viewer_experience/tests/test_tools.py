"""Tests for Viewer Experience tools — QoE scoring, dedup, complaints."""

from __future__ import annotations

import pytest

from apps.viewer_experience.schemas import QoESession
from apps.viewer_experience.tools import (
    categorize_complaint,
    compute_qoe_score,
    detect_qoe_anomaly,
    escalate_complaint,
    is_session_deduped,
    score_qoe_session,
)

# ── QoE Score Formula tests (exact match to spec Section 4) ──


def test_qoe_score_perfect():
    """Perfect session: no buffering, fast startup, high bitrate, no errors."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.0, startup_time_ms=1000, bitrate_avg=5000, errors=[])
    assert compute_qoe_score(s) == 5.0


def test_qoe_score_buffering():
    """Each 1% buffering = -0.1 (buffering_ratio * 10)."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.10, startup_time_ms=1000, bitrate_avg=5000, errors=[])
    assert compute_qoe_score(s) == 4.0  # 5.0 - 0.10*10 = 4.0


def test_qoe_score_startup_penalty():
    """Startup > 2000ms: penalty = (ms - 2000) / 1000."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.0, startup_time_ms=5000, bitrate_avg=5000, errors=[])
    assert compute_qoe_score(s) == 2.0  # 5.0 - (5000-2000)/1000 = 2.0


def test_qoe_score_startup_no_penalty():
    """Startup <= 2000ms: no penalty."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.0, startup_time_ms=1500, bitrate_avg=5000, errors=[])
    assert compute_qoe_score(s) == 5.0


def test_qoe_score_errors():
    """Each error = -0.3."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.0, startup_time_ms=1000, bitrate_avg=5000, errors=["err1", "err2"])
    assert compute_qoe_score(s) == 4.4  # 5.0 - 2*0.3 = 4.4


def test_qoe_score_low_bitrate():
    """Bitrate < 1500: penalty = (1500 - bitrate) / 1000."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.0, startup_time_ms=1000, bitrate_avg=500, errors=[])
    assert compute_qoe_score(s) == 4.0  # 5.0 - (1500-500)/1000 = 4.0


def test_qoe_score_combined_degradation():
    """Combined: buffering + startup + errors + low bitrate."""
    s = QoESession(
        tenant_id="t1", buffering_ratio=0.15, startup_time_ms=4000,
        bitrate_avg=1000, errors=["err1"],
    )
    # 5.0 - 0.15*10 - (4000-2000)/1000 - 0.3 - (1500-1000)/1000
    # = 5.0 - 1.5 - 2.0 - 0.3 - 0.5 = 0.7
    assert compute_qoe_score(s) == 0.7


def test_qoe_score_floor_zero():
    """Score cannot go below 0.0."""
    s = QoESession(tenant_id="t1", buffering_ratio=1.0, startup_time_ms=20000, bitrate_avg=100, errors=["e"] * 20)
    assert compute_qoe_score(s) == 0.0


def test_qoe_score_ceiling_five():
    """Score cannot exceed 5.0."""
    s = QoESession(tenant_id="t1", buffering_ratio=0.0, startup_time_ms=0, bitrate_avg=10000, errors=[])
    assert compute_qoe_score(s) == 5.0


# ── Session dedup tests ──


def test_session_dedup_first_time():
    assert is_session_deduped("sess-001") is False


def test_session_dedup_second_time():
    is_session_deduped("sess-002")
    assert is_session_deduped("sess-002") is True


def test_session_dedup_different_sessions():
    is_session_deduped("sess-003")
    assert is_session_deduped("sess-004") is False


# ── QoE anomaly detection ──


@pytest.mark.asyncio
async def test_detect_anomaly_degraded():
    s = QoESession(tenant_id="t1", quality_score=1.2, buffering_ratio=0.10, session_id="s1")
    anomaly = await detect_qoe_anomaly("t1", s)
    assert anomaly is not None
    assert anomaly.quality_score == 1.2
    assert anomaly.severity == "P1"


@pytest.mark.asyncio
async def test_detect_anomaly_normal():
    s = QoESession(tenant_id="t1", quality_score=4.5)
    anomaly = await detect_qoe_anomaly("t1", s)
    assert anomaly is None


@pytest.mark.asyncio
async def test_detect_anomaly_p2():
    s = QoESession(tenant_id="t1", quality_score=2.0, buffering_ratio=0.06, session_id="s2")
    anomaly = await detect_qoe_anomaly("t1", s)
    assert anomaly is not None
    assert anomaly.severity == "P2"


# ── Complaint categorization ──


@pytest.mark.asyncio
async def test_categorize_buffering():
    result = await categorize_complaint("t1", "Video sürekli donuyor, buffer yapıyor")
    assert result.category == "buffering"


@pytest.mark.asyncio
async def test_categorize_video_quality():
    result = await categorize_complaint("t1", "Video kalitesi çok kötü, piksel piksel")
    assert result.category == "video_quality"
    assert result.sentiment == "negative"


@pytest.mark.asyncio
async def test_categorize_audio():
    result = await categorize_complaint("t1", "Ses gelmiyor, audio problemi var")
    assert result.category == "audio"


@pytest.mark.asyncio
async def test_categorize_other():
    result = await categorize_complaint("t1", "Genel bir sorunum var")
    assert result.category == "other"


# ── Score tool ──


@pytest.mark.asyncio
async def test_score_qoe_session():
    s = QoESession(tenant_id="t1", buffering_ratio=0.05, startup_time_ms=3000, bitrate_avg=3000, errors=[])
    result = await score_qoe_session("t1", s)
    assert result.quality_score == 3.5  # 5.0 - 0.5 - 1.0 = 3.5


# ── Escalation ──


@pytest.mark.asyncio
async def test_escalate_complaint_approval():
    result = await escalate_complaint("t1", "CMP-001", "Repeated complaint")
    assert result["status"] == "approval_required"
