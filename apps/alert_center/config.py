"""Alert Center module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlertCenterConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALERT_CENTER_", extra="ignore")

    dedup_window_seconds: int = Field(default=900)
    storm_threshold_count: int = Field(default=10)
    storm_window_seconds: int = Field(default=300)
    default_slack_channel: str = Field(default="#ops-alerts")
    default_email_to: str = Field(default="ops@example.com")
