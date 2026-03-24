"""Tests for Agent Chat — context building, suggestions, mocked LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.routers.log_analyzer import (
    _build_chat_context,
    _fetch_jobs,
    _generate_suggestions,
)


# ── Context building ──


def test_chat_no_job():
    """No job_id → generic context."""
    ctx = _build_chat_context(None)
    assert "No analysis data" in ctx


def test_chat_with_job_context():
    """Job in memory → context includes metrics."""
    job_id = "test-chat-job"
    _fetch_jobs[job_id] = {
        "job_id": job_id,
        "status": "completed",
        "start_date": "2026-03-23",
        "end_date": "2026-03-24",
        "rows_parsed": 125000,
        "total_files": 48,
        "cache_hits": 1,
        "cache_misses": 1,
    }

    ctx = _build_chat_context(job_id)
    assert "2026-03-23" in ctx
    assert "125,000" in ctx
    assert "completed" in ctx

    del _fetch_jobs[job_id]


def test_chat_missing_job():
    """Job not in memory → fallback message."""
    ctx = _build_chat_context("nonexistent-job-id")
    assert "not available" in ctx


# ── Suggestions ──


def test_suggestions_no_job():
    """No job → generic suggestions."""
    suggestions = _generate_suggestions(None)
    assert len(suggestions) == 4
    assert any("Summarize" in s for s in suggestions)


def test_suggestions_with_job():
    """Job in memory → includes context-aware suggestions."""
    job_id = "test-suggest-job"
    _fetch_jobs[job_id] = {
        "job_id": job_id,
        "status": "completed",
        "parquet_paths": [],  # No parquet → will fall back to generic
    }

    suggestions = _generate_suggestions(job_id)
    assert len(suggestions) == 4
    assert any("Summarize" in s or "investigate" in s for s in suggestions)

    del _fetch_jobs[job_id]


# ── Chat endpoint (mocked LLM) ──


@pytest.mark.asyncio
async def test_chat_endpoint_mocked():
    """Chat endpoint returns response with mocked Anthropic client."""
    from backend.routers.log_analyzer import chat, ChatRequest
    from shared.schemas.base_event import TenantContext

    ctx = TenantContext(tenant_id="test_tenant")
    payload = ChatRequest(message="What is the error rate?", job_id=None, history=[])

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="The error rate is 3.2%.")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = "sk-test-key"

    with patch("backend.routers.log_analyzer.get_settings", return_value=mock_settings), \
         patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result = await chat(payload=payload, ctx=ctx)

    assert "error rate" in result["response"].lower() or "3.2" in result["response"]
    assert result["conversation_id"]


@pytest.mark.asyncio
async def test_chat_no_api_key():
    """No API key → clear error message."""
    from backend.routers.log_analyzer import chat, ChatRequest
    from shared.schemas.base_event import TenantContext

    ctx = TenantContext(tenant_id="test_tenant")
    payload = ChatRequest(message="Hello", history=[])

    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = ""

    with patch("backend.routers.log_analyzer.get_settings", return_value=mock_settings):
        result = await chat(payload=payload, ctx=ctx)

    assert "not configured" in result["response"].lower() or "API key" in result["response"]
