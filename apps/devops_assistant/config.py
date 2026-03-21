"""DevOps Assistant module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DevOpsAssistantConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVOPS_", extra="ignore")

    runbook_search_top_k: int = Field(default=3)
    deployment_history_limit: int = Field(default=20)
    health_check_timeout_ms: int = Field(default=5000)
    dangerous_commands: list[str] = Field(
        default=["rm -rf", "DROP TABLE", "DELETE FROM", "shutdown", "reboot"],
    )
