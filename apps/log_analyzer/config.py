"""Log Analyzer module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogAnalyzerConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOG_ANALYZER_", extra="ignore")

    s3_bucket: str = Field(default="ssport-datastream")
    s3_prefix: str = Field(default="logs/")
    s3_region: str = Field(default="eu-west-1")
    schedule_cron_hour: str = Field(default="*/6")
    anomaly_error_rate_threshold: float = Field(default=0.05)
    anomaly_cache_hit_threshold: float = Field(default=0.60)
    anomaly_ttfb_p99_threshold_ms: float = Field(default=3000.0)
    docx_reports_dir: str = Field(default="data/reports")
    logs_cache_dir: str = Field(default="data/logs")
