"""AI Lab module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AILabConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_LAB_", extra="ignore")

    token_budget_warn_pct: float = Field(default=80.0)
    token_budget_monthly: int = Field(default=10_000_000)
    experiment_max_variants: int = Field(default=5)
    significance_threshold: float = Field(default=0.05)
    prompt_version_retention: int = Field(default=10)
