"""Log Analyzer API router — /log-analyzer prefix."""

from __future__ import annotations

import gzip
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from apps.log_analyzer.schemas import SubModuleStatus
from backend.dependencies import get_sqlite, get_tenant_context
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext
from shared.utils.encryption import decrypt, encrypt
from shared.utils.settings import get_settings

# Turkey is UTC+3 — user dates are local Turkish time
TURKEY_TZ = timezone(timedelta(hours=3))

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
    cp_code: str | None = None
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


class CreateProjectRequest(BaseModel):
    name: str
    sub_module: str = "akamai"


class StructureAnalyzeRequest(BaseModel):
    start_date: str
    end_date: str
    sample_size: int = 1000


class FieldMappingRequest(BaseModel):
    field_name: str
    category: str


VALID_CATEGORIES = {
    "meta", "timing", "traffic", "content", "client",
    "network", "response", "cache", "geo", "custom",
}


def _infer_type(values: list[object]) -> str:
    """Infer the data type from a list of non-None values."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "string"

    sample = non_null[:50]

    # Check if all are bool
    if all(isinstance(v, bool) for v in sample):
        return "boolean"

    # Check integer (includes 0/1 booleans stored as int)
    if all(isinstance(v, int) and not isinstance(v, bool) for v in sample):
        int_vals = {v for v in sample}
        if int_vals <= {0, 1} and len(sample) > 2:
            return "boolean"
        return "integer"

    # Check float (including timestamp detection for epoch values)
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in sample):
        if all(1_000_000_000 < float(v) < 2_000_000_000 for v in sample):
            return "timestamp"
        return "float"

    # Check strings for patterns
    str_vals = [str(v) for v in sample]

    # ip_hash: 16-char hex strings (from SHA256 truncation)
    if all(len(s) == 16 and all(c in "0123456789abcdef" for c in s) for s in str_vals):
        return "ip_hash"

    # timestamp: looks like unix epoch float
    try:
        floats = [float(s) for s in str_vals]
        if all(1_000_000_000 < f < 2_000_000_000 for f in floats):
            return "timestamp"
    except (ValueError, TypeError):
        pass

    return "string"


def _analyze_fields(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    """Analyze each field across all entries and return field stats."""
    if not entries:
        return []

    all_fields: set[str] = set()
    for e in entries:
        all_fields.update(e.keys())

    result = []
    for field in sorted(all_fields):
        values = [e.get(field) for e in entries]
        non_null = [v for v in values if v is not None]
        null_count = len(values) - len(non_null)

        # Sample values: 3 distinct non-null
        seen: list[str] = []
        seen_set: set[str] = set()
        for v in non_null:
            s = str(v)
            if s not in seen_set and len(seen) < 3:
                seen.append(s[:60])
                seen_set.add(s)

        unique_count = len(set(str(v) for v in non_null))

        result.append({
            "field_name": field,
            "sample_values": seen,
            "null_count": null_count,
            "unique_count": unique_count,
            "inferred_type": _infer_type(non_null),
            "current_category": None,
        })

    return result


def _build_s3_prefixes(cp_code: str, start_date: str, end_date: str) -> list[str]:
    """Build S3 prefixes for Akamai DS2 path structure.

    Path format: logs/{cp_code}/{year}/{DD}/{MM}/{HH}/
    User dates are Turkish local time (UTC+3), S3 files use UTC.
    """
    # Parse user dates as Turkish local time
    local_start = datetime.strptime(start_date, "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, tzinfo=TURKEY_TZ,
    )
    local_end = datetime.strptime(end_date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=TURKEY_TZ,
    )

    # Convert to UTC
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)

    prefixes: list[str] = []
    current = utc_start.replace(minute=0, second=0, microsecond=0)
    while current <= utc_end:
        prefix = (
            f"logs/{cp_code}/{current.year}/"
            f"{current.day:02d}/{current.month:02d}/{current.hour:02d}/"
        )
        prefixes.append(prefix)
        current += timedelta(hours=1)

    return prefixes


def _read_s3_content(body: Any, key: str) -> str:
    """Read S3 object body, handling .gz compressed files."""
    raw_bytes = body.read()
    if key.endswith(".gz"):
        with gzip.open(io.BytesIO(raw_bytes), "rt", encoding="utf-8") as f:
            return f.read()
    return raw_bytes.decode("utf-8", errors="replace")


_schema_migrated = False


async def _ensure_schema(db: SQLiteClient) -> None:
    global _schema_migrated  # noqa: PLW0603
    if _schema_migrated:
        return
    _schema_migrated = True
    """Run lightweight migrations for columns/tables added after initial schema."""
    # Add cp_code column to settings if missing (SQLite has no ADD COLUMN IF NOT EXISTS)
    try:
        await db.execute("ALTER TABLE settings ADD COLUMN cp_code TEXT DEFAULT ''")
        logger.info("schema_migration", action="added cp_code column to settings")
    except Exception:
        pass  # Column already exists

    # Ensure field_category_mappings table exists
    await db.execute(
        """CREATE TABLE IF NOT EXISTS field_category_mappings (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(tenant_id, field_name)
        )"""
    )


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
async def list_projects(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT * FROM log_projects WHERE tenant_id = ? ORDER BY created_at DESC",
        (ctx.tenant_id,),
    )
    return [dict(r) for r in rows]


@router.post("/projects")
async def create_project(
    payload: CreateProjectRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    project_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO log_projects (id, tenant_id, name, sub_module, is_active, created_at)
           VALUES (?, ?, ?, ?, 1, datetime('now'))""",
        (project_id, ctx.tenant_id, payload.name, payload.sub_module),
    )
    logger.info("project_created", tenant_id=ctx.tenant_id, project_id=project_id, name=payload.name)
    return {
        "id": project_id,
        "tenant_id": ctx.tenant_id,
        "name": payload.name,
        "sub_module": payload.sub_module,
        "is_active": 1,
    }


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
    await _ensure_schema(db)
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
    await _ensure_schema(db)
    settings = get_settings()
    secret = settings.jwt_secret_key

    enc_aws_key = encrypt(payload.aws_access_key_id, secret) if payload.aws_access_key_id else None
    enc_aws_secret = encrypt(payload.aws_secret_access_key, secret) if payload.aws_secret_access_key else None
    enc_gcp_creds = encrypt(payload.gcp_credentials_json, secret) if payload.gcp_credentials_json else None

    row_id = f"{ctx.tenant_id}_global"
    await db.execute(
        """INSERT INTO settings (id, tenant_id, aws_access_key_id, aws_secret_access_key,
           aws_region, s3_bucket, s3_prefix, cp_code, gcp_project_id, gcp_dataset_id,
           gcp_credentials_json, bigquery_enabled, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET
             aws_access_key_id = excluded.aws_access_key_id,
             aws_secret_access_key = excluded.aws_secret_access_key,
             aws_region = excluded.aws_region,
             s3_bucket = excluded.s3_bucket,
             s3_prefix = excluded.s3_prefix,
             cp_code = excluded.cp_code,
             gcp_project_id = excluded.gcp_project_id,
             gcp_dataset_id = excluded.gcp_dataset_id,
             gcp_credentials_json = excluded.gcp_credentials_json,
             bigquery_enabled = excluded.bigquery_enabled,
             updated_at = datetime('now')
        """,
        (
            row_id, ctx.tenant_id, enc_aws_key, enc_aws_secret,
            payload.aws_region, payload.s3_bucket, payload.s3_prefix,
            payload.cp_code,
            payload.gcp_project_id, payload.gcp_dataset_id,
            enc_gcp_creds, payload.bigquery_enabled,
        ),
    )
    return {"status": "saved", "tenant_id": ctx.tenant_id}


