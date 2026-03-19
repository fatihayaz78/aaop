"""Viewer Experience module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ViewerExperienceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIEWER_EXP_", extra="ignore")

    qoe_degradation_threshold: float = Field(default=2.5)
    session_dedup_window_seconds: int = Field(default=300)
    chroma_collection: str = Field(default="complaints")
    similar_complaint_top_k: int = Field(default=5)
