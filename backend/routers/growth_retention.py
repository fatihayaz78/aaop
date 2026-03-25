"""Growth & Retention API router — /growth prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import get_duckdb, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/growth", tags=["growth-retention"])

_SEGMENT_META = {
    "power_user": {"description": "High engagement, QoE >4.0, daily active", "recommended_action": "Upsell premium content, referral program"},
    "regular": {"description": "Moderate usage, stable QoE", "recommended_action": "Engagement campaigns, personalized content"},
    "at_risk": {"description": "Declining activity, QoE dropping", "recommended_action": "Proactive outreach, QoE improvement, retention offers"},
    "churned": {"description": "Inactive >14 days, low QoE", "recommended_action": "Win-back campaign, exit survey, special pricing"},
}


class QueryRequest(BaseModel):
    question: str


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "growth_retention"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id

    total_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.retention_scores WHERE tenant_id = ?", [tid])
    total = total_row["cnt"] if total_row else 0

    at_risk_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.retention_scores WHERE tenant_id = ? AND churn_risk > 0.7", [tid])
    at_risk = at_risk_row["cnt"] if at_risk_row else 0

    avg_row = duck.fetch_one("SELECT AVG(churn_risk) as avg_cr, AVG(qoe_score) as avg_qoe FROM shared_analytics.retention_scores WHERE tenant_id = ?", [tid])
    avg_churn = round(float(avg_row["avg_cr"]), 3) if avg_row and avg_row["avg_cr"] else 0.0
    avg_qoe = round(float(avg_row["avg_qoe"]), 2) if avg_row and avg_row["avg_qoe"] else 0.0

    seg_rows = duck.fetch_all("SELECT segment, COUNT(*) as cnt FROM shared_analytics.retention_scores WHERE tenant_id = ? GROUP BY segment", [tid])
    seg_breakdown = {"power_user": 0, "regular": 0, "at_risk": 0, "churned": 0}
    for r in seg_rows:
        seg_breakdown[r["segment"]] = r["cnt"]

    return {
        "total_users": total,
        "at_risk_users": at_risk,
        "avg_churn_risk": avg_churn,
        "avg_qoe_score": avg_qoe,
        "segment_breakdown": seg_breakdown,
        "churn_trend_7d": [{"date": f"2026-03-{19+i}", "at_risk_count": at_risk + i - 3} for i in range(7)],
        "top_churn_reasons": [
            {"reason": "qoe_drop", "count": 34}, {"reason": "cdn_issues", "count": 22},
            {"reason": "inactivity", "count": 18}, {"reason": "price", "count": 12},
        ],
    }


@router.get("/retention")
async def retention_list(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    limit: int = 50,
    offset: int = 0,
    segment: str | None = None,
) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if segment:
        where += " AND segment = ?"
        params.append(segment)

    count_row = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.retention_scores {where}", params)
    total = count_row["cnt"] if count_row else 0

    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.retention_scores {where} ORDER BY churn_risk DESC LIMIT ? OFFSET ?", [*params, limit, offset])
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/churn-risk")
async def churn_risk(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id
    rows = duck.fetch_all(
        "SELECT * FROM shared_analytics.retention_scores WHERE tenant_id = ? AND churn_risk > 0.7 ORDER BY churn_risk DESC LIMIT 20",
        [tid],
    )
    return {"items": rows, "total": len(rows), "threshold": 0.7}


@router.get("/segments")
async def segments(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id
    seg_rows = duck.fetch_all(
        "SELECT segment, COUNT(*) as cnt, AVG(churn_risk) as avg_cr, AVG(qoe_score) as avg_qoe FROM shared_analytics.retention_scores WHERE tenant_id = ? GROUP BY segment",
        [tid],
    )
    result = []
    for r in seg_rows:
        meta = _SEGMENT_META.get(r["segment"], {"description": "", "recommended_action": ""})
        result.append({
            "name": r["segment"], "count": r["cnt"],
            "avg_churn_risk": round(float(r["avg_cr"]), 3), "avg_qoe": round(float(r["avg_qoe"]), 2),
            **meta,
        })
    return {"segments": result}


@router.post("/query")
async def data_analyst_query(
    payload: QueryRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    question = payload.question.strip()
    if not question:
        return {"error": "Question cannot be empty"}

    # Simple NL→SQL for demo (real impl would use LLM)
    sql = f"SELECT * FROM shared_analytics.retention_scores WHERE tenant_id = '{ctx.tenant_id}' LIMIT 10"
    q_lower = question.lower()
    if "churn" in q_lower and "high" in q_lower:
        sql = f"SELECT * FROM shared_analytics.retention_scores WHERE tenant_id = '{ctx.tenant_id}' AND churn_risk > 0.7 ORDER BY churn_risk DESC LIMIT 20"
    elif "segment" in q_lower:
        sql = f"SELECT segment, COUNT(*) as cnt FROM shared_analytics.retention_scores WHERE tenant_id = '{ctx.tenant_id}' GROUP BY segment"

    if not sql.strip().upper().startswith("SELECT"):
        return {"error": "Only SELECT queries allowed"}

    try:
        rows = duck.fetch_all(sql)
        return {"question": question, "sql": sql, "results": rows, "row_count": len(rows)}
    except Exception as exc:
        return {"error": str(exc), "question": question, "sql": sql}
