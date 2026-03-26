"""Tests for run_all.py, validate.py, and backend API endpoints."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.run_all import SOURCES, run
from apps.mock_data_gen.validate import ALL_CHECKS, run_all_checks


class TestRunAll:
    def test_run_all_single_source_medianova(self, tmp_path: Path):
        """Running medianova generator produces results."""
        # Patch OUTPUT_ROOT for the generator
        from apps.mock_data_gen.generators.medianova.generator import MedianovaGenerator

        gen = MedianovaGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_day(date(2026, 1, 2))
        assert count > 0

    def test_run_all_date_range(self, tmp_path: Path):
        """Running EPG for a date range produces results for each day."""
        from apps.mock_data_gen.generators.epg.generator import EPGGenerator

        gen = EPGGenerator(output_root=tmp_path, seed=42)
        results = gen.generate_range(date(2026, 1, 1), date(2026, 1, 3))
        assert len(results) == 3
        assert all(v > 0 for v in results.values())

    def test_all_13_sources_registered(self):
        """SOURCES dict has all 13 generators."""
        assert len(SOURCES) == 13
        expected = {
            "medianova", "origin_logs", "drm_widevine", "drm_fairplay",
            "player_events", "npaw", "api_logs", "newrelic",
            "crm", "epg", "billing", "push_notifications", "app_reviews",
        }
        assert set(SOURCES.keys()) == expected


class TestValidate:
    def test_validate_all_checks_exist(self):
        """All 8 validation check functions are registered."""
        assert len(ALL_CHECKS) == 8
        names = [fn.__name__ for fn in ALL_CHECKS]
        assert "check_medianova_origin_correlation" in names
        assert "check_player_npaw_qoe_correlation" in names
        assert "check_cdn_outage_spike" in names
        assert "check_elclasico_spike" in names
        assert "check_fairplay_ios_only" in names
        assert "check_billing_crm_correlation" in names
        assert "check_push_alert_on_outage" in names
        assert "check_epg_pre_scale" in names

    def test_validate_returns_results(self):
        """run_all_checks returns a list of check results."""
        results = run_all_checks()
        assert len(results) == 8
        for r in results:
            assert "name" in r
            assert "status" in r
            assert r["status"] in ("pass", "fail", "skip")
            assert "detail" in r


class TestAPIEndpoints:
    def test_api_sources_endpoint(self):
        """FastAPI /mock-data-gen/sources returns 13 sources."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        res = client.get("/mock-data-gen/sources")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 13
        names = {s["name"] for s in data}
        assert "medianova" in names
        assert "app_reviews" in names

    def test_api_schema_endpoint_medianova(self):
        """GET /mock-data-gen/sources/medianova/schema returns fields."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        res = client.get("/mock-data-gen/sources/medianova/schema")
        assert res.status_code == 200
        data = res.json()
        assert data["source_name"] == "medianova"
        assert data["field_count"] == 33
        assert len(data["fields"]) == 33
        assert len(data["categories"]) > 0

    def test_api_generate_returns_job_id(self):
        """POST /mock-data-gen/generate returns a job_id."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        res = client.post("/mock-data-gen/generate", json={
            "sources": ["epg"],
            "start_date": "2026-01-02",
            "end_date": "2026-01-02",
        })
        assert res.status_code == 200
        data = res.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_api_output_summary(self):
        """GET /mock-data-gen/output/summary returns list."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        res = client.get("/mock-data-gen/output/summary")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_api_validate_endpoint(self):
        """POST /mock-data-gen/validate returns check results."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        res = client.post("/mock-data-gen/validate")
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert data["total"] == 8
        assert "checks" in data
