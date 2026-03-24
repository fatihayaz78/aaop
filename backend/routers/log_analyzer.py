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
from backend.dependencies import get_duckdb, get_sqlite, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
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
    """Partial settings update — only non-None fields are written."""
    cp_code: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    gcp_project_id: str | None = None
    gcp_dataset_id: str | None = None
    gcp_credentials_json: str | None = None
    bigquery_enabled: int | None = None


class FetchRangeRequest(BaseModel):
    start_date: str
    end_date: str
    cache_mode: str = "auto"  # "auto" or "force_refresh"
    fetch_mode: str = "sampled"  # "sampled" or "full"


class ExportRequest(BaseModel):
    job_id: str
    categories: list[str]


class CreateProjectRequest(BaseModel):
    name: str
    sub_module: str = "akamai"
    description: str = ""
    source_type: str = "akamai_ds2"
    cp_code: str = ""
    fetch_mode: str = "sampled"
    default_date_range: str = "last_1_day"


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

# DS2 known field type overrides (fallback when inference returns "string")
DS2_FIELD_TYPES: dict[str, str] = {
    "req_time_sec": "timestamp",
    "dns_lookup_time_ms": "integer",
    "transfer_time_ms": "integer",
    "turn_around_time_ms": "integer",
    "bytes": "integer",
    "client_bytes": "integer",
    "response_body_size": "integer",
    "status_code": "integer",
    "cache_status": "integer",
    "cache_hit": "boolean",
    "client_ip": "ip_hash",
    "edge_ip": "string",
    "version": "integer",
    "cp_code": "integer",
}

DS2_FIELD_DESCRIPTIONS: dict[str, str] = {
    "version": "Log format version number",
    "cp_code": "Akamai Content Provider Code",
    "req_time_sec": "Request timestamp (Unix epoch, UTC)",
    "bytes": "Total bytes transferred",
    "client_bytes": "Bytes sent to client",
    "content_type": "MIME type of response content",
    "response_body_size": "Full object size in bytes",
    "user_agent": "Client User-Agent string",
    "hostname": "Requested hostname (e.g. cdn.ssportplus.com)",
    "req_path": "Request path",
    "status_code": "HTTP response status code",
    "client_ip": "Client IP (SHA256 hashed for PII)",
    "req_range": "HTTP Range header value",
    "cache_status": "Akamai cache status integer (0-9)",
    "dns_lookup_time_ms": "DNS resolution time in ms",
    "transfer_time_ms": "Transfer duration in ms",
    "turn_around_time_ms": "Edge turnaround time in ms",
    "error_code": "Akamai error code string",
    "cache_hit": "Binary cache hit flag (0/1)",
    "edge_ip": "Akamai edge node IP address",
    "country": "Client country code (ISO 3166)",
    "city": "Client city name",
}

DS2_DEFAULT_CATEGORIES: dict[str, str] = {
    "version": "meta", "cp_code": "meta",
    "req_time_sec": "timing", "dns_lookup_time_ms": "timing",
    "transfer_time_ms": "timing", "turn_around_time_ms": "timing",
    "bytes": "traffic", "client_bytes": "traffic", "response_body_size": "traffic",
    "content_type": "content", "req_path": "content",
    "user_agent": "client", "client_ip": "client", "req_range": "client",
    "hostname": "network", "edge_ip": "network",
    "status_code": "response", "error_code": "response",
    "cache_status": "cache", "cache_hit": "cache",
    "country": "geo", "city": "geo",
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
        # Treat None and empty string as null
        non_null = [v for v in values if v is not None and v != ""]
        null_count = len(values) - len(non_null)

        # Sample values: 3 distinct non-empty
        seen: list[str] = []
        seen_set: set[str] = set()
        for v in non_null:
            s = str(v)
            if s and s not in seen_set and len(seen) < 3:
                seen.append(s[:60])
                seen_set.add(s)

        unique_count = len(set(str(v) for v in non_null)) if non_null else 0

        # Type inference with DS2 fallback
        inferred = _infer_type(non_null)
        if inferred == "string" and field in DS2_FIELD_TYPES:
            inferred = DS2_FIELD_TYPES[field]

        result.append({
            "field_name": field,
            "description": DS2_FIELD_DESCRIPTIONS.get(field, ""),
            "sample_values": seen,
            "null_count": null_count,
            "unique_count": unique_count,
            "inferred_type": inferred,
            "current_category": None,
        })

    return result


def _cache_key(tenant_id: str, cp_code: str, date_str: str) -> str:
    """Build cache key for a single day: tenant_id:cp_code:date."""
    return f"{tenant_id}:{cp_code}:{date_str}"


def _date_range(start_date: str, end_date: str) -> list[str]:
    """Return list of YYYY-MM-DD strings from start to end inclusive."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    dates: list[str] = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


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

    logger.info(
        "s3_prefixes_built",
        input_start=start_date,
        input_end=end_date,
        utc_start=utc_start.isoformat(),
        utc_end=utc_end.isoformat(),
        total=len(prefixes),
        first=prefixes[0] if prefixes else None,
        last=prefixes[-1] if prefixes else None,
    )
    return prefixes


def _read_s3_content(body: Any, key: str) -> str:
    """Read S3 object body, handling .gz compressed files."""
    raw_bytes = body.read()
    if key.endswith(".gz"):
        with gzip.open(io.BytesIO(raw_bytes), "rt", encoding="utf-8") as f:
            return f.read()
    return raw_bytes.decode("utf-8", errors="replace")


# DS2 TSV field order (22 fields, positional — no header row in DS2)
_DS2_FIELDS = [
    "version", "cp_code", "req_time_sec", "bytes", "client_bytes",
    "content_type", "response_body_size", "user_agent", "hostname",
    "req_path", "status_code", "client_ip", "req_range", "cache_status",
    "dns_lookup_time_ms", "transfer_time_ms", "turn_around_time_ms",
    "error_code", "cache_hit", "edge_ip", "country", "city",
]

_DS2_INT_FIELDS = {
    "bytes", "client_bytes", "response_body_size", "status_code",
    "cache_status", "cache_hit", "dns_lookup_time_ms", "transfer_time_ms",
    "turn_around_time_ms", "version",
}
_DS2_FLOAT_FIELDS = {"req_time_sec"}


def _parse_ds2_row(fields: list[str]) -> dict[str, object]:
    """Convert a list of 22 TSV field values into a dict with type coercion + PII hash."""
    import hashlib

    if len(fields) < 22:
        fields.extend([""] * (22 - len(fields)))

    row: dict[str, object] = {}
    for i, name in enumerate(_DS2_FIELDS):
        val = fields[i].strip() if i < len(fields) else ""
        if not val:
            row[name] = None
            continue

        if name in ("client_ip", "user_agent"):
            row[name] = hashlib.sha256(val.encode()).hexdigest()[:16]
        elif name in _DS2_INT_FIELDS:
            try:
                row[name] = int(val)
            except (ValueError, TypeError):
                row[name] = None
        elif name in _DS2_FLOAT_FIELDS:
            try:
                row[name] = float(val)
            except (ValueError, TypeError):
                row[name] = None
        else:
            row[name] = val

    return row


def _stream_s3_gz(s3: Any, bucket: str, key: str, max_rows: int | None = None) -> list[dict[str, object]]:
    """Stream a .gz TSV file from S3 → parse rows in memory, no disk write."""
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()

    rows: list[dict[str, object]] = []
    if key.endswith(".gz"):
        with gzip.open(io.BytesIO(body), "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                fields = line.strip().split("\t")
                if len(fields) >= 22:
                    rows.append(_parse_ds2_row(fields))
                if max_rows and len(rows) >= max_rows:
                    break
    else:
        for line in body.decode("utf-8", errors="replace").splitlines():
            fields = line.strip().split("\t")
            if len(fields) >= 22:
                rows.append(_parse_ds2_row(fields))
            if max_rows and len(rows) >= max_rows:
                break

    return rows


_schema_migrated = False


async def _ensure_schema(db: SQLiteClient) -> None:
    """Ensure all log_analyzer tables exist and run column migrations."""
    global _schema_migrated  # noqa: PLW0603
    if _schema_migrated:
        return
    _schema_migrated = True

    # ── Create tables used by log_analyzer ──
    await db.execute(
        """CREATE TABLE IF NOT EXISTS log_projects (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sub_module TEXT NOT NULL,
            config_json TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )"""
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS log_sources (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            config_json TEXT,
            last_fetch TEXT,
            status TEXT DEFAULT 'idle'
        )"""
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY DEFAULT 'global',
            tenant_id TEXT NOT NULL,
            aws_access_key_id TEXT,
            aws_secret_access_key TEXT,
            aws_region TEXT DEFAULT 'eu-central-1',
            s3_bucket TEXT,
            s3_prefix TEXT DEFAULT 'logs/',
            cp_code TEXT DEFAULT '',
            gcp_project_id TEXT,
            gcp_dataset_id TEXT,
            gcp_credentials_json TEXT,
            bigquery_enabled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )"""
    )
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

    await db.execute(
        """CREATE TABLE IF NOT EXISTS anomaly_rules (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            field TEXT NOT NULL,
            operator TEXT NOT NULL,
            value TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )"""
    )

    # Seed default rules for s_sport_plus
    existing = await db.fetch_one("SELECT id FROM anomaly_rules WHERE tenant_id = 's_sport_plus' LIMIT 1", ())
    if not existing:
        await db.execute(
            """INSERT OR IGNORE INTO anomaly_rules (id, tenant_id, name, field, operator, value, severity, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("rule_foreign_country", "s_sport_plus", "Foreign Country Access", "country", "not_in",
             '["TR"]', "high", "Requests from outside Turkey are anomalous for this service"),
        )
        await db.execute(
            """INSERT OR IGNORE INTO anomaly_rules (id, tenant_id, name, field, operator, value, severity, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("rule_long_session", "s_sport_plus", "Long Session per IP", "session_duration_hours", "gt",
             "12", "medium", "Single IP streaming more than 12 hours/day"),
        )

    await db.execute(
        """CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            project_id TEXT,
            name TEXT NOT NULL,
            cp_code TEXT,
            s3_bucket TEXT,
            s3_prefix TEXT,
            schedule_cron TEXT NOT NULL,
            fetch_mode TEXT DEFAULT 'sampled',
            is_active INTEGER DEFAULT 1,
            notify_emails TEXT DEFAULT '[]',
            last_run TEXT,
            last_status TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )"""
    )

    # ── Column migrations for log_projects ──
    for col, default in [
        ("description", "''"), ("source_type", "'akamai_ds2'"),
        ("cp_code", "''"), ("fetch_mode", "'sampled'"), ("default_date_range", "'last_1_day'"),
    ]:
        try:
            await db.execute(f"ALTER TABLE log_projects ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass

    # ── Column migrations for scheduled_tasks ──
    for col, default in [("bq_export_enabled", "0"), ("bq_export_categories", "'[]'")]:
        try:
            await db.execute(f"ALTER TABLE scheduled_tasks ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass

    # ── Column migrations for settings ──
    for col, default in [
        ("cp_code", "''"),
        ("email_provider", "''"),
        ("email_smtp_host", "''"),
        ("email_smtp_port", "'587'"),
        ("email_username_enc", "''"),
        ("email_password_enc", "''"),
        ("email_from_name", "'Captain logAR'"),
    ]:
        try:
            await db.execute(f"ALTER TABLE settings ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass

    logger.info("log_analyzer_schema_ready")


_duckdb_schema_ready = False


def _ensure_duckdb_schema(duck: DuckDBClient) -> None:
    """Create DuckDB tables for log_analyzer fetch cache and job history."""
    global _duckdb_schema_ready  # noqa: PLW0603
    if _duckdb_schema_ready:
        return
    _duckdb_schema_ready = True
    duck.execute("""
        CREATE TABLE IF NOT EXISTS log_fetch_cache (
            cache_key TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            cp_code TEXT NOT NULL,
            fetch_date TEXT NOT NULL,
            files_count INTEGER,
            rows_count INTEGER,
            fetched_at TEXT,
            parquet_path TEXT
        )
    """)
    duck.execute("""
        CREATE TABLE IF NOT EXISTS fetch_job_history (
            job_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            project_id TEXT,
            cp_code TEXT,
            start_date TEXT,
            end_date TEXT,
            total_files INTEGER,
            total_rows INTEGER,
            cache_hits INTEGER,
            cache_misses INTEGER,
            status TEXT,
            created_at TEXT,
            completed_at TEXT,
            parquet_paths TEXT
        )
    """)
    logger.info("duckdb_log_analyzer_tables_ready")


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
    await _ensure_schema(db)
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
    await _ensure_schema(db)
    project_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO log_projects (id, tenant_id, name, sub_module, description, source_type, cp_code, fetch_mode, default_date_range, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))""",
        (project_id, ctx.tenant_id, payload.name, payload.sub_module,
         payload.description, payload.source_type, payload.cp_code,
         payload.fetch_mode, payload.default_date_range),
    )
    logger.info("project_created", tenant_id=ctx.tenant_id, project_id=project_id, name=payload.name)
    return {
        "id": project_id,
        "tenant_id": ctx.tenant_id,
        "name": payload.name,
        "sub_module": payload.sub_module,
        "description": payload.description,
        "source_type": payload.source_type,
        "cp_code": payload.cp_code,
        "fetch_mode": payload.fetch_mode,
        "default_date_range": payload.default_date_range,
        "is_active": 1,
    }


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    await _ensure_schema(db)
    await db.execute("DELETE FROM log_projects WHERE id=? AND tenant_id=?", (project_id, ctx.tenant_id))
    logger.info("project_deleted", tenant_id=ctx.tenant_id, project_id=project_id)
    return {"status": "deleted", "id": project_id}


