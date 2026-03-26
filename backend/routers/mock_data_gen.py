"""Mock Data Generator API — source listing, schema browser, generate jobs, validation."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import date
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

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
    }

    start = date.fromisoformat(req.start_date)
    end = date.fromisoformat(req.end_date)

    background_tasks.add_task(_run_generate_job, job_id, req.sources, start, end)
    return {"job_id": job_id, "status": "pending"}


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
