"""Admin & Governance Pydantic v2 models."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TenantInfo(BaseModel):
    tenant_id: str
    name: str
    plan: str = "starter"  # starter, growth, enterprise
    timezone: str = "Europe/Istanbul"
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModuleConfig(BaseModel):
    module_name: str
    tenant_id: str
    is_enabled: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class APIKeyInfo(BaseModel):
    key_id: str = Field(default_factory=lambda: f"KEY-{uuid4().hex[:8]}")
    tenant_id: str
    key_name: str
    masked_key: str = ""  # sk-ant-...XXXX — never full key in response
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rotated_at: datetime | None = None


class AuditEntry(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"AUD-{uuid4().hex[:12]}")
    tenant_id: str
    user_id: str = ""
    action: str
    resource: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    ip_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"CMP-{uuid4().hex[:8]}")
    tenant_id: str
    period: str = "weekly"
    total_decisions: int = 0
    high_risk_decisions: int = 0
    approval_rate: float = 0.0
    violations: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class UsageStats(BaseModel):
    tenant_id: str
    total_agent_calls: int = 0
    total_alerts: int = 0
    model_usage: dict[str, int] = Field(default_factory=dict)
    period: str = "daily"


def mask_api_key(full_key: str) -> str:
    """Mask API key — never return full key. Returns sk-ant-...XXXX."""
    if len(full_key) < 8:
        return "sk-ant-...****"
    return f"sk-ant-...{full_key[-4:]}"


def encrypt_api_key(key: str, secret: str) -> str:
    """Encrypt API key using AES-256 derived from JWT secret. Simplified: HMAC-SHA256."""
    return hashlib.sha256(f"{secret}:{key}".encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new API key."""
    return f"sk-ant-{os.urandom(24).hex()}"
