"""Natural Language Query API router — /nl-query prefix."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.dependencies import get_tenant_context
from shared.nl_query.nl_engine import NLEngine, NLQueryResult, EXAMPLE_QUERIES
from shared.nl_query.schema_registry import get_table_list
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/nl-query", tags=["nl-query"])

_engine = NLEngine()


class NLQueryRequest(BaseModel):
    natural_language: str
    max_rows: int = 100


@router.post("/query")
async def nl_query(
    body: NLQueryRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Execute NL→SQL query."""
    schema = getattr(ctx, "service_id", "aaop_company") or "aaop_company"
    result = await _engine.query(
        natural_language=body.natural_language,
        tenant_id=ctx.tenant_id,
        schema=schema,
        max_rows=min(body.max_rows, 1000),
    )
    return result.model_dump()


@router.get("/tables")
async def list_tables(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict]:
    """Return queryable tables and columns (PII columns hidden)."""
    schema = getattr(ctx, "service_id", "aaop_company") or "aaop_company"
    return get_table_list(schema)


@router.get("/examples")
async def get_examples() -> list[str]:
    """Return example NL queries."""
    return EXAMPLE_QUERIES
