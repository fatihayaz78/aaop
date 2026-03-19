"""Tests for backend middleware — tenant_context and rate_limit."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.rate_limit import MAX_REQUESTS, RateLimitMiddleware, _request_log
from backend.middleware.tenant_context import TenantContextMiddleware


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


@pytest.fixture
def client(app_with_middleware):
    with TestClient(app_with_middleware) as c:
        yield c
    _request_log.clear()


def test_tenant_context_injected(client: TestClient):
    response = client.get("/test", headers={"X-Tenant-ID": "bein"})
    assert response.status_code == 200


def test_request_without_tenant(client: TestClient):
    response = client.get("/test")
    assert response.status_code == 200


def test_rate_limit_not_exceeded(client: TestClient):
    for _ in range(5):
        response = client.get("/test", headers={"X-Tenant-ID": "t1"})
        assert response.status_code == 200


def test_rate_limit_exceeded(client: TestClient):
    _request_log.clear()
    for i in range(MAX_REQUESTS + 1):
        response = client.get("/test", headers={"X-Tenant-ID": "rate_test"})
        if i == MAX_REQUESTS:
            assert response.status_code == 429
