"""Application settings loaded from .env via Pydantic BaseSettings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = ""

    # Auth
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Database paths
    sqlite_path: str = "./data/sqlite/platform.db"
    duckdb_path: str = "./data/duckdb/analytics.duckdb"
    chromadb_path: str = "./data/chromadb"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = "ssport-datastream"

    # Environment
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "DEBUG"


@lru_cache
def get_settings() -> Settings:
    return Settings()
