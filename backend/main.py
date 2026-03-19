"""FastAPI application — router mount, startup/shutdown events, health check."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import router as auth_router
from backend.dependencies import init_clients, shutdown_clients
from backend.routers.log_analyzer import router as log_analyzer_router
from backend.routers.ops_center import router as ops_center_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup_begin")
    await init_clients()
    logger.info("startup_complete")
    yield
    logger.info("shutdown_begin")
    await shutdown_clients()
    logger.info("shutdown_complete")


app = FastAPI(
    title="AAOP — Captain logAR",
    version="0.1.0",
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

# App routers
app.include_router(log_analyzer_router)
app.include_router(ops_center_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
