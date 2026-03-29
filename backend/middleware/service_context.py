"""Multi-tenant service context middleware.

S-MT-01: Stub — defaults only.
S-MT-02: Full JWT parse + DB lookup.
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Stub: tenant → default service mapping
_DEFAULT_SERVICE: dict[str, str] = {
    "ott_co": "sport_stream",
    "tel_co": "tv_plus",
    "airline_co": "fly_ent",
}


class ServiceContextMiddleware(BaseHTTPMiddleware):
    """Inject service_id and duckdb_schema into request.state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = getattr(request.state, "tenant_id", None) or "ott_co"
        service_id = _DEFAULT_SERVICE.get(tenant_id, "sport_stream")

        request.state.service_id = service_id
        request.state.duckdb_schema = service_id

        return await call_next(request)
