"""Tests for shared/llm_gateway.py."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.llm_gateway import DEFAULT_MODEL, MODEL_ROUTING, LLMGateway
from shared.schemas.base_event import SeverityLevel


def test_model_routing():
    assert MODEL_ROUTING[SeverityLevel.P0] == "claude-opus-4-20250514"
    assert MODEL_ROUTING[SeverityLevel.P1] == "claude-opus-4-20250514"
    assert MODEL_ROUTING[SeverityLevel.P2] == "claude-sonnet-4-20250514"
    assert MODEL_ROUTING[SeverityLevel.P3] == "claude-haiku-4-5-20251001"


def test_select_model_default(mock_llm_gateway: LLMGateway):
    assert mock_llm_gateway.select_model() == DEFAULT_MODEL


def test_select_model_p0(mock_llm_gateway: LLMGateway):
    assert mock_llm_gateway.select_model(SeverityLevel.P0) == "claude-opus-4-20250514"


def test_select_model_p3(mock_llm_gateway: LLMGateway):
    assert mock_llm_gateway.select_model(SeverityLevel.P3) == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_invoke(mock_llm_gateway: LLMGateway):
    result = await mock_llm_gateway.invoke("What is the error rate?", use_cache=False)
    assert result["content"] == "Mock LLM response"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50


@pytest.mark.asyncio
async def test_token_tracking(mock_llm_gateway: LLMGateway):
    await mock_llm_gateway.invoke("query 1", use_cache=False)
    await mock_llm_gateway.invoke("query 2", use_cache=False)
    tokens = mock_llm_gateway.total_tokens
    assert tokens["input"] == 200
    assert tokens["output"] == 100
    assert tokens["total"] == 300


def test_cache_key_deterministic(mock_llm_gateway: LLMGateway):
    key1 = mock_llm_gateway._cache_key("hello", "model-a")
    key2 = mock_llm_gateway._cache_key("hello", "model-a")
    key3 = mock_llm_gateway._cache_key("hello", "model-b")
    assert key1 == key2
    assert key1 != key3


@pytest.mark.asyncio
async def test_invoke_with_system_prompt(mock_llm_gateway: LLMGateway):
    result = await mock_llm_gateway.invoke(
        "test prompt",
        system_prompt="You are a CDN expert.",
        use_cache=False,
    )
    assert result["content"] == "Mock LLM response"
    # Verify system prompt was passed
    call_kwargs = mock_llm_gateway._anthropic.messages.create.call_args
    assert call_kwargs.kwargs.get("system") == "You are a CDN expert."


@pytest.mark.asyncio
async def test_invoke_with_severity(mock_llm_gateway: LLMGateway):
    result = await mock_llm_gateway.invoke("critical issue", severity=SeverityLevel.P0, use_cache=False)
    assert result["model"] == "claude-opus-4-20250514"


@pytest.mark.asyncio
async def test_invoke_cache_hit(mock_llm_gateway: LLMGateway):
    # Simulate cache hit
    mock_llm_gateway._redis.get_json = AsyncMock(
        return_value={"content": "cached response", "model": "test", "input_tokens": 0, "output_tokens": 0}
    )
    result = await mock_llm_gateway.invoke("test", use_cache=True)
    assert result["content"] == "cached response"
    # LLM should not be called
    mock_llm_gateway._anthropic.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_invoke_cache_store(mock_llm_gateway: LLMGateway):
    mock_llm_gateway._redis.get_json = AsyncMock(return_value=None)
    mock_llm_gateway._redis.set_json = AsyncMock()
    result = await mock_llm_gateway.invoke("new query", use_cache=True)
    assert result["content"] == "Mock LLM response"
    mock_llm_gateway._redis.set_json.assert_called_once()
