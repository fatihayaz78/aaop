"""Ops Center module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpsCenterConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPS_CENTER_", extra="ignore")

    p1_mttr_target_seconds: int = Field(default=300)
    auto_rca_severities: list[str] = Field(default=["P0", "P1"])
    fp_rate_window_days: int = Field(default=7)
    fp_rate_threshold: float = Field(default=0.15)
    slack_webhook_url: str = Field(default="")
    pagerduty_routing_key: str = Field(default="")
