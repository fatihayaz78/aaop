"""Knowledge Base module configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeBaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KB_", extra="ignore")

    chunk_size_tokens: int = Field(default=500)
    chunk_overlap_tokens: int = Field(default=50)
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    collections: list[str] = Field(default=["incidents", "runbooks", "platform"])
    search_top_k: int = Field(default=5)
    min_relevance_score: float = Field(default=0.3)
