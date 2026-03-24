"""Tests for log structure analysis — type inference, mappings, error handling."""

from __future__ import annotations

import gzip
import io

import pytest

from backend.routers.log_analyzer import (
    VALID_CATEGORIES,
    _analyze_fields,
    _build_s3_prefixes,
    _infer_type,
    _read_s3_content,
)


# ── Type inference tests ──


def test_infer_type_integer():
    assert _infer_type([200, 301, 404, 500]) == "integer"


def test_infer_type_float():
    assert _infer_type([1.5, 2.3, 0.001]) == "float"


def test_infer_type_mixed_numeric_is_float():
    assert _infer_type([1, 2.5, 3]) == "float"


def test_infer_type_string():
    assert _infer_type(["text/html", "application/json"]) == "string"


def test_infer_type_timestamp():
    assert _infer_type([1711000000.123, 1711003600.456, 1711007200.789]) == "timestamp"


def test_infer_type_ip_hash():
    # SHA256 truncated to 16 hex chars
    assert _infer_type(["a1b2c3d4e5f6a7b8", "1234567890abcdef", "fedcba9876543210"]) == "ip_hash"


def test_infer_type_boolean_from_int():
    assert _infer_type([0, 1, 0, 1, 0, 1, 1]) == "boolean"


def test_infer_type_empty():
    assert _infer_type([]) == "string"


# ── Full field analysis from AkamaiLogEntry dicts ──


def test_infer_field_types_from_entry():
    """Simulate a parsed AkamaiLogEntry dict and verify inferred types."""
    entries = [
        {
            "version": 2,
            "cp_code": "12345",
            "req_time_sec": 1711000000.123,
            "bytes": 50000,
            "client_ip": "a1b2c3d4e5f6a7b8",
            "status_code": 200,
            "cache_hit": 1,
            "country": "TR",
            "city": "Istanbul",
            "content_type": "video/mp4",
        },
        {
            "version": 2,
            "cp_code": "12345",
            "req_time_sec": 1711003600.456,
            "bytes": 60000,
            "client_ip": "1234567890abcdef",
            "status_code": 404,
            "cache_hit": 0,
            "country": "DE",
            "city": "Berlin",
            "content_type": "text/html",
        },
        {
            "version": 2,
            "cp_code": "12345",
            "req_time_sec": 1711007200.789,
            "bytes": 70000,
            "client_ip": "fedcba9876543210",
            "status_code": 301,
            "cache_hit": 1,
            "country": "US",
            "city": None,
            "content_type": "application/json",
        },
    ]

    fields = _analyze_fields(entries)
    field_map = {f["field_name"]: f for f in fields}

    assert field_map["version"]["inferred_type"] == "integer"
    assert field_map["cp_code"]["inferred_type"] == "string"
    assert field_map["req_time_sec"]["inferred_type"] == "timestamp"
    assert field_map["bytes"]["inferred_type"] == "integer"
    assert field_map["client_ip"]["inferred_type"] == "ip_hash"
    assert field_map["status_code"]["inferred_type"] == "integer"
    assert field_map["country"]["inferred_type"] == "string"
    assert field_map["content_type"]["inferred_type"] == "string"

    # Null count check
    assert field_map["city"]["null_count"] == 1
    assert field_map["version"]["null_count"] == 0

    # Unique count
    assert field_map["country"]["unique_count"] == 3
    assert field_map["version"]["unique_count"] == 1

    # Sample values: max 3
    assert len(field_map["status_code"]["sample_values"]) == 3


def test_analyze_fields_empty():
    assert _analyze_fields([]) == []


# ── Category mapping validation ──


def test_valid_categories_set():
    expected = {"meta", "timing", "traffic", "content", "client", "network", "response", "cache", "geo", "custom"}
    assert VALID_CATEGORIES == expected


# ── Mapping upsert (unit test with mock DB) ──


