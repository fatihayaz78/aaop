"""Export Schema models — cross-source join definitions for DuckDB export."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FieldSelection(BaseModel):
    source_id: str
    fields: list[str]


class JoinKey(BaseModel):
    type: Literal["exact", "window", "filter"]
    left: str
    right: str
    note: str
    window_ms: int | None = None


class ExportSchema(BaseModel):
    id: str
    name: str
    description: str
    category: str
    sources: list[FieldSelection]
    join_keys: list[JoinKey]
    insight: str
    created_at: str


class ExportSchemaCreate(BaseModel):
    name: str
    description: str
    category: str
    sources: list[FieldSelection]
