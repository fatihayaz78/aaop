"""LLM Gateway — severity-based model routing, retry, Redis cache, cost tracking."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.clients.redis_client import RedisClient
from shared.schemas.base_event import SeverityLevel
from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)

MODEL_ROUTING: dict[SeverityLevel, str] = {
    SeverityLevel.P0: "claude-opus-4-20250514",
    SeverityLevel.P1: "claude-opus-4-20250514",
    SeverityLevel.P2: "claude-sonnet-4-20250514",
    SeverityLevel.P3: "claude-haiku-4-5-20251001",
}

DEFAULT_MODEL = "claude-sonnet-4-20250514"

CACHE_TTL = 86400  # 24 hours


class LLMGateway:
    def __init__(self, redis_client: RedisClient | None = None) -> None:
        settings = get_settings()
        self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._redis = redis_client
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def select_model(self, severity: SeverityLevel | None = None) -> str:
        if severity is None:
            return DEFAULT_MODEL
        return MODEL_ROUTING.get(severity, DEFAULT_MODEL)

    def _cache_key(self, prompt: str, model: str) -> str:
        content = f"{prompt}:{model}"
        digest = hashlib.sha256(content.encode()).hexdigest()
        return f"llm:cache:{digest}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def invoke(
        self,
        prompt: str,
        severity: SeverityLevel | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Call Anthropic API with routing, caching, and retry."""
        selected_model = model or self.select_model(severity)

        # Check cache
        if use_cache and self._redis:
            cache_key = self._cache_key(prompt, selected_model)
            cached = await self._redis.get_json(cache_key)
            if cached is not None:
                logger.info("llm_cache_hit", model=selected_model)
                return dict(cached)  # type: ignore[arg-type]

        # Build messages
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": selected_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        logger.info("llm_invoke", model=selected_model, prompt_len=len(prompt))
        response = await self._anthropic.messages.create(**kwargs)

        # Track tokens
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens

        result = {
            "content": response.content[0].text if response.content else "",
            "model": selected_model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "stop_reason": response.stop_reason,
        }

        # Store in cache
        if use_cache and self._redis:
            await self._redis.set_json(cache_key, result, ttl=CACHE_TTL)

        return result

    @property
    def total_tokens(self) -> dict[str, int]:
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
            "total": self._total_input_tokens + self._total_output_tokens,
        }
