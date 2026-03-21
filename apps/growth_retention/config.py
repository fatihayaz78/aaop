"""Growth & Retention module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GrowthRetentionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GROWTH_", extra="ignore")

    churn_risk_threshold: float = Field(default=0.7)
    retention_analysis_interval_hours: int = Field(default=24)
    max_sql_results: int = Field(default=1000)
    allowed_schemas: list[str] = Field(default=["shared_analytics"])
    allowed_tables: list[str] = Field(
        default=[
            "qoe_metrics",
            "cdn_analysis",
            "live_events",
            "agent_decisions",
            "retention_scores",
        ],
    )
    campaign_cooldown_hours: int = Field(default=48)
    segment_min_size: int = Field(default=10)
