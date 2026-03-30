"""DevOps Assistant tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.devops_assistant.config import DevOpsAssistantConfig
from apps.devops_assistant.schemas import CommandSuggestion, Deployment, RunbookExecution, ServiceHealth

logger = structlog.get_logger(__name__)


# ── LOW risk tools ──────────────────────────────────────


async def check_service_health(tenant_id: str, service: str) -> ServiceHealth:
    """Check health of a service from logs.duckdb. Risk: LOW."""
    try:
        from shared.ingest.log_queries import get_api_health, get_infrastructure_health
        api = get_api_health(tenant_id, hours=1)
        infra = get_infrastructure_health(tenant_id, hours=1)

        error_rate = api.get("error_rate_pct", 0) / 100.0  # pct → ratio
        p99 = api.get("p99_response_time_ms", 0)

        # Check infra for specific service
        for svc in infra.get("services", []):
            if service.lower() in svc.get("service_name", "").lower():
                error_rate = max(error_rate, svc.get("error_rate", 0))
                p99 = max(p99, svc.get("memory_mb", 0))  # response_time stored as memory_mb in query

        status = "healthy"
        if error_rate > 0.15:
            status = "down"
        elif error_rate > 0.05:
            status = "degraded"

        logger.info("service_health_check", tenant_id=tenant_id, service=service,
                     status=status, error_rate=error_rate)
        return ServiceHealth(
            service=service, status=status, latency_ms=int(p99),
            details={"error_rate": round(error_rate, 4), "p99_ms": round(p99, 1)},
        )
    except Exception as exc:
        logger.debug("health_check_fallback", service=service, error=str(exc))
        return ServiceHealth(service=service, status="unknown", latency_ms=0)


async def get_deployment_history(tenant_id: str, db: Any) -> list[dict]:
    """Get deployment history from shared_analytics. Risk: LOW."""
    config = DevOpsAssistantConfig()
    return db.fetch_all(
        """SELECT app, action, risk_level, llm_model_used, created_at
           FROM shared_analytics.agent_decisions
           WHERE tenant_id = ? AND action LIKE '%deploy%'
           ORDER BY created_at DESC LIMIT ?""",
        [tenant_id, config.deployment_history_limit],
    )


async def search_runbooks(tenant_id: str, query: str, chroma: Any) -> list[dict]:
    """Search runbooks from Knowledge Base ChromaDB. Risk: LOW."""
    config = DevOpsAssistantConfig()
    results = chroma.query(
        collection_name="runbooks",
        query_text=query,
        n_results=config.runbook_search_top_k,
        where={"tenant_id": tenant_id},
    )
    if not results or not results.get("documents"):
        return []

    docs = results["documents"][0] if results["documents"] else []
    ids = results["ids"][0] if results.get("ids") else []
    metadatas = results["metadatas"][0] if results.get("metadatas") else []

    return [
        {"id": ids[i] if i < len(ids) else "", "content": doc,
         "metadata": metadatas[i] if i < len(metadatas) else {}}
        for i, doc in enumerate(docs)
    ]


async def get_platform_metrics(tenant_id: str, db: Any) -> dict[str, Any]:
    """Get platform metrics from DuckDB. Risk: LOW."""
    incidents = db.fetch_all(
        """SELECT COUNT(*) as count FROM shared_analytics.incidents
           WHERE tenant_id = ? AND status = 'open'""",
        [tenant_id],
    )
    decisions = db.fetch_all(
        """SELECT COUNT(*) as count FROM shared_analytics.agent_decisions
           WHERE tenant_id = ?""",
        [tenant_id],
    )
    return {
        "open_incidents": incidents[0]["count"] if incidents else 0,
        "total_decisions": decisions[0]["count"] if decisions else 0,
    }


async def suggest_command(
    tenant_id: str, intent: str, context: str = "",
) -> CommandSuggestion:
    """Suggest a safe command. Risk: LOW."""
    config = DevOpsAssistantConfig()

    # Check if intent contains dangerous patterns
    is_dangerous = any(d in intent.lower() for d in [c.lower() for c in config.dangerous_commands])

    if is_dangerous:
        return CommandSuggestion(
            command=intent,
            description="This command is flagged as potentially dangerous",
            is_dangerous=True,
            risk_level="HIGH",
        )

    return CommandSuggestion(
        command=intent,
        description=f"Suggested for: {context}" if context else "Safe to execute",
        is_dangerous=False,
        risk_level="LOW",
    )


# ── MEDIUM risk tools ───────────────────────────────────


async def create_deployment_record(
    tenant_id: str, deployment: Deployment, db: Any,
) -> str:
    """Create deployment record. Risk: MEDIUM (auto+notify)."""
    from uuid import uuid4

    decision_id = f"DEC-{uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO shared_analytics.agent_decisions
        (decision_id, tenant_id, app, action, risk_level, approval_required,
         llm_model_used, reasoning_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            decision_id, tenant_id, "devops_assistant", "create_deployment",
            "MEDIUM", False, "claude-sonnet-4-20250514",
            f"Deploy {deployment.service} v{deployment.version}",
        ],
    )
    logger.info("deployment_recorded", tenant_id=tenant_id, deployment_id=deployment.deployment_id)
    return deployment.deployment_id


# ── HIGH risk tools ─────────────────────────────────────


async def execute_runbook(
    tenant_id: str, runbook: RunbookExecution,
) -> dict:
    """Execute a runbook. Risk: HIGH (approval_required)."""
    logger.warning(
        "runbook_execution_requested",
        tenant_id=tenant_id, runbook_id=runbook.runbook_id,
    )
    return {
        "status": "approval_required",
        "execution_id": runbook.execution_id,
        "runbook_id": runbook.runbook_id,
    }


async def restart_service(
    tenant_id: str, service: str, reason: str = "",
) -> dict:
    """Restart a service. Risk: HIGH (approval_required)."""
    logger.warning(
        "service_restart_requested",
        tenant_id=tenant_id, service=service, reason=reason,
    )
    return {
        "status": "approval_required",
        "service": service,
        "reason": reason,
    }
