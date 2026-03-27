"""FastAPI application — router mount, startup/shutdown events, health check."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import router as auth_router
from backend.dependencies import init_clients, shutdown_clients
from backend.routers.admin_governance import router as admin_governance_router
from backend.routers.ai_lab import router as ai_lab_router
from backend.routers.alert_center import router as alert_center_router
from backend.routers.capacity_cost import router as capacity_cost_router
from backend.routers.devops_assistant import router as devops_assistant_router
from backend.routers.growth_retention import router as growth_retention_router
from backend.routers.knowledge_base import router as knowledge_base_router
from backend.routers.live_intelligence import router as live_intelligence_router
from backend.routers.log_analyzer import router as log_analyzer_router
from backend.routers.ops_center import router as ops_center_router
from backend.routers.data_sources import router as data_sources_router
from backend.routers.mock_data_gen import router as mock_data_gen_router
from backend.routers.viewer_experience import router as viewer_experience_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup_begin")
    await init_clients()
    # Seeds disabled — data loaded via Data Ingestion Layer
    logger.info("Seeds disabled — data loaded via Data Ingestion Layer")
    # Initialize logs.duckdb for default tenant
    try:
        from shared.clients.logs_duckdb_client import LogsDuckDBClient
        from shared.ingest.log_schemas import LOG_TABLE_SCHEMAS
        logs_db = LogsDuckDBClient()
        logs_db.ensure_tenant_schema("aaop_company")
        for source_name, create_sql in LOG_TABLE_SCHEMAS.items():
            logs_db.ensure_source_table("aaop_company", source_name, create_sql)
        logger.info("logs_duckdb_initialized", tenant="aaop_company", tables=len(LOG_TABLE_SCHEMAS))
    except Exception as exc:
        logger.warning("logs_duckdb_init_error", error=str(exc))
    logger.info("startup_complete")
    yield
    logger.info("shutdown_begin")
    await shutdown_clients()
    logger.info("shutdown_complete")


app = FastAPI(
    title="AAOP — Captain logAR",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth
app.include_router(auth_router)

# App routers — all 11 apps
app.include_router(ops_center_router)
app.include_router(log_analyzer_router)
app.include_router(alert_center_router)
app.include_router(viewer_experience_router)
app.include_router(live_intelligence_router)
app.include_router(growth_retention_router)
app.include_router(capacity_cost_router)
app.include_router(ai_lab_router)
app.include_router(knowledge_base_router)
app.include_router(devops_assistant_router)
app.include_router(admin_governance_router)
app.include_router(mock_data_gen_router)
app.include_router(data_sources_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/detailed")
async def health_detailed() -> dict[str, str]:
    """Detailed health check for all platform components."""
    from backend.dependencies import _duckdb, _redis, _sqlite

    checks: dict[str, str] = {}

    # SQLite
    try:
        if _sqlite:
            await _sqlite.fetch_one("SELECT 1 as ok")
        checks["sqlite"] = "ok"
    except Exception as e:
        checks["sqlite"] = str(e)

    # DuckDB
    try:
        if _duckdb:
            _duckdb.fetch_all("SELECT 1 as ok", [])
        checks["duckdb"] = "ok"
    except Exception as e:
        checks["duckdb"] = str(e)

    # Redis
    try:
        if _redis and _redis._client:
            await _redis._client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)

    # ChromaDB — no persistent connection in local mode
    checks["chromadb"] = "ok"

    # LLM Gateway — static in local mode
    checks["llm_gateway"] = "ok"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "version": "1.0.0", **checks}


@app.get("/openapi-spec")
async def openapi_spec() -> dict:
    """Return the full OpenAPI specification for download."""
    return app.openapi()