@pytest.mark.asyncio
async def test_field_category_mapping_upsert():
    """Verify mapping upsert logic: save, then overwrite with new category."""
    import aiosqlite

    db_path = ":memory:"
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("""
            CREATE TABLE field_category_mappings (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(tenant_id, field_name)
            )
        """)

        tenant = "test_tenant"

        # Insert initial mapping
        mapping_id = f"{tenant}_status_code"
        await conn.execute(
            """INSERT INTO field_category_mappings (id, tenant_id, field_name, category)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET category = excluded.category""",
            (mapping_id, tenant, "status_code", "response"),
        )
        await conn.commit()

        # Verify first insert
        cursor = await conn.execute(
            "SELECT category FROM field_category_mappings WHERE id = ?", (mapping_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == "response"

        # Overwrite with new category
        await conn.execute(
            """INSERT INTO field_category_mappings (id, tenant_id, field_name, category)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET category = excluded.category""",
            (mapping_id, tenant, "status_code", "custom"),
        )
        await conn.commit()

        # Verify upsert
        cursor = await conn.execute(
            "SELECT category FROM field_category_mappings WHERE id = ?", (mapping_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == "custom"

        # Verify only 1 row exists
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM field_category_mappings WHERE tenant_id = ?", (tenant,),
        )
        count = await cursor.fetchone()
        assert count[0] == 1


# ── Structure analysis error handling ──


@pytest.mark.asyncio
async def test_structure_analyze_no_credentials():
    """Mock scenario: no settings row → returns clear error message."""
    from unittest.mock import AsyncMock

    from backend.routers.log_analyzer import structure_analyze, StructureAnalyzeRequest
    from shared.schemas.base_event import TenantContext

    mock_db = AsyncMock()
    mock_db.fetch_one = AsyncMock(return_value=None)

    ctx = TenantContext(tenant_id="test_tenant")
    payload = StructureAnalyzeRequest(start_date="2026-03-01", end_date="2026-03-02")

    result = await structure_analyze(payload=payload, ctx=ctx, db=mock_db)

    assert result["error"] is not None
    assert "credentials" in result["error"].lower() or "configured" in result["error"].lower()
    assert result["fields"] == []
    assert result["total_rows_sampled"] == 0
    assert result["files_scanned"] == 0


# ── S3 path generation ──


def test_s3_path_generation():
    """Verify correct S3 path format: logs/{cp_code}/{year}/{DD}/{MM}/{HH}/
    With UTC+3 → UTC conversion for Turkish local time."""
    prefixes = _build_s3_prefixes("60890", "2026-03-23", "2026-03-23")

    # Turkish 2026-03-23 00:00 = UTC 2026-03-22 21:00
    # Turkish 2026-03-23 23:59 = UTC 2026-03-23 20:59
    # So we expect hours from 2026-03-22 21:00 UTC through 2026-03-23 20:00 UTC

    # Check path format: logs/{cp_code}/{year}/{DD}/{MM}/{HH}/
    assert "logs/60890/2026/22/03/21/" in prefixes  # first UTC hour
    assert "logs/60890/2026/23/03/00/" in prefixes  # midnight UTC
    assert "logs/60890/2026/23/03/20/" in prefixes  # last UTC hour

    # All 24 hours should be present
    assert len(prefixes) == 24

    # Verify DD/MM order (day before month)
    for p in prefixes:
        parts = p.split("/")
        assert parts[0] == "logs"
        assert parts[1] == "60890"
        assert parts[2] == "2026"
        # parts[3] = DD, parts[4] = MM, parts[5] = HH
        dd = int(parts[3])
        mm = int(parts[4])
        hh = int(parts[5])
        assert 1 <= dd <= 31
        assert mm == 3
        assert 0 <= hh <= 23


def test_s3_path_multi_day():
    """Multi-day range generates correct number of hourly prefixes."""
    prefixes = _build_s3_prefixes("60890", "2026-03-23", "2026-03-24")
    # 2 days * 24 hours = 48 hourly prefixes
    assert len(prefixes) == 48


# ── GZ file handling ──


def test_gz_file_parsing():
    """Verify that .gz compressed content is read correctly."""
    original = "version\tcp_code\treq_time_sec\n2\t60890\t1711000000.0"

    # Compress the content
    buf = io.BytesIO()
    with gzip.open(buf, "wt", encoding="utf-8") as f:
        f.write(original)
    buf.seek(0)

    # Read using the helper
    content = _read_s3_content(buf, "logs/60890/2026/23/03/00/data.gz")
    assert content == original
    assert "60890" in content


def test_plain_file_parsing():
    """Verify that non-gz files are read as plain text."""
    original = "version\tcp_code\treq_time_sec\n2\t60890\t1711000000.0"
    buf = io.BytesIO(original.encode("utf-8"))

    content = _read_s3_content(buf, "logs/60890/2026/23/03/00/data.tsv")
    assert content == original


@pytest.mark.asyncio
async def test_structure_analyze_no_cp_code():
    """Mock scenario: settings exist but no cp_code → returns clear error."""
    from unittest.mock import AsyncMock

    from backend.routers.log_analyzer import structure_analyze, StructureAnalyzeRequest
    from shared.schemas.base_event import TenantContext
    from shared.utils.encryption import encrypt

    secret = "test-key"
    mock_db = AsyncMock()
    mock_db.fetch_one = AsyncMock(return_value={
        "aws_access_key_id": encrypt("AKIAEXAMPLE", secret),
        "aws_secret_access_key": encrypt("secret123", secret),
        "s3_bucket": "test-bucket",
        "s3_region": "eu-central-1",
        "cp_code": None,
    })

    ctx = TenantContext(tenant_id="test_tenant")
    payload = StructureAnalyzeRequest(start_date="2026-03-01", end_date="2026-03-02")

    # Mock get_settings to return matching jwt_secret_key
    import unittest.mock
    mock_settings = unittest.mock.MagicMock()
    mock_settings.jwt_secret_key = secret

    with unittest.mock.patch("backend.routers.log_analyzer.get_settings", return_value=mock_settings):
        result = await structure_analyze(payload=payload, ctx=ctx, db=mock_db)

    assert "CP Code" in result["error"]
    assert result["fields"] == []
