"""Admin & Governance module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminGovernanceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_", extra="ignore")

    api_key_mask_prefix: str = Field(default="sk-ant-...")
    api_key_mask_suffix_len: int = Field(default=4)
    audit_log_retention_days: int = Field(default=365)
    compliance_check_interval_hours: int = Field(default=168)  # weekly
    max_export_rows: int = Field(default=50_000)
    required_role: str = Field(default="admin")
