"""Mock Data Generator API — source listing, schema browser, generate jobs, validation, export schemas."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import date, datetime, timezone
from itertools import combinations
from typing import Any

import aiosqlite
import structlog
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from backend.models.export_schema import (
    ExportSchema,
    ExportSchemaCreate,
    FieldSelection,
    JoinKey,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/mock-data-gen", tags=["mock-data-gen"])

# ── Source registry ──

SOURCE_INFO: list[dict[str, str]] = [
    {"name": "medianova", "display_name": "Medianova CDN", "description": "CDN access logs (32 fields)", "group": "CDN"},
    {"name": "origin_logs", "display_name": "Origin Server", "description": "Origin server events (4 types)", "group": "CDN"},
    {"name": "drm_widevine", "display_name": "Widevine DRM", "description": "Widevine license events", "group": "DRM"},
    {"name": "drm_fairplay", "display_name": "FairPlay DRM", "description": "FairPlay license events", "group": "DRM"},
    {"name": "player_events", "display_name": "Player Events", "description": "Player session event chains (7 types)", "group": "QoE"},
    {"name": "npaw", "display_name": "NPAW Analytics", "description": "Post-session QoE aggregates", "group": "QoE"},
    {"name": "api_logs", "display_name": "API Logs", "description": "API gateway access logs (13 endpoints)", "group": "Platform"},
    {"name": "newrelic", "display_name": "New Relic APM", "description": "APM transactions + infra + errors", "group": "Platform"},
    {"name": "crm", "display_name": "CRM/Subscriber", "description": "485K subscriber base + daily deltas", "group": "Business"},
    {"name": "epg", "display_name": "EPG", "description": "Electronic Program Guide", "group": "Business"},
    {"name": "billing", "display_name": "Billing", "description": "Billing transactions (8 types)", "group": "Business"},
    {"name": "push_notifications", "display_name": "Push Notifications", "description": "Push notification logs (10 types)", "group": "Business"},
    {"name": "app_reviews", "display_name": "App Reviews", "description": "App store reviews with sentiment", "group": "Business"},
]

# Schema registry — lazy loaded
_SCHEMA_MODULES: dict[str, tuple[str, str]] = {
    "medianova": ("apps.mock_data_gen.generators.medianova.schemas", "MedianovaLogEntry"),
    "origin_logs": ("apps.mock_data_gen.generators.origin_logs.schemas", "OriginLogEntry"),
    "drm_widevine": ("apps.mock_data_gen.generators.drm_widevine.schemas", "WidevineLogEntry"),
    "drm_fairplay": ("apps.mock_data_gen.generators.drm_fairplay.schemas", "FairPlayLogEntry"),
    "player_events": ("apps.mock_data_gen.generators.player_events.schemas", "PlayerEventEntry"),
    "npaw": ("apps.mock_data_gen.generators.npaw.schemas", "NPAWSessionEntry"),
    "api_logs": ("apps.mock_data_gen.generators.api_logs.schemas", "APILogEntry"),
    "newrelic": ("apps.mock_data_gen.generators.newrelic.schemas", "NewRelicAPMEntry"),
    "crm": ("apps.mock_data_gen.generators.crm.schemas", "SubscriberProfile"),
    "epg": ("apps.mock_data_gen.generators.epg.schemas", "EPGProgram"),
    "billing": ("apps.mock_data_gen.generators.billing.schemas", "BillingLogEntry"),
    "push_notifications": ("apps.mock_data_gen.generators.push_notifications.schemas", "PushNotificationEntry"),
    "app_reviews": ("apps.mock_data_gen.generators.app_reviews.schemas", "AppReviewEntry"),
}

# In-memory job tracking
_jobs: dict[str, dict[str, Any]] = {}


class GenerateRequest(BaseModel):
    sources: list[str]
    start_date: str
    end_date: str


# ── Endpoints ──


@router.get("/sources")
async def list_sources() -> list[dict]:
    """List all 13 data sources with status."""
    result = []
    for src in SOURCE_INFO:
        job_status = "idle"
        for job in _jobs.values():
            if src["name"] in job.get("sources", []) and job["status"] == "running":
                job_status = "running"
                break
        result.append({**src, "status": job_status})
    return result


@router.get("/sources/{source_name}/schema")
async def get_source_schema(source_name: str) -> dict:
    """Return field schema for a specific source."""
    if source_name not in _SCHEMA_MODULES:
        return {"error": f"Unknown source: {source_name}", "fields": []}

    import importlib
    mod_path, class_name = _SCHEMA_MODULES[source_name]
    mod = importlib.import_module(mod_path)
    model_cls = getattr(mod, class_name)
    field_cats = getattr(mod, "FIELD_CATEGORIES", {})
    field_descs = getattr(mod, "FIELD_DESCRIPTIONS", {})

    fields = []
    for fname, finfo in model_cls.model_fields.items():
        annotation = finfo.annotation
        type_str = getattr(annotation, "__name__", str(annotation))
        fields.append({
            "field_name": fname,
            "type": type_str,
            "category": field_cats.get(fname, "unknown"),
            "description": field_descs.get(fname, ""),
            "optional": not finfo.is_required(),
        })

    categories = sorted(set(field_cats.values()))
    return {
        "source_name": source_name,
        "field_count": len(fields),
        "categories": categories,
        "fields": fields,
    }


# Sample values for field type inference
_SAMPLE_VALUES: dict[str, dict[str, str]] = {
    "medianova": {
        "request_id": "550e8400-e29b-41d4-a716-446655440000", "request_method": "GET",
        "request_uri": "/live/s_sport_1/1080/seg_123.ts", "request_time": "0.012",
        "scheme": "https", "http_protocol": "HTTP/2.0", "http_host": "cdn.ssport.com.tr",
        "http_user_agent": "ExoPlayer/2.18.7", "status": "200", "content_type": "video/MP2T",
        "proxy_cache_status": "HIT", "body_bytes_sent": "524288", "bytes_sent": "524800",
        "timestamp": "2026-03-04T19:30:00Z", "remote_addr": "a1b2c3d4e5f6a7b8",
        "client_port": "54321", "asn": "AS9121", "country_code": "TR", "isp": "Turk Telekom",
        "tcp_info_rtt": "25", "tcp_info_rtt_var": "5", "ssl_protocol": "TLSv1.3",
        "ssl_cipher": "TLS_AES_256_GCM_SHA384", "resource_uuid": "r-abcdef12",
        "account_type": "enterprise", "channel": "s_sport_1", "edge_node": "ist-01",
        "stream_type": "live", "request_param": "null", "http_referrer": "null",
        "upstream_response_time": "null", "sent_http_content_length": "524288", "via": "1.1 medianova",
    },
}

_TYPE_INFERENCE: dict[str, str] = {
    "str": "string", "int": "integer", "float": "float", "bool": "boolean",
}


def _infer_field_type(field_name: str, type_str: str) -> str:
    """Infer a friendly type name from field name and annotation."""
    name_lower = field_name.lower()
    if "timestamp" in name_lower or name_lower in ("created_at", "delivered_at", "opened_at", "start_time", "end_time"):
        return "datetime"
    if name_lower.endswith("_id") and "uuid" not in name_lower:
        if "subscriber" in name_lower or "session" in name_lower or "content" in name_lower:
            return "string"
        return "uuid"
    if name_lower == "event_id" or name_lower == "request_id" or name_lower == "notification_id" or name_lower == "review_id" or name_lower == "transaction_id" or name_lower == "program_id":
        return "uuid"
    if "ip" in name_lower and "hash" not in name_lower:
        return "ip_address"
    if name_lower.endswith("_ms") or name_lower.endswith("_s") or name_lower in ("status", "status_code", "rating", "port", "client_port", "pod_count", "retry_count"):
        return "integer"
    if name_lower.endswith("_pct") or name_lower.endswith("_rate") or name_lower.endswith("_ratio") or name_lower in ("amount_tl", "completion_rate", "apdex_score", "qoe_score", "youbora_score", "churn_risk_score"):
        return "float"
    if name_lower.startswith("is_") or name_lower in ("delivered", "opened", "conversion", "auto_renew", "developer_response", "error_fatal", "cache_hit", "pre_scale_required"):
        return "boolean"
    for base, friendly in _TYPE_INFERENCE.items():
        if base in type_str.lower():
            return friendly
    return "string"


def _get_sample_value(source_name: str, field_name: str, field_type: str) -> str:
    """Return a realistic sample value for a field."""
    # Check explicit samples first
    src_samples = _SAMPLE_VALUES.get(source_name, {})
    if field_name in src_samples:
        return src_samples[field_name]
    # Generic samples by type
    if field_type == "uuid":
        return "550e8400-e29b-41d4-a716-446655440000"
    if field_type == "datetime":
        return "2026-03-04T19:30:00Z"
    if field_type == "integer":
        return "200"
    if field_type == "float":
        return "0.95"
    if field_type == "boolean":
        return "true"
    if field_type == "ip_address":
        return "203.0.113.42"
    return "sample_value"


@router.get("/sources/{source_name}/fields")
async def get_source_fields(source_name: str) -> dict:
    """Return field list with inferred type and sample value."""
    if source_name not in _SCHEMA_MODULES:
        return {"error": f"Unknown source: {source_name}", "source_id": source_name, "fields": []}

    import importlib
    mod_path, class_name = _SCHEMA_MODULES[source_name]
    mod = importlib.import_module(mod_path)
    model_cls = getattr(mod, class_name)

    fields = []
    for fname, finfo in model_cls.model_fields.items():
        annotation = finfo.annotation
        type_str = getattr(annotation, "__name__", str(annotation))
        inferred = _infer_field_type(fname, type_str)
        sample = _get_sample_value(source_name, fname, inferred)
        fields.append({
            "name": fname,
            "type": inferred,
            "sample": sample,
        })

    return {"source_id": source_name, "fields": fields}


def _run_generate_job(job_id: str, sources: list[str], start: date, end: date) -> None:
    """Background task: run generators."""
    from apps.mock_data_gen.run_all import run

    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = time.time()

    try:
        results = run(sources=sources, start_date=start, end_date=end)
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["results"] = results
        total_records = sum(r["records"] for r in results.values())
        _jobs[job_id]["files_generated"] = total_records
    except Exception as exc:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
    finally:
        _jobs[job_id]["elapsed_s"] = round(time.time() - _jobs[job_id].get("started_at", time.time()), 2)


@router.post("/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks) -> dict:
    """Start a generation job in the background."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "sources": req.sources,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "status": "pending",
        "progress_pct": 0,
        "files_generated": 0,
        "elapsed_s": 0,
        "_task": None,
    }

    start = date.fromisoformat(req.start_date)
    end = date.fromisoformat(req.end_date)

    # Run in background thread via BackgroundTasks
    background_tasks.add_task(_run_generate_job, job_id, req.sources, start, end)
    return {"job_id": job_id, "status": "pending"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    """Cancel a running generation job."""
    job = _jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}

    if job["status"] not in ("running", "pending"):
        return {"job_id": job_id, "status": job["status"], "detail": "Job is not running"}

    job["status"] = "cancelled"
    # Cancel the asyncio task if stored
    task = job.get("_task")
    if task is not None and not task.done():
        task.cancel()

    job["elapsed_s"] = round(time.time() - job.get("started_at", time.time()), 2)
    logger.info("job_cancelled", job_id=job_id)
    return {"job_id": job_id, "status": "cancelled"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get job status."""
    job = _jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}

    # Estimate progress
    if job["status"] == "running":
        elapsed = time.time() - job.get("started_at", time.time())
        # Rough estimate: 1 source-day takes ~30s
        total_sources = len(job.get("sources", []))
        estimated_total = total_sources * 30
        job["progress_pct"] = min(95, int(elapsed / max(1, estimated_total) * 100))
    elif job["status"] == "done":
        job["progress_pct"] = 100

    return job


@router.get("/output/summary")
async def output_summary() -> list[dict]:
    """Summary of generated output files."""
    from apps.mock_data_gen.generators.base_generator import OUTPUT_ROOT

    summaries = []
    if not OUTPUT_ROOT.exists():
        return summaries

    for src in SOURCE_INFO:
        src_dir = OUTPUT_ROOT / src["name"]
        if not src_dir.exists():
            continue

        files = list(src_dir.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        total_bytes = sum(f.stat().st_size for f in files if f.is_file())

        summaries.append({
            "source": src["name"],
            "display_name": src["display_name"],
            "file_count": file_count,
            "total_size_mb": round(total_bytes / 1_048_576, 2),
        })

    return summaries


@router.post("/validate")
async def validate() -> dict:
    """Run all correlation validation checks."""
    from apps.mock_data_gen.validate import run_all_checks

    results = run_all_checks()
    passed = sum(1 for r in results if r["status"] == "pass")
    return {
        "total": len(results),
        "passed": passed,
        "checks": results,
    }


# ══════════════════════════════════════════════════════════════════════
# EXPORT SCHEMA — join key catalog, insight rules, CRUD, SQL export
# ══════════════════════════════════════════════════════════════════════

_EXPORT_DB_PATH = "data/sqlite/export_schemas.db"

JOIN_KEY_CATALOG: dict[tuple[str, str], list[JoinKey]] = {
    ("medianova_cdn", "origin_server"): [
        JoinKey(type="exact", left="medianova_cdn.client_ip", right="origin_server.client_ip", note="Same client, different CDN layer"),
        JoinKey(type="window", left="medianova_cdn.timestamp", right="origin_server.timestamp", note="±100ms (cache miss moment)", window_ms=100),
        JoinKey(type="exact", left="medianova_cdn.content_id", right="origin_server.content_id", note="Content-based correlation"),
    ],
    ("player_events", "npaw_analytics"): [
        JoinKey(type="exact", left="player_events.session_id", right="npaw_analytics.session_id", note="1:1 session match"),
    ],
    ("player_events", "crm_subscriber"): [
        JoinKey(type="exact", left="player_events.subscriber_id", right="crm_subscriber.subscriber_id", note="Subscriber profile join"),
    ],
    ("player_events", "widevine_drm"): [
        JoinKey(type="window", left="player_events.timestamp", right="widevine_drm.timestamp", note="±5s (license request moment)", window_ms=5000),
        JoinKey(type="exact", left="player_events.subscriber_id", right="widevine_drm.subscriber_id", note="Subscriber-level DRM trace"),
    ],
    ("player_events", "fairplay_drm"): [
        JoinKey(type="window", left="player_events.timestamp", right="fairplay_drm.timestamp", note="±5s (certificate exchange)", window_ms=5000),
        JoinKey(type="exact", left="player_events.subscriber_id", right="fairplay_drm.subscriber_id", note="Subscriber-level DRM trace"),
    ],
    ("widevine_drm", "fairplay_drm"): [
        JoinKey(type="exact", left="widevine_drm.subscriber_id", right="fairplay_drm.subscriber_id", note="Same subscriber, different DRM"),
        JoinKey(type="exact", left="widevine_drm.content_id", right="fairplay_drm.content_id", note="Content-based error comparison"),
    ],
    ("crm_subscriber", "billing"): [
        JoinKey(type="exact", left="crm_subscriber.subscriber_id", right="billing.subscriber_id", note="Subscription + payment history"),
        JoinKey(type="window", left="crm_subscriber.timestamp", right="billing.timestamp", note="±24h (daily granular)", window_ms=86400000),
    ],
    ("player_events", "api_logs"): [
        JoinKey(type="exact", left="player_events.subscriber_id", right="api_logs.subscriber_id", note="Subscriber-level API trace"),
        JoinKey(type="window", left="player_events.timestamp", right="api_logs.timestamp", note="±2s (auth + manifest request)", window_ms=2000),
    ],
    ("medianova_cdn", "akamai_ds2"): [
        JoinKey(type="exact", left="medianova_cdn.client_ip", right="akamai_ds2.client_ip", note="Same client, multi-CDN bandwidth"),
        JoinKey(type="window", left="medianova_cdn.timestamp", right="akamai_ds2.timestamp", note="±60s (same client, different request)", window_ms=60000),
    ],
}


def _detect_join_keys(source_ids: list[str]) -> list[JoinKey]:
    """Auto-detect join keys from the catalog for given source pairs."""
    keys: list[JoinKey] = []
    seen: set[tuple[str, str]] = set()
    for a, b in combinations(source_ids, 2):
        pair = tuple(sorted([a, b]))
        catalog_keys = JOIN_KEY_CATALOG.get(pair, [])  # type: ignore[arg-type]
        for jk in catalog_keys:
            sig = (jk.left, jk.right)
            if sig not in seen:
                seen.add(sig)
                keys.append(jk)
    return keys


def _generate_insight(join_keys: list[JoinKey], source_ids: list[str]) -> str:
    """Rule-based insight generation (no LLM)."""
    parts: list[str] = []
    all_keys_str = " ".join(jk.left + " " + jk.right for jk in join_keys)

    if "client_ip" in all_keys_str:
        parts.append("client_ip başına toplam bandwidth hesaplanır, overlap window çıkarılır.")
    if "session_id" in all_keys_str:
        parts.append("session_id üzerinden QoE metrikleri karşılaştırılır.")
    if "crm_subscriber" in source_ids and "billing" in source_ids:
        parts.append("Churn risk sinyali: seans azalması + payment_failed + churn_risk > 0.7")
    if "subscriber_id" in all_keys_str:
        parts.append("Abone bazında cross-source analiz mümkündür.")

    if not parts:
        parts.append(f"{len(join_keys)} join key tespit edildi.")

    return " ".join(parts)


def _generate_sql(schema: ExportSchema) -> str:
    """Generate DuckDB SQL from an ExportSchema."""
    lines: list[str] = []
    lines.append(f"-- Schema: {schema.name}")
    lines.append(f"-- Join keys: {len(schema.join_keys)}")
    lines.append("")

    # WITH clauses
    cte_parts: list[str] = []
    source_aliases: dict[str, str] = {}
    for i, src in enumerate(schema.sources):
        alias = src.source_id.replace("-", "_").replace(" ", "_")
        source_aliases[src.source_id] = alias
        fields_str = ", ".join(src.fields) if src.fields else "*"
        cte = f"  {alias} AS (\n    SELECT {fields_str}\n    FROM read_parquet('{src.source_id}/*.parquet')\n  )"
        cte_parts.append(cte)

    lines.append("WITH")
    lines.append(",\n".join(cte_parts))

    # SELECT
    all_fields: list[str] = []
    for src in schema.sources:
        alias = source_aliases[src.source_id]
        for f in src.fields:
            all_fields.append(f"{alias}.{f}")

    lines.append(f"SELECT {', '.join(all_fields) if all_fields else '*'}")

    # FROM + JOINs
    if schema.sources:
        first_alias = source_aliases[schema.sources[0].source_id]
        lines.append(f"FROM {first_alias}")

        for src in schema.sources[1:]:
            alias = source_aliases[src.source_id]
            # Find join keys involving these two sources
            join_conditions: list[str] = []
            for jk in schema.join_keys:
                left_src = jk.left.split(".")[0]
                right_src = jk.right.split(".")[0]
                involved = {left_src, right_src}
                if alias in involved or first_alias in involved:
                    left_col = jk.left.split(".")[-1]
                    right_col = jk.right.split(".")[-1]
                    if jk.type == "exact":
                        join_conditions.append(f"  {jk.left} = {jk.right}")
                    elif jk.type == "window" and jk.window_ms:
                        join_conditions.append(
                            f"  ABS(epoch_ms({jk.left}) - epoch_ms({jk.right})) <= {jk.window_ms}"
                        )

            if join_conditions:
                lines.append(f"JOIN {alias} ON")
                lines.append("\n  AND ".join(join_conditions))
            else:
                lines.append(f"CROSS JOIN {alias}")

    lines.append(";")
    return "\n".join(lines)


async def _get_export_db():
    """Get or create the export schemas SQLite database."""
    import os
    os.makedirs("data/sqlite", exist_ok=True)
    db = await aiosqlite.connect(_EXPORT_DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("""
        CREATE TABLE IF NOT EXISTS export_schemas (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            sources_json TEXT,
            join_keys_json TEXT,
            insight TEXT,
            created_at TEXT
        )
    """)
    await db.commit()
    return db


@router.get("/schemas")
async def list_schemas() -> list[dict]:
    """List all saved export schemas."""
    db = await _get_export_db()
    try:
        cursor = await db.execute("SELECT * FROM export_schemas ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "category": row["category"],
                "sources": json.loads(row["sources_json"]),
                "join_keys": json.loads(row["join_keys_json"]),
                "insight": row["insight"],
                "created_at": row["created_at"],
            })
        return result
    finally:
        await db.close()


@router.post("/schemas")
async def create_schema(req: ExportSchemaCreate) -> dict:
    """Create a new export schema with auto-detected join keys and insight."""
    source_ids = [s.source_id for s in req.sources]
    join_keys = _detect_join_keys(source_ids)
    insight = _generate_insight(join_keys, source_ids)

    schema_id = f"es-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    schema = ExportSchema(
        id=schema_id,
        name=req.name,
        description=req.description,
        category=req.category,
        sources=req.sources,
        join_keys=join_keys,
        insight=insight,
        created_at=now,
    )

    db = await _get_export_db()
    try:
        await db.execute(
            """INSERT INTO export_schemas (id, name, description, category, sources_json, join_keys_json, insight, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                schema.id, schema.name, schema.description, schema.category,
                json.dumps([s.model_dump() for s in schema.sources]),
                json.dumps([jk.model_dump() for jk in schema.join_keys]),
                schema.insight, schema.created_at,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return schema.model_dump()


@router.get("/schemas/{schema_id}")
async def get_schema(schema_id: str) -> dict:
    """Get a single export schema by ID."""
    db = await _get_export_db()
    try:
        cursor = await db.execute("SELECT * FROM export_schemas WHERE id = ?", (schema_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "Schema not found"}
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "category": row["category"],
            "sources": json.loads(row["sources_json"]),
            "join_keys": json.loads(row["join_keys_json"]),
            "insight": row["insight"],
            "created_at": row["created_at"],
        }
    finally:
        await db.close()


@router.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: str) -> dict:
    """Delete an export schema."""
    db = await _get_export_db()
    try:
        await db.execute("DELETE FROM export_schemas WHERE id = ?", (schema_id,))
        await db.commit()
        return {"deleted": schema_id}
    finally:
        await db.close()


@router.get("/schemas/{schema_id}/export/sql")
async def export_sql(schema_id: str) -> dict:
    """Generate DuckDB SQL query for an export schema."""
    db = await _get_export_db()
    try:
        cursor = await db.execute("SELECT * FROM export_schemas WHERE id = ?", (schema_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "Schema not found"}

        schema = ExportSchema(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            category=row["category"] or "",
            sources=[FieldSelection(**s) for s in json.loads(row["sources_json"])],
            join_keys=[JoinKey(**jk) for jk in json.loads(row["join_keys_json"])],
            insight=row["insight"] or "",
            created_at=row["created_at"] or "",
        )
        sql = _generate_sql(schema)
        return {"sql": sql}
    finally:
        await db.close()
