"""APScheduler-based scheduler for periodic S3 log fetching."""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.log_analyzer.config import LogAnalyzerConfig

logger = structlog.get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _fetch_job(tenant_id: str, project_id: str, sub_module: str) -> None:
    """Scheduled job: fetch logs from S3, analyze, and write to DuckDB."""
    logger.info("scheduler_fetch_start", tenant_id=tenant_id, project_id=project_id, sub_module=sub_module)
    # Full implementation will use SubModuleRegistry to run the pipeline
    # This is wired up when the agent registers scheduled jobs


def start_scheduler(config: LogAnalyzerConfig) -> AsyncIOScheduler:
    """Start the APScheduler for periodic log fetching."""
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    logger.info("log_analyzer_scheduler_started", cron_hour=config.schedule_cron_hour)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("log_analyzer_scheduler_stopped")
    _scheduler = None


def add_fetch_job(
    tenant_id: str,
    project_id: str,
    sub_module: str,
    cron_hour: str = "*/6",
) -> str:
    """Add a recurring fetch job. Returns the job ID."""
    if _scheduler is None:
        msg = "Scheduler not started"
        raise RuntimeError(msg)
    job = _scheduler.add_job(
        _fetch_job,
        "cron",
        hour=cron_hour,
        kwargs={"tenant_id": tenant_id, "project_id": project_id, "sub_module": sub_module},
        id=f"fetch_{tenant_id}_{project_id}",
        replace_existing=True,
    )
    logger.info("scheduler_job_added", job_id=job.id, tenant_id=tenant_id)
    return job.id