@router.get("/settings/test-connection")
async def test_connection(
    type: str = Query(..., description="Connection type: s3 or bq"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Test AWS S3 or GCP BigQuery connectivity using stored credentials."""
    row = await db.fetch_one(
        "SELECT * FROM settings WHERE tenant_id = ?", (ctx.tenant_id,),
    )
    if not row:
        return {"success": False, "message": "No credentials configured. Save settings first."}

    settings = get_settings()
    secret = settings.jwt_secret_key
    row_dict = dict(row)

    if type == "s3":
        enc_key = row_dict.get("aws_access_key_id")
        enc_secret = row_dict.get("aws_secret_access_key")
        if not enc_key or not enc_secret:
            return {"success": False, "message": "AWS credentials not configured."}
        try:
            aws_key = decrypt(enc_key, secret)
            aws_secret = decrypt(enc_secret, secret)
            bucket = row_dict.get("s3_bucket") or "ssport-datastream"
            region = row_dict.get("s3_region") or row_dict.get("aws_region") or "eu-central-1"

            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError

            s3 = boto3.client(
                "s3",
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name=region,
            )
            s3.head_bucket(Bucket=bucket)
            return {"success": True, "message": f"S3 connection successful. Bucket '{bucket}' is accessible."}
        except (ClientError, NoCredentialsError) as exc:
            return {"success": False, "message": f"S3 connection failed: {exc}"}
        except Exception as exc:
            return {"success": False, "message": f"S3 connection failed: {exc}"}

    elif type == "bq":
        enc_creds = row_dict.get("gcp_credentials_json")
        if not enc_creds:
            return {"success": False, "message": "GCP credentials not configured."}
        try:
            import json

            from google.cloud import bigquery
            from google.oauth2 import service_account

            creds_json = decrypt(enc_creds, secret)
            creds_dict = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            project_id = row_dict.get("gcp_project_id") or creds_dict.get("project_id")
            client = bigquery.Client(credentials=credentials, project=project_id)
            datasets = list(client.list_datasets(max_results=1))
            dataset_info = f" Found {len(datasets)} dataset(s)." if datasets else " No datasets found."
            return {"success": True, "message": f"BigQuery connection successful.{dataset_info}"}
        except Exception as exc:
            return {"success": False, "message": f"BigQuery connection failed: {exc}"}

    return {"success": False, "message": f"Unknown connection type: '{type}'. Use 's3' or 'bq'."}


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
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Accept start/end date range, build S3 prefixes with correct path structure."""
    job_id = str(uuid.uuid4())

    # Read cp_code from settings
    row = await db.fetch_one(
        "SELECT cp_code FROM settings WHERE tenant_id = ?", (ctx.tenant_id,),
    )
    cp_code = dict(row).get("cp_code") if row else None
    if not cp_code:
        return {"error": "CP Code not configured. Set it in Log Analyzer Settings."}

    try:
        prefixes = _build_s3_prefixes(cp_code, payload.start_date, payload.end_date)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    logger.info(
        "akamai_fetch_range",
        tenant_id=ctx.tenant_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        job_id=job_id,
        s3_prefixes_count=len(prefixes),
        cp_code=cp_code,
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "tenant_id": ctx.tenant_id,
        "cp_code": cp_code,
        "s3_prefixes_count": len(prefixes),
    }


# ── BigQuery export endpoints ──


@router.post("/bigquery/export")
async def bigquery_export(
    payload: ExportRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Accept job_id and categories, return export status stub."""
    logger.info(
        "bigquery_export_request",
        tenant_id=ctx.tenant_id,
        job_id=payload.job_id,
        categories=payload.categories,
    )
    return {
        "job_id": payload.job_id,
        "status": "queued",
        "categories": payload.categories,
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


# ── Log Structure Analysis ──


@router.post("/structure/analyze")
async def structure_analyze(
    payload: StructureAnalyzeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Analyze log structure by sampling S3 files in a date range."""
    await _ensure_schema(db)
    _empty = {"fields": [], "total_rows_sampled": 0, "files_scanned": 0}
    sample_size = min(payload.sample_size, 5000)

    # Get credentials
    row = await db.fetch_one(
        "SELECT * FROM settings WHERE tenant_id = ?", (ctx.tenant_id,),
    )
    if not row:
        return {"error": "No credentials configured. Go to Settings and save AWS credentials first.", **_empty}

    settings = get_settings()
    secret = settings.jwt_secret_key
    row_dict = dict(row)

    # Diagnostic log (exclude encrypted fields)
    logger.info(
        "structure_analyze_settings",
        tenant_id=ctx.tenant_id,
        cp_code=row_dict.get("cp_code"),
        s3_bucket=row_dict.get("s3_bucket"),
        s3_region=row_dict.get("s3_region") or row_dict.get("aws_region"),
        has_aws_key=bool(row_dict.get("aws_access_key_id")),
        has_aws_secret=bool(row_dict.get("aws_secret_access_key")),
        columns=list(row_dict.keys()),
    )

    enc_key = row_dict.get("aws_access_key_id")
    enc_secret = row_dict.get("aws_secret_access_key")
    if not enc_key or not enc_secret:
        return {"error": "AWS credentials not configured. Go to Settings and save AWS credentials.", **_empty}

    try:
        aws_key = decrypt(enc_key, secret)
        aws_secret = decrypt(enc_secret, secret)
    except Exception:
        return {"error": "Failed to decrypt AWS credentials. Re-save credentials in Settings.", **_empty}

    bucket = row_dict.get("s3_bucket") or "ssport-datastream"
    region = row_dict.get("s3_region") or row_dict.get("aws_region") or "eu-central-1"
    cp_code = row_dict.get("cp_code")
    if not cp_code:
        return {"error": "CP Code not configured. Set it in Log Analyzer Settings.", **_empty}

    # Build S3 prefixes for the date range (UTC+3 → UTC conversion)
    try:
        prefixes = _build_s3_prefixes(cp_code, payload.start_date, payload.end_date)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD.", **_empty}

    import boto3
    from botocore.exceptions import ClientError

    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=region,
        )

        # Collect file keys across all hourly prefixes
        file_keys: list[str] = []
        for prefix in prefixes:
            try:
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=100)
                for obj in resp.get("Contents", []):
                    file_keys.append(obj["Key"])
            except ClientError:
                pass

        if not file_keys:
            return {"error": f"No log files found in S3 for {payload.start_date} to {payload.end_date}.", **_empty}

        # Download and parse files until we have enough rows
        from apps.log_analyzer.sub_modules.akamai.parser import parse_auto

        all_entries: list[dict[str, object]] = []
        files_scanned = 0
        for key in file_keys:
            if len(all_entries) >= sample_size:
                break
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                content = _read_s3_content(obj["Body"], key)
                parsed = parse_auto(content)
                for entry in parsed:
                    if len(all_entries) >= sample_size:
                        break
                    all_entries.append(entry.model_dump())
                files_scanned += 1
            except Exception:
                logger.warning("structure_analyze_file_error", key=key)
                continue

        # Analyze fields
        fields = _analyze_fields(all_entries)

        # Merge saved category mappings
        mappings = await db.fetch_all(
            "SELECT field_name, category FROM field_category_mappings WHERE tenant_id = ?",
            (ctx.tenant_id,),
        )
        mapping_dict = {m["field_name"]: m["category"] for m in mappings}
        for f in fields:
            f["current_category"] = mapping_dict.get(str(f["field_name"]))

        return {
            "fields": fields,
            "total_rows_sampled": len(all_entries),
            "files_scanned": files_scanned,
        }

    except ClientError as exc:
        return {"error": f"S3 error: {exc}", **_empty}
    except Exception as exc:
        logger.error("structure_analyze_error", error=str(exc))
        return {"error": f"Analysis failed: {exc}", **_empty}


@router.post("/structure/mappings")
async def save_field_mapping(
    payload: FieldMappingRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    """Upsert a field→category mapping."""
    if payload.category not in VALID_CATEGORIES:
        return {"status": "error", "message": f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"}

    mapping_id = f"{ctx.tenant_id}_{payload.field_name}"
    await db.execute(
        """INSERT INTO field_category_mappings (id, tenant_id, field_name, category, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET
             category = excluded.category,
             created_at = datetime('now')""",
        (mapping_id, ctx.tenant_id, payload.field_name, payload.category),
    )
    return {"status": "saved", "field_name": payload.field_name, "category": payload.category}


@router.get("/structure/mappings")
async def list_field_mappings(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    """Return all saved field→category mappings for a tenant."""
    rows = await db.fetch_all(
        "SELECT * FROM field_category_mappings WHERE tenant_id = ? ORDER BY field_name",
        (ctx.tenant_id,),
    )
    return [dict(r) for r in rows]
