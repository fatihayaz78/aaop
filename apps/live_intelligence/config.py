"""Live Intelligence module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LiveIntelligenceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIVE_INTEL_", extra="ignore")

    pre_event_trigger_minutes: int = Field(default=30)
    sportradar_poll_seconds: int = Field(default=30)
    drm_poll_seconds: int = Field(default=60)
    epg_poll_seconds: int = Field(default=300)
    active_event_ttl: int = Field(default=60)
    pre_scale_status_ttl: int = Field(default=3600)
    drm_status_ttl: int = Field(default=60)
    sportradar_ttl: int = Field(default=30)
