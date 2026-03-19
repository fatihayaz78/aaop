"""Simple in-memory rate limiter middleware."""

from __future__ import annotations

import time
from collections import defaultdict

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

# tenant_id -> list of request timestamps
_request_log: dict[str, list[float]] = defaultdict(list)
MAX_REQUESTS = 100
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        now = time.monotonic()

        # Prune old entries
        _request_log[tenant_id] = [t for t in _request_log[tenant_id] if now - t < WINDOW_SECONDS]

        if len(_request_log[tenant_id]) >= MAX_REQUESTS:
            logger.warning("rate_limit_exceeded", tenant_id=tenant_id)
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        _request_log[tenant_id].append(now)
        return await call_next(request)
