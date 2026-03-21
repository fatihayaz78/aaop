"""Admin & Governance tools — all require tenant_id. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.admin_governance.config import AdminGovernanceConfig
from apps.admin_governance.schemas import (
    AuditEntry,
    ComplianceReport,
    ModuleConfig,
    TenantInfo,
    UsageStats,
    encrypt_api_key,
    generate_api_key,
    mask_api_key,
)

logger = structlog.get_logger(__name__)


async def _write_audit(
    tenant_id: str, user_id: str, action: str, resource: str,
    detail: dict[str, Any], success: bool, sqlite: Any,
) -> None:
    """Write to audit_log. Every action (success + fail) is recorded."""

    entry = AuditEntry(
        tenant_id=tenant_id, user_id=user_id, action=action,
        resource=resource, detail=detail, success=success,
    )
    sqlite.execute(
        """INSERT INTO audit_log (id, tenant_id, user_id, action, resource, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        [entry.audit_id, tenant_id, user_id, action, resource, str(detail)],
    )
    logger.info("audit_logged", tenant_id=tenant_id, action=action, success=success)


# ── LOW risk tools ──────────────────────────────────────


async def list_tenants(sqlite: Any) -> list[TenantInfo]:
    """List all tenants. Risk: LOW."""
    rows = sqlite.fetch_all("SELECT * FROM tenants WHERE is_active = 1", [])
    return [
        TenantInfo(
            tenant_id=r["id"], name=r["name"], plan=r["plan"],
            timezone=r.get("timezone", "Europe/Istanbul"),
        )
        for r in rows
    ]


async def get_module_configs(tenant_id: str, sqlite: Any) -> list[ModuleConfig]:
    """Get module configurations for tenant. Risk: LOW."""
    rows = sqlite.fetch_all(
        "SELECT * FROM module_configs WHERE tenant_id = ?", [tenant_id],
    )
    return [
        ModuleConfig(
            module_name=r["module_name"], tenant_id=tenant_id,
            is_enabled=bool(r.get("is_enabled", 1)),
        )
        for r in rows
    ]


async def get_audit_log(
    tenant_id: str, sqlite: Any, limit: int = 100,
) -> list[dict[str, Any]]:
    """Get audit log entries. Risk: LOW."""
    return sqlite.fetch_all(
        "SELECT * FROM audit_log WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
        [tenant_id, limit],
    )


async def get_usage_stats(tenant_id: str, db: Any) -> UsageStats:
    """Get usage statistics from DuckDB. Risk: LOW."""
    decisions = db.fetch_all(
        """SELECT llm_model_used, COUNT(*) as count
           FROM shared_analytics.agent_decisions WHERE tenant_id = ?
           GROUP BY llm_model_used""",
        [tenant_id],
    )
    alerts = db.fetch_all(
        "SELECT COUNT(*) as count FROM shared_analytics.alerts_sent WHERE tenant_id = ?",
        [tenant_id],
    )
    model_usage = {r["llm_model_used"]: r["count"] for r in decisions}
    total = sum(model_usage.values())
    return UsageStats(
        tenant_id=tenant_id,
        total_agent_calls=total,
        total_alerts=alerts[0]["count"] if alerts else 0,
        model_usage=model_usage,
    )


async def generate_compliance_report(
    tenant_id: str, db: Any,
) -> ComplianceReport:
    """Generate compliance report from agent_decisions. Risk: LOW."""
    total_rows = db.fetch_all(
        "SELECT COUNT(*) as count FROM shared_analytics.agent_decisions WHERE tenant_id = ?",
        [tenant_id],
    )
    high_risk_rows = db.fetch_all(
        """SELECT COUNT(*) as count FROM shared_analytics.agent_decisions
           WHERE tenant_id = ? AND risk_level = 'HIGH'""",
        [tenant_id],
    )
    total = total_rows[0]["count"] if total_rows else 0
    high_risk = high_risk_rows[0]["count"] if high_risk_rows else 0
    approval_rate = ((total - high_risk) / total * 100) if total > 0 else 100.0

    violations: list[dict[str, Any]] = []
    if high_risk > 0:
        unapproved = db.fetch_all(
            """SELECT COUNT(*) as count FROM shared_analytics.agent_decisions
               WHERE tenant_id = ? AND risk_level = 'HIGH' AND approval_required = FALSE""",
            [tenant_id],
        )
        if unapproved and unapproved[0]["count"] > 0:
            violations.append({
                "type": "unapproved_high_risk",
                "count": unapproved[0]["count"],
                "description": "HIGH risk actions executed without approval",
            })

    return ComplianceReport(
        tenant_id=tenant_id,
        total_decisions=total,
        high_risk_decisions=high_risk,
        approval_rate=round(approval_rate, 1),
        violations=violations,
    )


