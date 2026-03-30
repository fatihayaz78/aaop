"""SQL Validator — security checks for NL-generated SQL."""

from __future__ import annotations

import re

import structlog

from shared.nl_query.schema_registry import QUERYABLE_TABLES, get_all_pii_columns

logger = structlog.get_logger(__name__)


class ValidationResult:
    def __init__(self, valid: bool, reason: str = "OK", warnings: list[str] | None = None):
        self.valid = valid
        self.reason = reason
        self.warnings = warnings or []


class SQLValidator:
    """Validates generated SQL for safety before execution."""

    def validate(self, sql: str, tenant_id: str, schema: str) -> ValidationResult:
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()
        warnings: list[str] = []

        # 1. Must be SELECT
        if not sql_upper.startswith("SELECT"):
            return ValidationResult(False, "Only SELECT statements allowed")

        # 2. No write statements
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]
        for kw in forbidden:
            if re.search(rf"\b{kw}\b", sql_upper):
                return ValidationResult(False, f"Write operation '{kw}' not allowed")

        # 3. Must have tenant_id filter
        if "tenant_id" not in sql.lower():
            return ValidationResult(False, "Query must include tenant_id filter")

        # 4. No PII columns in SELECT or WHERE
        pii = get_all_pii_columns()
        for col in pii:
            if re.search(rf"\b{col}\b", sql, re.IGNORECASE):
                return ValidationResult(False, f"PII column '{col}' cannot be queried")

        # 5. Must have LIMIT
        if "LIMIT" not in sql_upper:
            return ValidationResult(False, "Query must include LIMIT clause")

        # 6. Check LIMIT value
        limit_match = re.search(r"LIMIT\s+(\d+)", sql_upper)
        if limit_match and int(limit_match.group(1)) > 1000:
            warnings.append("LIMIT exceeds 1000 — capped to 1000")

        # 7. Only allowed tables
        found_table = False
        resolved_tables = {k.replace("{schema}", schema) for k in QUERYABLE_TABLES}
        for table in resolved_tables:
            if table.lower() in sql.lower() or table.split(".")[-1].lower() in sql.lower():
                found_table = True
                break
        if not found_table:
            return ValidationResult(False, "Query references unknown tables")

        logger.info("sql_validated", valid=True, warnings=warnings)
        return ValidationResult(True, "OK", warnings)
