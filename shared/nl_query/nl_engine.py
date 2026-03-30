"""NL Engine — Natural Language to SQL query engine."""

from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

from shared.nl_query.schema_registry import get_schema_context
from shared.nl_query.sql_validator import SQLValidator, ValidationResult
from shared.utils.pii_scrubber import scrub

logger = structlog.get_logger(__name__)

NL_SYSTEM_PROMPT = """You are a SQL query generator for an OTT streaming analytics platform.
You receive a natural language question and generate a DuckDB-compatible SELECT query.

RULES:
- ONLY generate SELECT statements — no INSERT/UPDATE/DELETE/DROP
- ALWAYS include WHERE tenant_id = '{tenant_id}'
- ALWAYS end with LIMIT {max_rows}
- NEVER select PII columns: client_ip, subscriber_id, user_agent
- Use DuckDB syntax: INTERVAL, DATE_TRUNC, PERCENTILE_CONT
- Return ONLY the SQL query, no explanation

{schema_context}
"""


class NLQueryResult(BaseModel):
    natural_language: str
    generated_sql: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_ms: float = 0.0
    columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


EXAMPLE_QUERIES = [
    "Son 7 günün P0 incident'ları",
    "Dün en yüksek QoE skoru hangi cihazda?",
    "Bu ay CDN error rate ortalaması",
    "API P99 latency trendi (günlük)",
    "Churn riski > 0.7 olan abone sayısı",
    "En çok hata veren 10 API endpoint'i",
    "Son 24 saatteki live event'ler",
    "Medianova cache hit oranı (son 7 gün)",
]


class NLEngine:
    """Production-grade NL→SQL engine with PII protection and validation."""

    def __init__(self) -> None:
        self._validator = SQLValidator()

    async def query(
        self,
        natural_language: str,
        tenant_id: str,
        schema: str = "aaop_company",
        max_rows: int = 100,
    ) -> NLQueryResult:
        # 1. PII scrub the natural language input
        scrubbed_nl = scrub(natural_language)

        # 2. Build LLM prompt with schema context
        schema_context = get_schema_context(schema)
        system = NL_SYSTEM_PROMPT.format(
            tenant_id=tenant_id, max_rows=min(max_rows, 1000), schema_context=schema_context,
        )
        prompt = f"Question: {scrubbed_nl}\nGenerate SQL:"

        # 3. Call LLM (Sonnet)
        try:
            from shared.llm_gateway import LLMGateway
            llm = LLMGateway()
            response = await llm.invoke(prompt=prompt, model="claude-sonnet-4-20250514", system_prompt=system)
            generated_sql = response.get("content", "").strip()
            # Clean markdown code fences if present
            if generated_sql.startswith("```"):
                lines = generated_sql.split("\n")
                generated_sql = "\n".join(l for l in lines if not l.startswith("```")).strip()
        except Exception as exc:
            logger.error("nl_llm_error", error=str(exc))
            return NLQueryResult(
                natural_language=natural_language,
                generated_sql="",
                error=f"LLM error: {exc}",
            )

        # 4. Validate SQL
        validation = self._validator.validate(generated_sql, tenant_id, schema)
        if not validation.valid:
            return NLQueryResult(
                natural_language=natural_language,
                generated_sql=generated_sql,
                error=validation.reason,
                warnings=validation.warnings,
            )

        # 5. Execute query
        try:
            start = time.monotonic()
            rows, columns = await self._execute(generated_sql, schema)
            execution_ms = round((time.monotonic() - start) * 1000, 1)

            logger.info("nl_query_executed", tenant_id=tenant_id, rows=len(rows), ms=execution_ms)

            return NLQueryResult(
                natural_language=natural_language,
                generated_sql=generated_sql,
                rows=rows[:max_rows],
                row_count=len(rows),
                execution_ms=execution_ms,
                columns=columns,
                warnings=validation.warnings,
            )
        except Exception as exc:
            logger.error("nl_query_exec_error", error=str(exc), sql=generated_sql[:200])
            return NLQueryResult(
                natural_language=natural_language,
                generated_sql=generated_sql,
                error=f"Execution error: {exc}",
            )

    async def _execute(self, sql: str, schema: str) -> tuple[list[dict], list[str]]:
        """Execute SQL on appropriate database."""
        sql_lower = sql.lower()

        # Determine which database to use
        if "shared_analytics." in sql_lower:
            from backend.dependencies import _duckdb
            if _duckdb:
                rows = _duckdb.fetch_all(sql, [])
                columns = list(rows[0].keys()) if rows else []
                return rows, columns

        # logs.duckdb
        from shared.ingest.log_queries import _get_logs_db
        db = _get_logs_db()
        conn = db.get_connection()
        rel = conn.execute(sql)
        columns = [d[0] for d in rel.description]
        raw_rows = rel.fetchall()
        rows = [dict(zip(columns, row)) for row in raw_rows]
        return rows, columns
