"""Router tests for Live Intelligence — 15 tests with mocked DuckDB."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_duckdb, get_tenant_context
from backend.main import app
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext

HEADERS = {"X-Tenant-ID": "s_sport_plus"}

MOCK_EVENT_LIVE = {
    "event_id": "EVT-test001", "tenant_id": "s_sport_plus",
    "event_name": "NBA Playoffs Game 3", "sport": "basketball",
    "competition": "NBA", "kickoff_time": "2026-03-25T09:00:00+00:00",
    "status": "live", "expected_viewers": 420000, "peak_viewers": 380000,
    "pre_scale_done": True, "metrics": '{"drm_status":"healthy"}',
    "created_at": "2026-03-25T08:00:00+00:00",
}

MOCK_EVENT_UPCOMING = {
    **MOCK_EVENT_LIVE, "event_id": "EVT-test002",
    "event_name": "Galatasaray vs Fenerbahce", "sport": "football",
    "competition": "Super Lig", "status": "scheduled", "peak_viewers": None,
    "pre_scale_done": False,
}


def _make_mock_duck(*, events=None, empty=False):
    mock = MagicMock(spec=DuckDBClient)
    items = [] if empty else (events or [MOCK_EVENT_LIVE, MOCK_EVENT_UPCOMING])

    def _fetch_one(sql, params=None):
        sql_l = sql.lower()
        if "event_id = ?" in sql_l and params:
            target = params[0]
            for e in items:
                if e["event_id"] == target:
                    return e
            return None
        if "count" in sql_l and "status = 'live'" in sql_l:
            return {"cnt": sum(1 for e in items if e["status"] == "live")}
        if "count" in sql_l and "status = 'scheduled'" in sql_l:
            return {"cnt": sum(1 for e in items if e["status"] == "scheduled")}
        if "count" in sql_l and "pre_scale_done = false" in sql_l:
            return {"cnt": sum(1 for e in items if not e.get("pre_scale_done"))}
        if "max(peak_viewers)" in sql_l:
            peaks = [e["peak_viewers"] for e in items if e.get("peak_viewers")]
            return {"peak": max(peaks) if peaks else 0}
        if "count" in sql_l:
            return {"cnt": len(items)}
        return {"cnt": 0}

    def _fetch_all(sql, params=None):
        sql_l = sql.lower()
        result = list(items)
        if params:
            for p in params:
                if isinstance(p, str) and p in ("live", "scheduled", "completed"):
                    result = [e for e in result if e["status"] == p]
        return result

    mock.fetch_one.side_effect = _fetch_one
    mock.fetch_all.side_effect = _fetch_all
    return mock


@pytest.fixture
def client():
    mock_duck = _make_mock_duck()
    app.dependency_overrides[get_duckdb] = lambda: mock_duck
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ═══ Dashboard ═══

def test_dashboard_returns_expected_shape(client):
    data = client.get("/live/dashboard", headers=HEADERS).json()
    for key in ("live_now_count", "upcoming_24h_count", "total_events_7d", "pre_scale_pending", "drm_issues", "peak_viewers_today", "events_timeline"):
        assert key in data

def test_dashboard_timeline_has_24_slots(client):
    data = client.get("/live/dashboard", headers=HEADERS).json()
    assert len(data["events_timeline"]) == 24

# ═══ Events ═══

def test_events_list_returns_items(client):
    data = client.get("/live/events", headers=HEADERS).json()
    assert "items" in data and "total" in data

def test_events_filter_by_status_live(client):
    data = client.get("/live/events?status=live", headers=HEADERS).json()
    for item in data["items"]:
        assert item["status"] == "live"

def test_events_filter_by_status_upcoming(client):
    data = client.get("/live/events?status=scheduled", headers=HEADERS).json()
    for item in data["items"]:
        assert item["status"] == "scheduled"

def test_event_detail_found(client):
    data = client.get("/live/events/EVT-test001", headers=HEADERS).json()
    assert data.get("event_id") == "EVT-test001"

def test_event_detail_not_found(client):
    data = client.get("/live/events/nonexistent", headers=HEADERS).json()
    assert "error" in data

# ═══ DRM ═══

def test_drm_status_returns_three_providers(client):
    data = client.get("/live/drm/status", headers=HEADERS).json()
    for key in ("widevine", "fairplay", "playready"):
        assert key in data

def test_drm_status_has_overall_health(client):
    data = client.get("/live/drm/status", headers=HEADERS).json()
    assert "overall_health" in data

# ═══ SportRadar ═══

def test_sportradar_returns_mock_data(client):
    data = client.get("/live/sportradar", headers=HEADERS).json()
    assert "next_match" in data and "live_matches" in data

def test_sportradar_has_next_match(client):
    data = client.get("/live/sportradar", headers=HEADERS).json()
    assert "title" in data["next_match"]
    assert "kickoff" in data["next_match"]

# ═══ EPG ═══

def test_epg_returns_channels(client):
    data = client.get("/live/epg", headers=HEADERS).json()
    assert "channels" in data

def test_epg_has_four_channels(client):
    data = client.get("/live/epg", headers=HEADERS).json()
    assert len(data["channels"]) == 4

# ═══ Auth ═══

def test_dashboard_requires_auth(client):
    import backend.routers.live_intelligence as li
    import inspect
    assert "ctx" in inspect.signature(li.dashboard).parameters

def test_events_requires_auth(client):
    import backend.routers.live_intelligence as li
    import inspect
    assert "ctx" in inspect.signature(li.list_events).parameters