# ── MEDIUM risk tools ───────────────────────────────────


async def create_tenant(
    tenant_id: str, name: str, plan: str, sqlite: Any, user_id: str = "",
) -> TenantInfo:
    """Create a new tenant. Risk: MEDIUM (auto+notify)."""
    sqlite.execute(
        "INSERT INTO tenants (id, name, plan) VALUES (?, ?, ?)",
        [tenant_id, name, plan],
    )
    await _write_audit(tenant_id, user_id, "create_tenant", "tenants", {"name": name, "plan": plan}, True, sqlite)
    logger.info("tenant_created", tenant_id=tenant_id, plan=plan)
    return TenantInfo(tenant_id=tenant_id, name=name, plan=plan)


async def update_module_config(
    tenant_id: str, module_name: str, is_enabled: bool, sqlite: Any, user_id: str = "",
) -> ModuleConfig:
    """Update module config. Risk: MEDIUM (auto+notify)."""
    sqlite.execute(
        """INSERT OR REPLACE INTO module_configs (id, tenant_id, module_name, is_enabled, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        [f"{tenant_id}:{module_name}", tenant_id, module_name, int(is_enabled)],
    )
    await _write_audit(
        tenant_id, user_id, "update_module_config", "module_configs",
        {"module_name": module_name, "is_enabled": is_enabled}, True, sqlite,
    )
    return ModuleConfig(module_name=module_name, tenant_id=tenant_id, is_enabled=is_enabled)


# ── HIGH risk tools ─────────────────────────────────────


async def rotate_api_key(
    tenant_id: str, key_name: str, jwt_secret: str, sqlite: Any, user_id: str = "",
) -> dict:
    """Rotate API key. Risk: HIGH (approval_required). Returns masked key only."""
    new_key = generate_api_key()
    encrypted = encrypt_api_key(new_key, jwt_secret)
    masked = mask_api_key(new_key)

    await _write_audit(
        tenant_id, user_id, "rotate_api_key", "api_keys",
        {"key_name": key_name, "masked": masked}, True, sqlite,
    )

    logger.warning("api_key_rotated", tenant_id=tenant_id, key_name=key_name, masked=masked)
    return {
        "status": "approval_required",
        "key_name": key_name,
        "masked_key": masked,
        "encrypted_hash": encrypted,
    }


async def delete_tenant(
    tenant_id: str, sqlite: Any, user_id: str = "",
) -> dict:
    """Delete tenant. Risk: HIGH (approval_required)."""
    await _write_audit(
        tenant_id, user_id, "delete_tenant", "tenants",
        {"tenant_id": tenant_id}, True, sqlite,
    )
    logger.warning("tenant_delete_requested", tenant_id=tenant_id)
    return {
        "status": "approval_required",
        "tenant_id": tenant_id,
    }


async def export_audit_log(
    tenant_id: str, sqlite: Any, user_id: str = "",
) -> dict:
    """Export audit log. Risk: HIGH (approval_required)."""
    config = AdminGovernanceConfig()
    await _write_audit(
        tenant_id, user_id, "export_audit_log", "audit_log",
        {"max_rows": config.max_export_rows}, True, sqlite,
    )
    logger.warning("audit_log_export_requested", tenant_id=tenant_id)
    return {
        "status": "approval_required",
        "tenant_id": tenant_id,
        "max_rows": config.max_export_rows,
    }
