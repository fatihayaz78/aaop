"""Tests for shared/utils/settings.py."""

from __future__ import annotations

from shared.utils.settings import Settings


def test_settings_defaults():
    s = Settings(anthropic_api_key="test-key")
    assert s.environment == "local"
    assert s.redis_port == 6379
    assert s.jwt_algorithm == "HS256"
    assert s.sqlite_path == "./data/sqlite/platform.db"
    assert s.duckdb_path == "./data/duckdb/analytics.duckdb"


def test_settings_custom_values():
    s = Settings(
        anthropic_api_key="key",
        redis_host="redis.example.com",
        redis_port=6380,
        environment="production",
    )
    assert s.redis_host == "redis.example.com"
    assert s.redis_port == 6380
    assert s.environment == "production"