@router.get("/results")
async def list_results(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    # Placeholder — will read from DuckDB
    return []


@router.delete("/results/{job_id}")
async def delete_result(
    job_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, str]:
    """Delete a fetch job from DuckDB history."""
    _ensure_duckdb_schema(duck)
    try:
        duck.execute("DELETE FROM fetch_job_history WHERE job_id = ? AND tenant_id = ?", [job_id, ctx.tenant_id])
    except Exception:
        pass
    return {"status": "deleted", "job_id": job_id}


@router.get("/projects/{project_id}/summary")
async def get_project_summary(
    project_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Return project info + last job + scheduled task count + anomaly count."""
    await _ensure_schema(db)
    _ensure_duckdb_schema(duck)

    project = await db.fetch_one(
        "SELECT * FROM log_projects WHERE id = ? AND tenant_id = ?", (project_id, ctx.tenant_id),
    )
    if not project:
        return {"error": "Project not found"}

    # Last job from DuckDB
    last_job = None
    try:
        row = duck.fetch_one(
            "SELECT * FROM fetch_job_history WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1",
            [ctx.tenant_id],
        )
        if row:
            last_job = {k: row[k] for k in ("job_id", "start_date", "end_date", "total_rows", "total_files", "status", "completed_at")}
    except Exception:
        pass

    # Scheduled tasks count
    tasks_row = await db.fetch_one(
        "SELECT COUNT(*) as cnt FROM scheduled_tasks WHERE tenant_id = ? AND project_id = ? AND is_active = 1",
        (ctx.tenant_id, project_id),
    )
    scheduled_count = tasks_row["cnt"] if tasks_row else 0

    return {
        "project": dict(project),
        "last_job": last_job,
        "scheduled_tasks_count": scheduled_count,
        "last_anomaly_count": 0,
    }


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
    """Partial-update settings — only non-None fields overwrite existing values."""
    await _ensure_schema(db)
    logger.info(
        "save_settings_payload",
        tenant_id=ctx.tenant_id,
        cp_code=payload.cp_code,
        s3_bucket=payload.s3_bucket,
        aws_region=payload.aws_region,
        has_aws_key=bool(payload.aws_access_key_id),
        has_gcp_creds=bool(payload.gcp_credentials_json),
    )

    row_id = f"{ctx.tenant_id}_global"
    settings = get_settings()
    secret = settings.jwt_secret_key

    # Read existing row (may be None if first save)
    existing = await db.fetch_one("SELECT * FROM settings WHERE id = ?", (row_id,))
    old = dict(existing) if existing else {}

    def _merge(field: str, new_val: str | int | None, *, is_encrypted: bool = False) -> str | int | None:
        """Merge a field: None=keep existing, ''=clear, value=overwrite."""
        if new_val is None:
            return old.get(field)
        if isinstance(new_val, str) and new_val == "":
            return "" if not is_encrypted else None
        if is_encrypted and isinstance(new_val, str):
            return encrypt(new_val, secret)
        return new_val

    merged_aws_key = _merge("aws_access_key_id", payload.aws_access_key_id, is_encrypted=True)
    merged_aws_secret = _merge("aws_secret_access_key", payload.aws_secret_access_key, is_encrypted=True)
    merged_gcp_creds = _merge("gcp_credentials_json", payload.gcp_credentials_json, is_encrypted=True)
    merged_aws_region = _merge("aws_region", payload.aws_region)
    merged_s3_bucket = _merge("s3_bucket", payload.s3_bucket)
    merged_s3_prefix = _merge("s3_prefix", payload.s3_prefix)
    merged_cp_code = _merge("cp_code", payload.cp_code)
    merged_gcp_project = _merge("gcp_project_id", payload.gcp_project_id)
    merged_gcp_dataset = _merge("gcp_dataset_id", payload.gcp_dataset_id)
    merged_bq_enabled = _merge("bigquery_enabled", payload.bigquery_enabled)

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
            row_id, ctx.tenant_id, merged_aws_key, merged_aws_secret,
            merged_aws_region, merged_s3_bucket, merged_s3_prefix,
            merged_cp_code,
            merged_gcp_project, merged_gcp_dataset,
            merged_gcp_creds, merged_bq_enabled,
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
    await _ensure_schema(db)
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
    await _ensure_schema(db)
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


# ── Akamai fetch / configure ──

# In-memory job store (good enough for single-process local dev)
_fetch_jobs: dict[str, dict[str, Any]] = {}


class AkamaiConfigureRequest(BaseModel):
    project_id: str | None = None
    s3_bucket: str = "ssport-datastream"
    s3_prefix: str = "logs/"
    schedule_cron: str = "0 */6 * * *"
    enabled: bool = True


@router.post("/akamai/configure")
async def configure_akamai(
    payload: AkamaiConfigureRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Save Akamai sub-module configuration for a project."""
    logger.info(
        "akamai_configure",
        tenant_id=ctx.tenant_id,
        project_id=payload.project_id,
        s3_bucket=payload.s3_bucket,
        schedule_cron=payload.schedule_cron,
    )
    return {"status": "saved", "tenant_id": ctx.tenant_id}


@router.post("/akamai/fetch-range")
async def fetch_range(
    payload: FetchRangeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Start a background fetch job for S3 logs in a date range."""
    await _ensure_schema(db)
    _ensure_duckdb_schema(duck)
    job_id = str(uuid.uuid4())

    # Read settings
    row = await db.fetch_one(
        "SELECT * FROM settings WHERE tenant_id = ?", (ctx.tenant_id,),
    )
    if not row:
        return {"error": "No credentials configured. Go to Settings first."}
    row_dict = dict(row)

    cp_code = row_dict.get("cp_code")
    if not cp_code:
        return {"error": "CP Code not configured. Set it in Log Analyzer Settings."}

    enc_key = row_dict.get("aws_access_key_id")
    enc_secret = row_dict.get("aws_secret_access_key")
    if not enc_key or not enc_secret:
        return {"error": "AWS credentials not configured."}

    app_settings = get_settings()
    secret = app_settings.jwt_secret_key
    try:
        aws_key = decrypt(enc_key, secret)
        aws_secret_val = decrypt(enc_secret, secret)
    except Exception:
        return {"error": "Failed to decrypt AWS credentials."}

    bucket = row_dict.get("s3_bucket") or "ssport-datastream"
    region = row_dict.get("s3_region") or row_dict.get("aws_region") or "eu-central-1"

    try:
        dates = _date_range(payload.start_date, payload.end_date)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    cache_mode = payload.cache_mode or "auto"
    fetch_mode = payload.fetch_mode or "sampled"

    # Initialize job
    _fetch_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 10,
        "total_files": 0,
        "files_downloaded": 0,
        "rows_parsed": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "error": None,
        "cancelled": False,
        "message": None,
        "tenant_id": ctx.tenant_id,
        "cp_code": cp_code,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "fetch_mode": fetch_mode,
    }
    logger.info("fetch_job_created", job_id=job_id, status="queued", days=len(dates), cache_mode=cache_mode, fetch_mode=fetch_mode)

    # Launch background task
    import asyncio

    asyncio.get_event_loop().create_task(
        _run_fetch_job(
            job_id, ctx.tenant_id, cp_code, aws_key, aws_secret_val,
            bucket, region, dates, cache_mode, fetch_mode, duck,
        )
    )

    return _fetch_jobs[job_id]


MAX_FILES_PER_DAY = 500
MAX_FILES_PER_JOB = 2000

# Thread executor for blocking boto3 calls — keeps event loop responsive
from concurrent.futures import ThreadPoolExecutor

_s3_executor = ThreadPoolExecutor(max_workers=4)


async def _run_fetch_job(
    job_id: str,
    tenant_id: str,
    cp_code: str,
    aws_key: str,
    aws_secret: str,
    bucket: str,
    region: str,
    dates: list[str],
    cache_mode: str,
    fetch_mode: str,
    duck: DuckDBClient,
) -> None:
    """Background task: stream S3 files via S3 Select, day by day with cache.

    S3 Select queries TSV data directly on S3 (no local download for raw files).
    Parquet cache stores parsed results for re-analysis.
    fetch_mode: "sampled" (LIMIT 100/file, max 500 files/day) or "full" (no limits).
    """
    import asyncio
    import json
    from pathlib import Path

    loop = asyncio.get_event_loop()
    job = _fetch_jobs[job_id]
    total_rows = 0
    total_files = 0
    cache_hits = 0
    cache_misses = 0
    parquet_paths: list[str] = []

    # Per-file row limit for sampled mode
    stream_limit = 100 if fetch_mode == "sampled" else None

    def _is_cancelled() -> bool:
        return bool(job.get("cancelled"))

    def _mark_cancelled(msg: str) -> None:
        job["status"] = "cancelled"
        job["message"] = msg
        logger.info("fetch_job_cancelled", job_id=job_id, message=msg)

    try:
        job["status"] = "downloading"
        job["progress"] = 15
        logger.info("fetch_job_status", job_id=job_id, status="downloading", mode=fetch_mode)

        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=region,
        )

        for day_idx, date_str in enumerate(dates):
            if _is_cancelled():
                _mark_cancelled(f"Cancelled after {day_idx} of {len(dates)} days")
                return

            ck = _cache_key(tenant_id, cp_code, date_str)

            # Check parquet cache (unless force_refresh)
            if cache_mode == "auto":
                try:
                    cached = duck.fetch_one(
                        "SELECT * FROM log_fetch_cache WHERE cache_key = ?", [ck],
                    )
                    if cached and cached.get("parquet_path"):
                        ppath = cached["parquet_path"]
                        if Path(ppath).exists():
                            cache_hits += 1
                            total_rows += cached.get("rows_count", 0)
                            total_files += cached.get("files_count", 0)
                            parquet_paths.append(ppath)
                            job["cache_hits"] = cache_hits
                            job["rows_parsed"] = total_rows
                            job["message"] = f"Day {date_str}: cache ({cached.get('rows_count', 0):,} rows)"
                            logger.info("fetch_day_cache_hit", job_id=job_id, date=date_str, rows=cached.get("rows_count"))
                            continue
                except Exception:
                    pass

            # Build hourly prefixes for this single day
            prefixes = _build_s3_prefixes(cp_code, date_str, date_str)

            # List files for this day
            day_keys: list[str] = []
            for prefix in prefixes:
                if _is_cancelled():
                    _mark_cancelled(f"Cancelled during listing {date_str}")
                    return
                try:
                    if fetch_mode == "full":
                        paginator = s3.get_paginator("list_objects_v2")
                        pages = await loop.run_in_executor(
                            _s3_executor,
                            lambda p=prefix: list(paginator.paginate(Bucket=bucket, Prefix=p, Delimiter="/")),
                        )
                        for page in pages:
                            for obj in page.get("Contents", []):
                                if obj["Key"].endswith((".gz", ".tsv", ".csv")):
                                    day_keys.append(obj["Key"])
                    else:
                        resp = await loop.run_in_executor(
                            _s3_executor,
                            lambda p=prefix: s3.list_objects_v2(Bucket=bucket, Prefix=p, Delimiter="/"),
                        )
                        for obj in resp.get("Contents", []):
                            if obj["Key"].endswith((".gz", ".tsv", ".csv")):
                                day_keys.append(obj["Key"])
                except ClientError:
                    pass

            logger.info("s3_day_scan", date=date_str, files_found=len(day_keys), fetch_mode=fetch_mode)

            # Apply limits only in sampled mode
            if fetch_mode == "sampled":
                if len(day_keys) > MAX_FILES_PER_DAY:
                    logger.warning("fetch_day_too_many_files", date=date_str, count=len(day_keys), limit=MAX_FILES_PER_DAY)
                    day_keys.sort(reverse=True)
                    day_keys = day_keys[:MAX_FILES_PER_DAY]
                if total_files + len(day_keys) > MAX_FILES_PER_JOB:
                    job["status"] = "failed"
                    job["error"] = f"Too many files ({total_files + len(day_keys)}). Use 'Full' mode or reduce date range."
                    job["progress"] = 0
                    return

            job["status"] = "streaming"
            job["message"] = f"Day {date_str}: streaming {len(day_keys)} files..."

            # Stream S3 files → parse in memory, no disk write for raw data
            day_entries: list[dict[str, object]] = []
            for file_idx, key in enumerate(day_keys):
                if _is_cancelled():
                    _mark_cancelled(f"Cancelled during {date_str} ({file_idx}/{len(day_keys)} files)")
                    return
                try:
                    rows = await loop.run_in_executor(
                        _s3_executor,
                        lambda k=key: _stream_s3_gz(s3, bucket, k, max_rows=stream_limit),
                    )
                    day_entries.extend(rows)
                    logger.info("s3_stream_rows", file=key.split("/")[-1], rows=len(rows))
                except Exception as exc:
                    logger.warning("fetch_job_file_error", job_id=job_id, key=key, error=str(exc))

                if _is_cancelled():
                    _mark_cancelled(f"Cancelled during {date_str} ({file_idx + 1}/{len(day_keys)} files)")
                    return

                # Update progress within day
                job["files_downloaded"] = total_files + file_idx + 1
                job["rows_parsed"] = total_rows + len(day_entries)

            total_files += len(day_keys)
            total_rows += len(day_entries)
            cache_misses += 1

            # Save parsed results as parquet cache for analysis endpoint
            ppath = f"data/logs/{tenant_id}/{cp_code}/{date_str}.parquet"
            try:
                import pandas as pd
                Path(ppath).parent.mkdir(parents=True, exist_ok=True)
                df = pd.DataFrame(day_entries) if day_entries else pd.DataFrame()
                df.to_parquet(ppath, index=False)
                parquet_paths.append(ppath)

                duck.execute(
                    """INSERT OR REPLACE INTO log_fetch_cache
                       (cache_key, tenant_id, cp_code, fetch_date, files_count, rows_count, fetched_at, parquet_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [ck, tenant_id, cp_code, date_str, len(day_keys), len(day_entries),
                     datetime.now(timezone.utc).isoformat(), ppath],
                )
            except Exception as exc:
                logger.warning("fetch_cache_write_error", job_id=job_id, date=date_str, error=str(exc))

            # Update progress
            job["files_downloaded"] = total_files
            job["rows_parsed"] = total_rows
            job["cache_hits"] = cache_hits
            job["cache_misses"] = cache_misses
            job["total_files"] = total_files
            pct = 15 + int((day_idx + 1) / len(dates) * 80)
            job["progress"] = min(pct, 95)
            job["message"] = f"Day {date_str}: {len(day_entries):,} rows from {len(day_keys)} files"
            logger.info("fetch_day_complete", job_id=job_id, date=date_str, rows=len(day_entries), files=len(day_keys))

        # Done — store parquet paths for analysis endpoint
        job["status"] = "completed"
        job["progress"] = 100
        job["parquet_paths"] = parquet_paths
        job["message"] = f"Completed: {total_rows:,} rows from {total_files} files ({cache_hits} cached, {cache_misses} fetched)"

        # Save to DuckDB history
        try:
            duck.execute(
                """INSERT OR REPLACE INTO fetch_job_history
                   (job_id, tenant_id, cp_code, start_date, end_date, total_files, total_rows,
                    cache_hits, cache_misses, status, created_at, completed_at, parquet_paths)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [job_id, tenant_id, cp_code, dates[0], dates[-1], total_files, total_rows,
                 cache_hits, cache_misses, "completed",
                 job.get("created_at", datetime.now(timezone.utc).isoformat()),
                 datetime.now(timezone.utc).isoformat(),
                 json.dumps(parquet_paths)],
            )
        except Exception as exc:
            logger.warning("fetch_history_write_error", job_id=job_id, error=str(exc))

        logger.info("fetch_job_status", job_id=job_id, status="completed",
                     rows=total_rows, files=total_files, cache_hits=cache_hits)

    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["progress"] = 0
        logger.error("fetch_job_error", job_id=job_id, error=str(exc))


@router.get("/akamai/jobs/{job_id}")
async def get_fetch_job(
    job_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Poll fetch job status — check in-memory first, then DuckDB."""
    job = _fetch_jobs.get(job_id)
    if job:
        return job
    # Fallback to DuckDB history
    _ensure_duckdb_schema(duck)
    try:
        row = duck.fetch_one(
            "SELECT * FROM fetch_job_history WHERE job_id = ?", [job_id],
        )
        if row:
            return {**row, "progress": 100}
    except Exception:
        pass
    return {"job_id": job_id, "status": "not_found", "error": "Job not found"}


@router.post("/akamai/jobs/{job_id}/cancel")
async def cancel_fetch_job(
    job_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Cancel a running fetch job."""
    logger.info("job_cancel_requested", job_id=job_id, current_status=_fetch_jobs.get(job_id, {}).get("status"))
    job = _fetch_jobs.get(job_id)
    if not job:
        return {"cancelled": False, "job_id": job_id, "status": "not_found", "message": f"Job {job_id} not found"}
    if job["status"] in ("completed", "failed", "cancelled"):
        return {"cancelled": False, "job_id": job_id, "status": job["status"], "message": f"Job already {job['status']}"}
    job["cancelled"] = True
    return {"cancelled": True, "job_id": job_id, "status": "cancelling", "message": "Cancel requested"}


@router.get("/akamai/jobs")
async def list_fetch_jobs(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> list[dict[str, Any]]:
    """List fetch job history from DuckDB."""
    _ensure_duckdb_schema(duck)
    try:
        rows = duck.fetch_all(
            "SELECT * FROM fetch_job_history WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 20",
            [ctx.tenant_id],
        )
        return rows
    except Exception:
        return []


# ── Analysis endpoint ──


_CACHE_STATUS_LABELS = {
    0: "Miss", 1: "Hit", 2: "Revalidated", 3: "Hit-Stale",
    4: "Hit-Synthetic", 5: "Hit-BW-Optimized", 6: "Hit-Prefetch",
    7: "Hit-Remote", 8: "SureHit", 9: "Non-Cacheable",
}


def _run_analysis(df: Any) -> dict[str, Any]:
    """Run 13 aggregation analyses on a pandas DataFrame of parsed logs."""
    import numpy as np
    import pandas as pd

    if df is None or df.empty:
        return {"summary": {}, "charts": {}}

    total_rows = len(df)

    # Coerce numeric columns (parquet may store as object/string)
    for col in ("bytes", "client_bytes", "status_code", "cache_hit", "cache_status",
                "transfer_time_ms", "dns_lookup_time_ms", "turn_around_time_ms",
                "response_body_size", "version"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    total_bytes = int(df["bytes"].sum()) if "bytes" in df.columns else 0
    total_gb = round(total_bytes / (1024**3), 3)
    if "bytes" in df.columns:
        bytes_col = df["bytes"].dropna()
        logger.info("analysis_bytes_diagnostic",
                     sum_bytes_raw=total_bytes, mean_bytes=round(float(bytes_col.mean()), 1) if len(bytes_col) else 0,
                     max_bytes=int(bytes_col.max()) if len(bytes_col) else 0,
                     min_bytes=int(bytes_col.min()) if len(bytes_col) else 0,
                     total_gb=total_gb, non_null_count=len(bytes_col))

    # Error rate
    error_count = int((df["status_code"] >= 400).sum()) if "status_code" in df.columns else 0
    error_rate_pct = round(error_count / total_rows * 100, 2) if total_rows else 0

    # Cache hit ratio — coerced to numeric above
    if "cache_hit" in df.columns:
        cache_valid = df["cache_hit"].dropna()
        cache_hits = int((cache_valid == 1).sum())
        cache_hit_pct = round(cache_hits / len(cache_valid) * 100, 2) if len(cache_valid) else 0
    else:
        cache_hit_pct = 0

    # Avg latency
    avg_latency = round(float(df["transfer_time_ms"].mean()), 1) if "transfer_time_ms" in df.columns and df["transfer_time_ms"].notna().any() else 0

    # Unique countries + top 5 log
    unique_countries = int(df["country"].nunique()) if "country" in df.columns else 0
    if "country" in df.columns:
        top5 = df["country"].dropna().value_counts().head(5)
        logger.info("analysis_top_countries", top5={str(k): int(v) for k, v in top5.items()})

    summary = {
        "total_rows": total_rows,
        "total_gb": total_gb,
        "avg_latency_ms": avg_latency,
        "error_rate_pct": error_rate_pct,
        "cache_hit_pct": cache_hit_pct,
        "unique_countries": unique_countries,
    }

    charts: dict[str, list[dict]] = {}

    # 1. Status code distribution
    if "status_code" in df.columns:
        sc = df["status_code"].dropna().astype(int).value_counts().sort_index().head(20)
        charts["status_code_distribution"] = [{"status": int(k), "count": int(v)} for k, v in sc.items()]
        # Diagnostic: top 5 status codes
        top5_sc = sc.head(5)
        logger.info("chart_status_codes",
                     top5={f"status_{int(k)}": f"{int(v)} ({round(int(v)/total_rows*100,1)}%)" for k, v in top5_sc.items()})

    # 2. Cache hit ratio (show both % labels and raw counts)
    if "cache_hit" in df.columns:
        ch = df["cache_hit"].dropna().astype(int).value_counts()
        ch_total = int(ch.sum())
        null_count = int(df["cache_hit"].isna().sum())
        hit_count = int(ch.get(1, 0))
        miss_count = int(ch.get(0, 0))
        hit_pct = round(hit_count / ch_total * 100, 1) if ch_total else 0
        miss_pct = round(miss_count / ch_total * 100, 1) if ch_total else 0
        logger.info("chart_cache_hit",
                     hit_count=hit_count, miss_count=miss_count,
                     hit_pct=hit_pct, miss_pct=miss_pct, null_count=null_count)
        charts["cache_hit_ratio"] = [
            {"label": f"Hit ({hit_pct}%)", "count": hit_count},
            {"label": f"Miss ({miss_pct}%)", "count": miss_count},
        ]

    # 3. Bandwidth by hour (bytes as MB, fill missing hours with 0)
    if "req_time_sec" in df.columns and "bytes" in df.columns:
        # Sample 5 bytes values for magnitude check
        bytes_sample = df["bytes"].dropna().head(5).tolist()
        logger.info("chart_bandwidth_bytes_sample", sample=bytes_sample)

        df_bw = df[df["req_time_sec"].notna()].copy()
        df_bw["hour"] = pd.to_datetime(df_bw["req_time_sec"], unit="s", utc=True).dt.hour
        bw = df_bw.groupby("hour")["bytes"].sum()
        # Fill missing hours with 0 for complete 0-23 range
        all_hours = pd.Series(0, index=range(24), dtype="int64")
        for h in bw.index:
            all_hours[int(h)] = int(bw[h])
        total_mb = round(int(all_hours.sum()) / (1024**2), 1)
        hours_with_data = int((all_hours > 0).sum())
        mean_mb = round(total_mb / hours_with_data, 1) if hours_with_data else 0
        max_hour = int(all_hours.idxmax()) if hours_with_data else 0
        min_hour_val = all_hours[all_hours > 0]
        min_hour = int(min_hour_val.idxmin()) if len(min_hour_val) else 0
        logger.info("chart_bandwidth_by_hour",
                     total_mb=total_mb, mean_mb_per_hour=mean_mb,
                     max_hour=max_hour, min_hour=min_hour, hours_with_data=hours_with_data)
        charts["bandwidth_by_hour"] = [{"hour": h, "mb": round(int(all_hours[h]) / (1024**2), 1)} for h in range(24)]

    # 4. Top error paths (last 50 chars for display, full in tooltip)
    if "status_code" in df.columns and "req_path" in df.columns:
        errors = df[df["status_code"] >= 400]
        top_err = errors["req_path"].value_counts().head(10)
        charts["top_error_paths"] = [{"path": str(k)[-50:], "full_path": str(k), "count": int(v)} for k, v in top_err.items()]

    # 5. Latency percentiles
    if "transfer_time_ms" in df.columns:
        vals = df["transfer_time_ms"].dropna()
        if len(vals) > 0:
            charts["latency_percentiles"] = [
                {"percentile": "p50", "ms": round(float(vals.quantile(0.5)), 1)},
                {"percentile": "p75", "ms": round(float(vals.quantile(0.75)), 1)},
                {"percentile": "p95", "ms": round(float(vals.quantile(0.95)), 1)},
                {"percentile": "p99", "ms": round(float(vals.quantile(0.99)), 1)},
            ]

    # 6. Top Cities (city + country label)
    if "city" in df.columns:
        df_geo = df.copy()
        df_geo["city_clean"] = df_geo["city"].fillna("Unknown").replace({"": "Unknown", "-": "Unknown"})
        if "country" in df_geo.columns:
            df_geo["city_label"] = df_geo["city_clean"] + " (" + df_geo["country"].fillna("??") + ")"
        else:
            df_geo["city_label"] = df_geo["city_clean"]
        geo = df_geo["city_label"].value_counts().head(15)
        charts["geo_distribution"] = [{"city": str(k), "count": int(v)} for k, v in geo.items()]
    elif "country" in df.columns:
        geo = df["country"].dropna().value_counts().head(15)
        charts["geo_distribution"] = [{"city": str(k), "count": int(v)} for k, v in geo.items()]

    # 7. Content type breakdown
    if "content_type" in df.columns:
        ct = df["content_type"].dropna().value_counts().head(10)
        charts["content_type_breakdown"] = [{"type": str(k)[:40], "count": int(v)} for k, v in ct.items()]

    # 8. Cache status breakdown (robust float→int→label)
    if "cache_status" in df.columns:
        cs_raw = pd.to_numeric(df["cache_status"], errors="coerce").dropna()
        cs = cs_raw.astype(int).value_counts().sort_index()
        charts["cache_status_breakdown"] = [
            {"status": _CACHE_STATUS_LABELS.get(int(k), f"Unknown({k})"), "count": int(v)}
            for k, v in cs.items()
        ]

    # 9. Error rate trend (hourly, full 24h)
    if "req_time_sec" in df.columns and "status_code" in df.columns:
        df_hr = df[df["req_time_sec"].notna()].copy()
        df_hr["hour"] = pd.to_datetime(df_hr["req_time_sec"], unit="s", utc=True).dt.hour
        hourly = df_hr.groupby("hour").agg(
            total=("status_code", "count"),
            errors=("status_code", lambda x: (x >= 400).sum()),
        )
        hourly = hourly.reindex(range(24), fill_value=0)
        hourly["error_rate"] = (hourly["errors"] / hourly["total"].replace(0, 1) * 100).round(2)
        charts["error_rate_trend"] = [{"hour": h, "error_rate": float(hourly.loc[h, "error_rate"])} for h in range(24)]

    # 10. Bytes vs client_bytes (hourly, full 24h, as MB)
    if "req_time_sec" in df.columns and "bytes" in df.columns and "client_bytes" in df.columns:
        df_bc = df[df["req_time_sec"].notna()].copy()
        df_bc["hour"] = pd.to_datetime(df_bc["req_time_sec"], unit="s", utc=True).dt.hour
        bc = df_bc.groupby("hour").agg(bytes=("bytes", "sum"), client_bytes=("client_bytes", "sum"))
        bc = bc.reindex(range(24), fill_value=0)
        charts["bytes_vs_client"] = [
            {"hour": h, "server_mb": round(int(bc.loc[h, "bytes"]) / (1024**2), 1), "client_mb": round(int(bc.loc[h, "client_bytes"]) / (1024**2), 1)}
            for h in range(24)
        ]

    # 11. Top 10 Client IPs by Bandwidth (full hash in data, truncated in label)
    if "client_ip" in df.columns and "bytes" in df.columns:
        ip_bw = df.groupby("client_ip")["bytes"].sum().sort_values(ascending=False).head(10)
        charts["top_client_ips"] = [{"ip": str(k)[:12] + "...", "full_ip": str(k), "mb": round(int(v) / (1024**2), 1)} for k, v in ip_bw.items()]

    # 12. Request Volume by Hour (full 24h)
    if "req_time_sec" in df.columns:
        df_rv = df[df["req_time_sec"].notna()].copy()
        df_rv["hour"] = pd.to_datetime(df_rv["req_time_sec"], unit="s", utc=True).dt.hour
        rv = df_rv.groupby("hour").size()
        rv = rv.reindex(range(24), fill_value=0)
        charts["request_volume_by_hour"] = [{"hour": h, "requests": int(rv[h])} for h in range(24)]

    # 13. Anomaly Timeline (full 24h, z-score on transfer_time_ms per hour)
    if "req_time_sec" in df.columns and "transfer_time_ms" in df.columns:
        df_at = df[df["req_time_sec"].notna() & df["transfer_time_ms"].notna()].copy()
        df_at["hour"] = pd.to_datetime(df_at["req_time_sec"], unit="s", utc=True).dt.hour
        hourly_lat = df_at.groupby("hour")["transfer_time_ms"].mean()
        hourly_lat = hourly_lat.reindex(range(24), fill_value=0)
        mean_val = hourly_lat[hourly_lat > 0].mean() if (hourly_lat > 0).any() else 0
        std_val = hourly_lat[hourly_lat > 0].std() if (hourly_lat > 0).any() else 0
        result_at = []
        for h in range(24):
            avg_ms = float(hourly_lat[h])
            z = round((avg_ms - mean_val) / std_val, 2) if std_val and std_val > 0 and avg_ms > 0 else 0.0
            anomaly = 1 if abs(z) > 2.5 else 0
            result_at.append({"hour": h, "avg_ms": round(avg_ms, 1), "z_score": z, "anomaly": anomaly})
        charts["anomaly_timeline"] = result_at

    return {"summary": summary, "charts": charts}


@router.get("/akamai/analysis/{job_id}")
async def get_analysis(
    job_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Load parsed data for a job and return 10 chart analyses + summary."""
    import json
    from pathlib import Path

    import pandas as pd

    # Get parquet paths from in-memory job or DuckDB history
    parquet_paths: list[str] = []
    job = _fetch_jobs.get(job_id)
    if job and job.get("parquet_paths"):
        parquet_paths = job["parquet_paths"]
    else:
        _ensure_duckdb_schema(duck)
        try:
            row = duck.fetch_one("SELECT parquet_paths FROM fetch_job_history WHERE job_id = ?", [job_id])
            if row and row.get("parquet_paths"):
                parquet_paths = json.loads(row["parquet_paths"])
        except Exception:
            pass

    if not parquet_paths:
        return {"error": "No data found for this job. Run fetch first.", "summary": {}, "charts": {}}

    # Load all parquet files into a single DataFrame
    dfs = []
    for p in parquet_paths:
        if Path(p).exists():
            try:
                dfs.append(pd.read_parquet(p))
            except Exception as exc:
                logger.warning("analysis_parquet_read_error", path=p, error=str(exc))

    if not dfs:
        return {"error": "Parquet files not found. Re-fetch logs.", "summary": {}, "charts": {}}

    df = pd.concat(dfs, ignore_index=True)
    logger.info("analysis_data_loaded", job_id=job_id, rows=len(df), total_columns=len(df.columns), columns=sorted(df.columns.tolist()))

    return _run_analysis(df)


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
                    # model_dump excludes_none=False keeps all fields including None
                    all_entries.append(entry.model_dump())
                files_scanned += 1
            except Exception:
                logger.warning("structure_analyze_file_error", key=key)
                continue

        logger.info(
            "structure_analyze_parsed",
            rows_parsed=len(all_entries),
            files_scanned=files_scanned,
            fields_found=len(all_entries[0]) if all_entries else 0,
        )

        if not all_entries:
            return {"error": "Files found but no rows could be parsed. Check file format.", **_empty}

        # Analyze fields
        fields = _analyze_fields(all_entries)

        # Merge saved category mappings (DB saved > DS2 default > None)
        mappings = await db.fetch_all(
            "SELECT field_name, category FROM field_category_mappings WHERE tenant_id = ?",
            (ctx.tenant_id,),
        )
        mapping_dict = {m["field_name"]: m["category"] for m in mappings}
        for f in fields:
            fname = str(f["field_name"])
            saved = mapping_dict.get(fname)
            f["current_category"] = saved or DS2_DEFAULT_CATEGORIES.get(fname)

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
    await _ensure_schema(db)
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
    await _ensure_schema(db)
    rows = await db.fetch_all(
        "SELECT * FROM field_category_mappings WHERE tenant_id = ? ORDER BY field_name",
        (ctx.tenant_id,),
    )
    return [dict(r) for r in rows]


# ── Anomaly Rules ──


class AnomalyRulePayload(BaseModel):
    name: str
    field: str
    operator: str  # "not_in" | "gt" | "lt" | "eq" | "contains"
    value: str
    severity: str = "medium"
    description: str = ""
    is_active: int = 1


def _get_mask(df: Any, field: str, op: str, val: str) -> Any:
    """Apply operator to get boolean mask. Returns (mask, error_str|None)."""
    import json

    col = df[field].dropna()

    if op == "not_in":
        try:
            allowed = json.loads(val) if val.startswith("[") else [v.strip() for v in val.split(",")]
        except Exception:
            allowed = [val]
        return ~col.astype(str).isin([str(a) for a in allowed]), None
    elif op == "gt":
        import pandas as pd
        col_num = pd.to_numeric(col, errors="coerce").dropna()
        return col_num > float(val), None
    elif op == "lt":
        import pandas as pd
        col_num = pd.to_numeric(col, errors="coerce").dropna()
        return col_num < float(val), None
    elif op == "eq":
        return col.astype(str) == str(val), None
    elif op == "contains":
        return col.astype(str).str.contains(str(val), case=False, na=False), None
    return None, f"Unknown operator '{op}'"


def _build_detail(rule: dict[str, Any], df: Any, affected_df: Any) -> dict[str, Any]:
    """Build breakdown, top_offenders, timeline for a triggered rule."""
    import pandas as pd

    field = rule["field"]
    op = rule["operator"]
    detail: dict[str, Any] = {"breakdown": [], "top_offenders": [], "timeline": []}

    # Timeline: hourly count of affected rows
    if "req_time_sec" in affected_df.columns and not affected_df.empty:
        ts = affected_df[affected_df["req_time_sec"].notna()].copy()
        if not ts.empty:
            ts["hour"] = pd.to_datetime(ts["req_time_sec"].astype(float), unit="s", utc=True).dt.hour
            hourly = ts.groupby("hour").size().reset_index(name="count")
            detail["timeline"] = [{"hour": int(r["hour"]), "count": int(r["count"])} for _, r in hourly.iterrows()]

    # Country-specific breakdown (not_in on country)
    if field == "country" and op == "not_in" and not affected_df.empty:
        grp = affected_df.groupby("country").agg(
            request_count=("country", "size"),
            total_bytes=("bytes", lambda x: x.sum() if "bytes" in affected_df.columns else 0),
        ).reset_index().sort_values("request_count", ascending=False)
        aff_total = len(affected_df)
        detail["breakdown"] = [
            {"country": str(r["country"]), "request_count": int(r["request_count"]),
             "total_bytes_mb": round(int(r["total_bytes"]) / (1024**2), 1),
             "pct_of_affected": round(int(r["request_count"]) / aff_total * 100, 1) if aff_total else 0}
            for _, r in grp.head(20).iterrows()
        ]

        # Top offenders by IP
        if "client_ip" in affected_df.columns:
            ip_grp = affected_df.groupby("client_ip").agg(
                country=("country", "first"),
                request_count=("client_ip", "size"),
                total_bytes=("bytes", lambda x: x.sum() if "bytes" in affected_df.columns else 0),
                first_seen=("req_time_sec", "min"),
                last_seen=("req_time_sec", "max"),
            ).reset_index().sort_values("request_count", ascending=False).head(10)

            offenders = []
            for _, r in ip_grp.iterrows():
                ip_rows = affected_df[affected_df["client_ip"] == r["client_ip"]]
                top_paths = ip_rows["req_path"].value_counts().head(3).index.tolist() if "req_path" in ip_rows.columns else []
                fs = pd.Timestamp(r["first_seen"], unit="s", tz="UTC").strftime("%d.%m.%Y %H:%M UTC") if pd.notna(r["first_seen"]) else "—"
                ls = pd.Timestamp(r["last_seen"], unit="s", tz="UTC").strftime("%d.%m.%Y %H:%M UTC") if pd.notna(r["last_seen"]) else "—"
                offenders.append({
                    "client_ip": str(r["client_ip"]),
                    "country": str(r["country"]),
                    "request_count": int(r["request_count"]),
                    "total_bytes_mb": round(int(r["total_bytes"]) / (1024**2), 1),
                    "first_seen": fs,
                    "last_seen": ls,
                    "top_paths": [str(p)[:60] for p in top_paths],
                })
            detail["top_offenders"] = offenders

    # Session duration (gt on computed field)
    elif field == "session_duration_hours" and op == "gt" and "client_ip" in df.columns and "req_time_sec" in df.columns:
        threshold = float(rule["value"])
        ip_sessions = df.groupby("client_ip").agg(
            min_ts=("req_time_sec", "min"),
            max_ts=("req_time_sec", "max"),
            request_count=("client_ip", "size"),
            total_bytes=("bytes", lambda x: x.sum() if "bytes" in df.columns else 0),
        ).reset_index()
        ip_sessions["session_hours"] = ((ip_sessions["max_ts"] - ip_sessions["min_ts"]) / 3600).round(2)
        flagged = ip_sessions[ip_sessions["session_hours"] > threshold].sort_values("session_hours", ascending=False).head(10)

        offenders = []
        for _, r in flagged.iterrows():
            ip_rows = df[df["client_ip"] == r["client_ip"]]
            countries = ip_rows["country"].dropna().unique().tolist() if "country" in ip_rows.columns else []
            fs = pd.Timestamp(r["min_ts"], unit="s", tz="UTC").strftime("%d.%m.%Y %H:%M UTC") if pd.notna(r["min_ts"]) else "—"
            ls = pd.Timestamp(r["max_ts"], unit="s", tz="UTC").strftime("%d.%m.%Y %H:%M UTC") if pd.notna(r["max_ts"]) else "—"
            offenders.append({
                "client_ip": str(r["client_ip"]),
                "session_hours": float(r["session_hours"]),
                "request_count": int(r["request_count"]),
                "total_bytes_mb": round(int(r["total_bytes"]) / (1024**2), 1),
                "first_seen": fs,
                "last_seen": ls,
                "countries": [str(c) for c in countries[:5]],
            })
        detail["top_offenders"] = offenders
        detail["breakdown"] = [
            {"label": f">{threshold}h", "count": len(flagged)},
            {"label": f"<={threshold}h", "count": len(ip_sessions) - len(flagged)},
        ]

    # Generic: top offenders for any field-based rule
    elif not affected_df.empty and "client_ip" in affected_df.columns:
        ip_grp = affected_df.groupby("client_ip").size().reset_index(name="request_count")
        ip_grp = ip_grp.sort_values("request_count", ascending=False).head(10)
        detail["top_offenders"] = [
            {"client_ip": str(r["client_ip"]), "request_count": int(r["request_count"])}
            for _, r in ip_grp.iterrows()
        ]

    return detail


def _evaluate_rule(rule: dict[str, Any], df: Any) -> dict[str, Any]:
    """Evaluate a single anomaly rule against a DataFrame with detailed breakdown."""
    import pandas as pd

    field = rule["field"]
    op = rule["operator"]
    val = rule["value"]
    total = len(df)
    base = {"rule_id": rule["id"], "rule_name": rule["name"], "severity": rule["severity"]}

    # Handle computed fields (session_duration_hours)
    if field == "session_duration_hours" and "client_ip" in df.columns and "req_time_sec" in df.columns:
        threshold = float(val)
        ip_sessions = df.groupby("client_ip").agg(
            min_ts=("req_time_sec", "min"), max_ts=("req_time_sec", "max"),
            request_count=("client_ip", "size"),
        ).reset_index()
        ip_sessions["session_hours"] = ((ip_sessions["max_ts"] - ip_sessions["min_ts"]) / 3600).round(2)
        flagged_ips = set(ip_sessions[ip_sessions["session_hours"] > threshold]["client_ip"])
        affected_mask = df["client_ip"].isin(flagged_ips)
        affected = int(affected_mask.sum())
        affected_df = df[affected_mask]
        pct = round(affected / total * 100, 2) if total else 0
        detail = _build_detail(rule, df, affected_df)
        return {**base, "affected_rows": affected, "pct_of_total": pct,
                "sample_values": list(flagged_ips)[:5], **detail}

    if field not in df.columns:
        return {**base, "affected_rows": 0, "pct_of_total": 0, "sample_values": [],
                "breakdown": [], "top_offenders": [], "timeline": [],
                "error": f"Field '{field}' not in data"}

    mask, err = _get_mask(df, field, op, val)
    if err:
        return {**base, "affected_rows": 0, "pct_of_total": 0, "sample_values": [],
                "breakdown": [], "top_offenders": [], "timeline": [], "error": err}

    # Align mask index with df
    affected_df = df.loc[mask.index[mask]] if mask is not None and mask.any() else df.iloc[:0]
    affected = len(affected_df)
    samples = df[field].loc[mask.index[mask]].astype(str).unique()[:5].tolist() if affected > 0 else []
    pct = round(affected / total * 100, 2) if total else 0

    detail = _build_detail(rule, df, affected_df)

    return {**base, "affected_rows": affected, "pct_of_total": pct,
            "sample_values": samples, **detail}


@router.get("/anomaly-rules")
async def list_anomaly_rules(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    await _ensure_schema(db)
    rows = await db.fetch_all(
        "SELECT * FROM anomaly_rules WHERE tenant_id = ? ORDER BY created_at", (ctx.tenant_id,),
    )
    return [dict(r) for r in rows]


@router.post("/anomaly-rules")
async def create_anomaly_rule(
    payload: AnomalyRulePayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    rule_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO anomaly_rules (id, tenant_id, name, field, operator, value, severity, description, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rule_id, ctx.tenant_id, payload.name, payload.field, payload.operator,
         payload.value, payload.severity, payload.description, payload.is_active),
    )
    return {"id": rule_id, "status": "created"}


@router.patch("/anomaly-rules/{rule_id}")
async def update_anomaly_rule(
    rule_id: str,
    payload: AnomalyRulePayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    await _ensure_schema(db)
    await db.execute(
        """UPDATE anomaly_rules SET name=?, field=?, operator=?, value=?, severity=?, description=?, is_active=?
           WHERE id=? AND tenant_id=?""",
        (payload.name, payload.field, payload.operator, payload.value,
         payload.severity, payload.description, payload.is_active, rule_id, ctx.tenant_id),
    )
    return {"status": "updated", "id": rule_id}


@router.delete("/anomaly-rules/{rule_id}")
async def delete_anomaly_rule(
    rule_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    await _ensure_schema(db)
    await db.execute("DELETE FROM anomaly_rules WHERE id=? AND tenant_id=?", (rule_id, ctx.tenant_id))
    return {"status": "deleted", "id": rule_id}


@router.post("/anomaly-rules/evaluate")
async def evaluate_anomaly_rules(
    job_id: str = Query(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
    duck: DuckDBClient = Depends(get_duckdb),
) -> list[dict[str, Any]]:
    """Run all active rules against a job's DataFrame."""
    import json
    from pathlib import Path

    import pandas as pd

    await _ensure_schema(db)

    parquet_paths: list[str] = []
    job = _fetch_jobs.get(job_id)
    if job and job.get("parquet_paths"):
        parquet_paths = job["parquet_paths"]
    else:
        _ensure_duckdb_schema(duck)
        try:
            row = duck.fetch_one("SELECT parquet_paths FROM fetch_job_history WHERE job_id = ?", [job_id])
            if row and row.get("parquet_paths"):
                parquet_paths = json.loads(row["parquet_paths"])
        except Exception:
            pass

    if not parquet_paths:
        return [{"error": "No data found for this job."}]

    dfs = []
    for p in parquet_paths:
        if Path(p).exists():
            try:
                dfs.append(pd.read_parquet(p))
            except Exception:
                pass
    if not dfs:
        return [{"error": "Parquet files not found."}]

    df = pd.concat(dfs, ignore_index=True)

    rules = await db.fetch_all(
        "SELECT * FROM anomaly_rules WHERE tenant_id = ? AND is_active = 1", (ctx.tenant_id,),
    )
    return [_evaluate_rule(dict(rule), df) for rule in rules]


# ── Scheduled Tasks ──


class ScheduledTaskPayload(BaseModel):
    project_id: str | None = None
    name: str | None = None
    cp_code: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    schedule_cron: str | None = None
    fetch_mode: str | None = None
    is_active: int | None = None
    notify_emails: str | None = None


@router.get("/scheduled-tasks")
async def list_scheduled_tasks(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    await _ensure_schema(db)
    rows = await db.fetch_all(
        "SELECT * FROM scheduled_tasks WHERE tenant_id = ? ORDER BY created_at DESC", (ctx.tenant_id,),
    )
    return [dict(r) for r in rows]


@router.post("/scheduled-tasks")
async def create_scheduled_task(
    payload: ScheduledTaskPayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    if not payload.name:
        return {"error": "Task name is required."}
    task_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO scheduled_tasks
           (id, tenant_id, project_id, name, cp_code, s3_bucket, s3_prefix, schedule_cron, fetch_mode, is_active, notify_emails)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, ctx.tenant_id, payload.project_id, payload.name, payload.cp_code,
         payload.s3_bucket, payload.s3_prefix, payload.schedule_cron or "0 */6 * * *",
         payload.fetch_mode or "sampled", payload.is_active if payload.is_active is not None else 1,
         payload.notify_emails or "[]"),
    )
    return {"id": task_id, "status": "created"}


@router.patch("/scheduled-tasks/{task_id}")
async def update_scheduled_task(
    task_id: str,
    payload: ScheduledTaskPayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    await _ensure_schema(db)
    existing = await db.fetch_one("SELECT * FROM scheduled_tasks WHERE id=? AND tenant_id=?", (task_id, ctx.tenant_id))
    if not existing:
        return {"error": "Task not found"}
    old = dict(existing)

    def _m(field: str, new_val: Any) -> Any:
        return new_val if new_val is not None else old.get(field)

    await db.execute(
        """UPDATE scheduled_tasks SET name=?, project_id=?, cp_code=?, s3_bucket=?, s3_prefix=?,
           schedule_cron=?, fetch_mode=?, is_active=?, notify_emails=?
           WHERE id=? AND tenant_id=?""",
        (_m("name", payload.name), _m("project_id", payload.project_id),
         _m("cp_code", payload.cp_code), _m("s3_bucket", payload.s3_bucket),
         _m("s3_prefix", payload.s3_prefix), _m("schedule_cron", payload.schedule_cron),
         _m("fetch_mode", payload.fetch_mode),
         payload.is_active if payload.is_active is not None else old.get("is_active"),
         _m("notify_emails", payload.notify_emails),
         task_id, ctx.tenant_id),
    )
    return {"status": "updated", "id": task_id}


@router.delete("/scheduled-tasks/{task_id}")
async def delete_scheduled_task(
    task_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    await _ensure_schema(db)
    await db.execute("DELETE FROM scheduled_tasks WHERE id=? AND tenant_id=?", (task_id, ctx.tenant_id))
    return {"status": "deleted", "id": task_id}


@router.post("/scheduled-tasks/{task_id}/run")
async def run_scheduled_task(
    task_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Trigger an immediate fetch job for a scheduled task."""
    await _ensure_schema(db)
    task = await db.fetch_one("SELECT * FROM scheduled_tasks WHERE id=? AND tenant_id=?", (task_id, ctx.tenant_id))
    if not task:
        return {"error": "Task not found"}
    task_dict = dict(task)
    # Update last_run
    await db.execute(
        "UPDATE scheduled_tasks SET last_run=datetime('now'), last_status='running' WHERE id=?",
        (task_id,),
    )
    return {"status": "triggered", "task_id": task_id, "name": task_dict.get("name")}


# ── Email Settings ──


class EmailSettingsPayload(BaseModel):
    email_provider: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: str | None = None
    email_username: str | None = None
    email_password: str | None = None
    email_from_name: str | None = None


@router.post("/settings/email")
async def save_email_settings(
    payload: EmailSettingsPayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    """Save email notification settings."""
    await _ensure_schema(db)
    app_settings = get_settings()
    secret = app_settings.jwt_secret_key

    enc_user = encrypt(payload.email_username, secret) if payload.email_username else None
    enc_pass = encrypt(payload.email_password, secret) if payload.email_password else None

    row_id = f"{ctx.tenant_id}_global"
    existing = await db.fetch_one("SELECT * FROM settings WHERE id = ?", (row_id,))

    if existing:
        updates = []
        params: list[Any] = []
        if payload.email_provider is not None:
            updates.append("email_provider = ?")
            params.append(payload.email_provider)
        if payload.email_smtp_host is not None:
            updates.append("email_smtp_host = ?")
            params.append(payload.email_smtp_host)
        if payload.email_smtp_port is not None:
            updates.append("email_smtp_port = ?")
            params.append(payload.email_smtp_port)
        if enc_user is not None:
            updates.append("email_username_enc = ?")
            params.append(enc_user)
        if enc_pass is not None:
            updates.append("email_password_enc = ?")
            params.append(enc_pass)
        if payload.email_from_name is not None:
            updates.append("email_from_name = ?")
            params.append(payload.email_from_name)
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(row_id)
            await db.execute(f"UPDATE settings SET {', '.join(updates)} WHERE id = ?", tuple(params))
    return {"status": "saved"}


@router.post("/settings/email/test")
async def test_email(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Send a test email using saved SMTP settings."""
    await _ensure_schema(db)
    row = await db.fetch_one("SELECT * FROM settings WHERE tenant_id = ?", (ctx.tenant_id,))
    if not row:
        return {"success": False, "message": "No settings configured."}
    row_dict = dict(row)
    provider = row_dict.get("email_provider")
    if not provider:
        return {"success": False, "message": "Email provider not configured."}

    app_settings = get_settings()
    secret = app_settings.jwt_secret_key

    try:
        import smtplib
        from email.mime.text import MIMEText

        host = row_dict.get("email_smtp_host") or ("smtp.gmail.com" if provider == "gmail" else "")
        port = int(row_dict.get("email_smtp_port") or "587")
        username = decrypt(row_dict["email_username_enc"], secret) if row_dict.get("email_username_enc") else ""
        password = decrypt(row_dict["email_password_enc"], secret) if row_dict.get("email_password_enc") else ""
        from_name = row_dict.get("email_from_name") or "Captain logAR"

        if not username or not password:
            return {"success": False, "message": "Email credentials not configured."}

        msg = MIMEText("This is a test email from Captain logAR. If you received this, email is working.")
        msg["Subject"] = "Captain logAR — Test Email"
        msg["From"] = f"{from_name} <{username}>"
        msg["To"] = username

        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)

        return {"success": True, "message": f"Test email sent to {username}"}
    except Exception as exc:
        return {"success": False, "message": f"Email test failed: {exc}"}


# ── Agent Chat ──


class ChatRequest(BaseModel):
    message: str
    job_id: str | None = None
    conversation_id: str | None = None
    history: list[dict[str, str]] = []


def _build_chat_context(job_id: str | None) -> str:
    """Build analysis context string for the LLM from current job data."""
    if not job_id:
        return "No analysis data loaded. Answer general CDN questions."

    job = _fetch_jobs.get(job_id)
    if not job:
        return "Job data not available in memory."

    parts = [
        f"Date range: {job.get('start_date', '?')} to {job.get('end_date', '?')}",
        f"Total rows: {job.get('rows_parsed', 0):,}",
        f"Total files: {job.get('total_files', 0)}",
        f"Status: {job.get('status', '?')}",
        f"Cache hits: {job.get('cache_hits', 0)} days from cache, {job.get('cache_misses', 0)} days fetched",
    ]

    # Try to add analysis summary if parquet paths available
    if job.get("parquet_paths"):
        try:
            import pandas as pd
            from pathlib import Path

            dfs = []
            for p in job["parquet_paths"][:5]:
                if Path(p).exists():
                    dfs.append(pd.read_parquet(p))
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                for col in ("bytes", "status_code", "cache_hit", "transfer_time_ms"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                total = len(df)
                if "status_code" in df.columns:
                    errs = int((df["status_code"] >= 400).sum())
                    parts.append(f"Error rate: {round(errs/total*100, 1)}% ({errs:,} errors)")
                if "cache_hit" in df.columns:
                    hits = int((df["cache_hit"].dropna() == 1).sum())
                    valid = df["cache_hit"].dropna().shape[0]
                    parts.append(f"Cache hit: {round(hits/valid*100, 1) if valid else 0}%")
                if "transfer_time_ms" in df.columns:
                    avg = df["transfer_time_ms"].mean()
                    parts.append(f"Avg latency: {round(avg, 1)}ms")
                if "country" in df.columns:
                    top3 = df["country"].dropna().value_counts().head(3)
                    parts.append(f"Top countries: {', '.join(f'{k}({v})' for k, v in top3.items())}")
                if "bytes" in df.columns:
                    gb = round(int(df["bytes"].sum()) / (1024**3), 2)
                    parts.append(f"Total bandwidth: {gb} GB")
        except Exception:
            pass

    return "\n".join(parts)


def _generate_suggestions(job_id: str | None) -> list[str]:
    """Generate 4 context-aware chat suggestions."""
    suggestions = ["Summarize the key findings", "What should I investigate next?"]

    if not job_id:
        suggestions.extend(["What metrics matter for CDN performance?", "How does caching work in Akamai?"])
        return suggestions[:4]

    job = _fetch_jobs.get(job_id)
    if job and job.get("parquet_paths"):
        try:
            import pandas as pd
            from pathlib import Path

            dfs = []
            for p in job["parquet_paths"][:3]:
                if Path(p).exists():
                    dfs.append(pd.read_parquet(p))
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                for col in ("status_code", "cache_hit", "country"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce") if col != "country" else df[col]

                if "status_code" in df.columns:
                    err_rate = (df["status_code"] >= 400).sum() / len(df) * 100
                    if err_rate > 5:
                        suggestions.append(f"What's causing the {err_rate:.1f}% error rate?")
                if "country" in df.columns:
                    non_tr = df[df["country"].astype(str) != "TR"]
                    if len(non_tr) > 0:
                        suggestions.append("Which IPs accessed from outside Turkey?")
        except Exception:
            pass

    if len(suggestions) < 4:
        suggestions.extend(["Compare cache performance across hours", "Which content types have the most errors?"])
    return suggestions[:4]


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """AI chat powered by Captain logAR."""
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    context = _build_chat_context(payload.job_id)

    system_prompt = (
        "You are Captain logAR, an AI analyst for S Sport Plus CDN logs.\n"
        "You have access to the current analysis:\n"
        f"{context}\n\n"
        "Answer questions about CDN performance, errors, anomalies, and patterns.\n"
        "Be concise and actionable. Use Turkish if the user writes in Turkish."
    )

    # Build messages for multi-turn
    messages: list[dict[str, str]] = []
    for h in payload.history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": payload.message})

    try:
        from anthropic import AsyncAnthropic

        settings = get_settings()
        if not settings.anthropic_api_key:
            return {"response": "Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env", "conversation_id": conversation_id}

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )
        text = response.content[0].text if response.content else "No response generated."
        logger.info("chat_response", conversation_id=conversation_id, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
        return {"response": text, "conversation_id": conversation_id}
    except Exception as exc:
        logger.error("chat_error", error=str(exc))
        return {"response": f"Chat error: {exc}", "conversation_id": conversation_id}


@router.get("/chat/suggestions")
async def chat_suggestions(
    job_id: str | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, list[str]]:
    """Return context-aware chat suggestions."""
    return {"suggestions": _generate_suggestions(job_id)}


@router.get("/chat/api-status")
async def chat_api_status() -> dict[str, Any]:
    """Check if Anthropic API key is configured."""
    settings = get_settings()
    has_key = bool(settings.anthropic_api_key)
    return {"configured": has_key}
