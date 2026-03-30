"""Tests for NL query engine — validator, schema registry, engine."""

from __future__ import annotations

import pytest

from shared.nl_query.nl_engine import NLEngine, NLQueryResult, EXAMPLE_QUERIES
from shared.nl_query.schema_registry import get_schema_context, get_table_list, get_all_pii_columns
from shared.nl_query.sql_validator import SQLValidator, ValidationResult


# ── Schema Registry ─────────────────────────────────────────

def test_schema_context_contains_tables():
    ctx = get_schema_context("aaop_company")
    assert "medianova_logs" in ctx
    assert "incidents" in ctx
    assert "client_ip" not in ctx  # PII filtered


def test_table_list():
    tables = get_table_list("sport_stream")
    assert len(tables) >= 10
    for t in tables:
        assert "table" in t
        assert "columns" in t
        assert "client_ip" not in t["columns"]  # PII filtered


def test_pii_columns():
    pii = get_all_pii_columns()
    assert "client_ip" in pii
    assert "subscriber_id" in pii


# ── SQL Validator ────────────────────────────────────────────

@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator()


def test_valid_select(validator: SQLValidator):
    sql = "SELECT severity, COUNT(*) FROM shared_analytics.incidents WHERE tenant_id = 'ott_co' GROUP BY severity LIMIT 10"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is True


def test_reject_insert(validator: SQLValidator):
    sql = "INSERT INTO shared_analytics.incidents VALUES ('x')"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is False
    assert "SELECT" in r.reason or "INSERT" in r.reason


def test_reject_drop(validator: SQLValidator):
    sql = "DROP TABLE shared_analytics.incidents"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is False


def test_reject_no_tenant(validator: SQLValidator):
    sql = "SELECT * FROM shared_analytics.incidents LIMIT 10"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is False
    assert "tenant_id" in r.reason


def test_reject_pii_column(validator: SQLValidator):
    sql = "SELECT client_ip FROM sport_stream.medianova_logs WHERE tenant_id = 'ott_co' LIMIT 10"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is False
    assert "PII" in r.reason


def test_reject_no_limit(validator: SQLValidator):
    sql = "SELECT * FROM shared_analytics.incidents WHERE tenant_id = 'ott_co'"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is False
    assert "LIMIT" in r.reason


def test_logs_table_valid(validator: SQLValidator):
    sql = "SELECT status_code, COUNT(*) FROM sport_stream.medianova_logs WHERE tenant_id = 'ott_co' GROUP BY status_code LIMIT 20"
    r = validator.validate(sql, "ott_co", "sport_stream")
    assert r.valid is True


# ── NL Engine ────────────────────────────────────────────────

def test_example_queries_exist():
    assert len(EXAMPLE_QUERIES) >= 5


def test_nl_query_result_model():
    r = NLQueryResult(
        natural_language="test question",
        generated_sql="SELECT 1",
        rows=[{"col": 1}],
        row_count=1,
        execution_ms=5.0,
        columns=["col"],
    )
    assert r.error is None
    assert r.row_count == 1
