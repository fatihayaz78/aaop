"""Multi-tenant service context middleware — JWT-based (S-MT-02).

Decodes JWT from Authorization header, sets service_id and duckdb_schema
on request.state. Falls back to defaults if no token present.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)

# In-memory cache: service_id → duckdb_schema (TTL 5 min)
_schema_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300.0


def _get_cached_schema(service_id: str) -> str | None:
    entry = _schema_cache.get(service_id)
    if entry and (time.monotonic() - entry[1]) < _CACHE_TTL:
        return entry[0]
    return None


def _set_cached_schema(service_id: str, schema: str) -> None:
    _schema_cache[service_id] = (schema, time.monotonic())


class ServiceContextMiddleware(BaseHTTPMiddleware):
    """Inject service_id and duckdb_schema into request.state from JWT."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        service_id = "sport_stream"
        duckdb_schema = "sport_stream"

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                settings = get_settings()
                payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
                active = payload.get("active_service_id")
                if active:
                    service_id = active
                    # Look up duckdb_schema from cache or DB
                    cached = _get_cached_schema(service_id)
                    if cached:
                        duckdb_schema = cached
                    else:
                        schema = await self._lookup_schema(service_id)
                        duckdb_schema = schema or service_id
                        _set_cached_schema(service_id, duckdb_schema)
            except (JWTError, KeyError):
                pass  # Fall back to defaults

        request.state.service_id = service_id
        request.state.duckdb_schema = duckdb_schema

        return await call_next(request)

    @staticmethod
    async def _lookup_schema(service_id: str) -> str | None:
        try:
            from backend.dependencies import _sqlite
            if _sqlite:
                row = await _sqlite.fetch_one(
                    "SELECT duckdb_schema FROM services WHERE id = ?", (service_id,),
                )
                if row:
                    return row["duckdb_schema"]
        except Exception:
            pass
        return None
