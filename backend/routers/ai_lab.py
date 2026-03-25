"""AI Lab API router — /ai-lab prefix."""
from __future__ import annotations
import uuid
from typing import Any
import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from backend.dependencies import get_duckdb, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ai-lab", tags=["ai-lab"])

class ExperimentCreate(BaseModel):
    name: str
    hypothesis: str = ""
    variant_a: str = ""
    variant_b: str = ""
    sample_size: int = 1000

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "ai_lab"}

@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant_context), duck: DuckDBClient = Depends(get_duckdb)) -> dict[str, Any]:
    tid = ctx.tenant_id
    total = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.experiments WHERE tenant_id = ?", [tid])
    running = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.experiments WHERE tenant_id = ? AND status = 'running'", [tid])
    completed = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.experiments WHERE tenant_id = ? AND status = 'completed'", [tid])
    prod = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.model_registry WHERE tenant_id = ? AND status = 'production'", [tid])
    acc = duck.fetch_one("SELECT AVG(accuracy) as avg_acc FROM shared_analytics.model_registry WHERE tenant_id = ?", [tid])
    recent = duck.fetch_all("SELECT id, name, status, created_at FROM shared_analytics.experiments WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 5", [tid])
    return {
        "total_experiments": total["cnt"] if total else 0,
        "running_experiments": running["cnt"] if running else 0,
        "completed_experiments": completed["cnt"] if completed else 0,
        "models_in_production": prod["cnt"] if prod else 0,
        "avg_model_accuracy": round(float(acc["avg_acc"] or 0), 3) if acc else 0,
        "recent_experiments": recent,
    }

@router.get("/experiments")
async def list_experiments(ctx: TenantContext = Depends(get_tenant_context), duck: DuckDBClient = Depends(get_duckdb),
    status: str | None = None, limit: int = 20) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if status:
        where += " AND status = ?"
        params.append(status)
    count = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.experiments {where}", params)
    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.experiments {where} ORDER BY created_at DESC LIMIT ?", [*params, limit])
    return {"items": rows, "total": count["cnt"] if count else 0}

@router.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str, ctx: TenantContext = Depends(get_tenant_context), duck: DuckDBClient = Depends(get_duckdb)) -> dict[str, Any]:
    row = duck.fetch_one("SELECT * FROM shared_analytics.experiments WHERE id = ? AND tenant_id = ?", [exp_id, ctx.tenant_id])
    return row if row else {"error": "Experiment not found"}

@router.post("/experiments")
async def create_experiment(payload: ExperimentCreate, ctx: TenantContext = Depends(get_tenant_context), duck: DuckDBClient = Depends(get_duckdb)) -> dict[str, Any]:
    from datetime import datetime, timezone
    eid = f"EXP-{uuid.uuid4().hex[:8]}"
    duck.execute("INSERT INTO shared_analytics.experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [eid, ctx.tenant_id, payload.name, payload.hypothesis, "draft",
         payload.variant_a, payload.variant_b, payload.sample_size,
         None, None, None, datetime.now(timezone.utc).isoformat(), None])
    return {"id": eid, "name": payload.name, "status": "draft"}

@router.get("/models")
async def list_models(ctx: TenantContext = Depends(get_tenant_context), duck: DuckDBClient = Depends(get_duckdb),
    status: str | None = None) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if status:
        where += " AND status = ?"
        params.append(status)
    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.model_registry {where} ORDER BY created_at DESC", params)
    return {"items": rows, "total": len(rows)}

@router.get("/models/{model_id}")
async def get_model(model_id: str, ctx: TenantContext = Depends(get_tenant_context), duck: DuckDBClient = Depends(get_duckdb)) -> dict[str, Any]:
    row = duck.fetch_one("SELECT * FROM shared_analytics.model_registry WHERE id = ? AND tenant_id = ?", [model_id, ctx.tenant_id])
    return row if row else {"error": "Model not found"}
