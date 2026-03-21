"""Capacity & Cost module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CapacityCostConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAPACITY_", extra="ignore")

    warn_threshold_pct: float = Field(default=70.0)
    crit_threshold_pct: float = Field(default=90.0)
    forecast_horizon_hours: int = Field(default=24)
    usage_check_interval_minutes: int = Field(default=60)
    pre_scale_lead_minutes: int = Field(default=30)
    cost_currency: str = Field(default="USD")
    max_scale_factor: float = Field(default=5.0)
