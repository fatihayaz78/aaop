"""Tests for backend/main.py — FastAPI app and health endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with (
        patch("backend.dependencies.init_clients", new_callable=AsyncMock),
        patch("backend.dependencies.shutdown_clients", new_callable=AsyncMock),
        TestClient(app) as c,
    ):
        yield c


def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_cors_headers(client: TestClient):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200


def test_login_not_implemented(client: TestClient):
    response = client.post("/auth/login", data={"username": "admin", "password": "test"})
    assert response.status_code == 501
