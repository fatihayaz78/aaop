"""Tests for backend/auth.py — JWT token creation, verification, password hashing."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from jose import jwt

from backend.auth import (
    TokenResponse,
    UserPayload,
    _create_token,
    _revoked_tokens,
    get_current_user,
    hash_password,
    verify_password,
)
from shared.utils.settings import Settings


@pytest.fixture(autouse=True)
def _clear_revoked():
    _revoked_tokens.clear()
    yield
    _revoked_tokens.clear()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        anthropic_api_key="test",
        jwt_secret_key="test-secret-key-256bit",
        jwt_algorithm="HS256",
        jwt_expire_minutes=30,
    )


def test_hash_and_verify_password():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_token(test_settings: Settings):
    with patch("backend.auth.get_settings", return_value=test_settings):
        token = _create_token({"sub": "user1", "tenant_id": "t1", "username": "admin", "role": "admin"})
        payload = jwt.decode(token, test_settings.jwt_secret_key, algorithms=[test_settings.jwt_algorithm])
        assert payload["sub"] == "user1"
        assert payload["tenant_id"] == "t1"


def test_create_token_custom_expiry(test_settings: Settings):
    with patch("backend.auth.get_settings", return_value=test_settings):
        token = _create_token(
            {"sub": "user1", "tenant_id": "t1", "username": "admin", "role": "admin"},
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(token, test_settings.jwt_secret_key, algorithms=[test_settings.jwt_algorithm])
        assert payload["sub"] == "user1"


@pytest.mark.asyncio
async def test_get_current_user_valid(test_settings: Settings):
    with patch("backend.auth.get_settings", return_value=test_settings):
        token = _create_token({"sub": "u1", "tenant_id": "t1", "username": "admin", "role": "admin"})
        user = await get_current_user(token)
        assert user.user_id == "u1"
        assert user.tenant_id == "t1"
        assert user.username == "admin"
        assert user.role == "admin"


@pytest.mark.asyncio
async def test_get_current_user_revoked(test_settings: Settings):
    with patch("backend.auth.get_settings", return_value=test_settings):
        token = _create_token({"sub": "u1", "tenant_id": "t1", "username": "admin", "role": "admin"})
        _revoked_tokens.add(token)
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(test_settings: Settings):
    with patch("backend.auth.get_settings", return_value=test_settings):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid.token.here")
        assert exc_info.value.status_code == 401


def test_user_payload_model():
    u = UserPayload(user_id="u1", tenant_id="t1", username="admin", role="admin")
    assert u.user_id == "u1"


def test_token_response_model():
    t = TokenResponse(access_token="abc123", expires_in=3600)
    assert t.token_type == "bearer"
