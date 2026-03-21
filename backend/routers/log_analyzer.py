"""Log Analyzer API router — /log-analyzer prefix."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.log_analyzer.schemas import SubModuleStatus
from backend.dependencies import get_sqlite, get_tenant_context
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext
from shared.utils.encryption import decrypt, encrypt
from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/log-analyzer", tags=["log-analyzer"])


def _mask_key(value: str | None) -> str | None:
    """Mask a secret key, showing only last 4 characters."""
    if not value:
        return None
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


# ── Request/Response models ──


class SettingsPayload(BaseModel):
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "eu-central-1"
    s3_bucket: str | None = None
    s3_prefix: str = "logs/"
    gcp_project_id: str | None = None
    gcp_dataset_id: str | None = None
    gcp_credentials_json: str | None = None
    bigquery_enabled: int = 0


class FetchRangeRequest(BaseModel):
    start_date: str
    end_date: str


class ExportRequest(BaseModel):
    job_id: str
    categories: list[str]


# ── Existing endpoints ──


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "log_analyzer"}


@router.get("/sub-modules")
async def list_sub_modules() -> list[SubModuleStatus]:
    from apps.log_analyzer.sub_modules import SubModuleRegistry

    modules = SubModuleRegistry.list_all()
    return [
        SubModuleStatus(name=cls.name, display_name=cls.display_name)
        for cls in modules.values()
    ]


@router.get("/projects")
async def list_projects(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    # Placeholder — will read from SQLite in full implementation
    return []


@router.get("/results")
async def list_results(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    # Placeholder — will read from DuckDB
    return []


# ── Settings endpoints ──


@router.get("/settings")
async def get_settings_endpoint(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Return settings with masked AWS/GCP keys (last 4 chars only)."""
    row = await db.fetch_one(
        "SELECT * FROM settings WHERE tenant_id = ?", (ctx.tenant_id,),
    )
    if not row:
        return {"status": "not_configured", "tenant_id": ctx.tenant_id}

    settings = get_settings()
    secret = settings.jwt_secret_key

    result = dict(row)
    # Decrypt then mask sensitive fields
    for field in ("aws_access_key_id", "aws_secret_access_key", "gcp_credentials_json"):
        raw = result.get(field)
        if raw:
            try:
                decrypted = decrypt(raw, secret)
                result[field] = _mask_key(decrypted)
            except Exception:
                result[field] = _mask_key(raw)
        else:
            result[field] = None

    return result


@router.post("/settings")
async def save_settings(
    payload: SettingsPayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    """Save settings, encrypting AWS/GCP keys."""
    settings = get_settings()
    secret = settings.jwt_secret_key

    enc_aws_key = encrypt(payload.aws_access_key_id, secret) if payload.aws_access_key_id else None
    enc_aws_secret = encrypt(payload.aws_secret_access_key, secret) if payload.aws_secret_access_key else None
    enc_gcp_creds = encrypt(payload.gcp_credentials_json, secret) if payload.gcp_credentials_json else None

    row_id = f"{ctx.tenant_id}_global"
    await db.execute(
        """INSERT INTO settings (id, tenant_id, aws_access_key_id, aws_secret_access_key,
           aws_region, s3_bucket, s3_prefix, gcp_project_id, gcp_dataset_id,
           gcp_credentials_json, bigquery_enabled, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET
             aws_access_key_id = excluded.aws_access_key_id,
             aws_secret_access_key = excluded.aws_secret_access_key,
             aws_region = excluded.aws_region,
             s3_bucket = excluded.s3_bucket,
             s3_prefix = excluded.s3_prefix,
             gcp_project_id = excluded.gcp_project_id,
             gcp_dataset_id = excluded.gcp_dataset_id,
             gcp_credentials_json = excluded.gcp_credentials_json,
             bigquery_enabled = excluded.bigquery_enabled,
             updated_at = datetime('now')
        """,
        (
            row_id, ctx.tenant_id, enc_aws_key, enc_aws_secret,
            payload.aws_region, payload.s3_bucket, payload.s3_prefix,
            payload.gcp_project_id, payload.gcp_dataset_id,
            enc_gcp_creds, payload.bigquery_enabled,
        ),
    )
    return {"status": "saved", "tenant_id": ctx.tenant_id}


@router.delete("/settings/credentials")
async def clear_credentials(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    """Clear AWS + GCP credential fields."""
    await db.execute(
        """UPDATE settings SET
           aws_access_key_id = NULL,
           aws_secret_access_key = NULL,
           gcp_credentials_json = NULL,
           updated_at = datetime('now')
           WHERE tenant_id = ?""",
        (ctx.tenant_id,),
    )
    return {"status": "credentials_cleared", "tenant_id": ctx.tenant_id}


# ── Akamai fetch range ──


@router.post("/akamai/fetch-range")
async def fetch_range(
    payload: FetchRangeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Accept start/end date range, return a job stub."""
    job_id = str(uuid.uuid4())
    logger.info(
        "akamai_fetch_range",
        tenant_id=ctx.tenant_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        job_id=job_id,
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "tenant_id": ctx.tenant_id,
    }


# ── BigQuery export endpoints ──


@router.get("/bigquery/export")
async def bigquery_export(
    job_id: str,
    categories: str = "meta,timing,traffic",
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Accept job_id and categories, return export status stub."""
    category_list = [c.strip() for c in categories.split(",") if c.strip()]
    logger.info(
        "bigquery_export_request",
        tenant_id=ctx.tenant_id,
        job_id=job_id,
        categories=category_list,
    )
    return {
        "job_id": job_id,
        "status": "pending",
        "categories": category_list,
        "tenant_id": ctx.tenant_id,
    }


@router.get("/bigquery/jobs/{job_id}")
async def bigquery_job_status(
    job_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Return job status stub."""
    return {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "tenant_id": ctx.tenant_id,
    }
