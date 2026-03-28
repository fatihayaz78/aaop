"""Tests for P1/P2 log query helpers added in S-DI-04."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_db(overrides: dict | None = None):
    d = overrides or {}

    def mock_query(tenant_id, sql):
        s = sql.lower()

        # App reviews
        if "app_reviews" in s:
            if "avg(rating)" in s:
                return [{"avg_r": d.get("review_avg", 3.8)}]
            if "sentiment" in s and "group by" in s:
                return [{"sentiment": "positive", "cnt": 60}, {"sentiment": "negative", "cnt": 20}]
            if "category" in s and "group by" in s:
                return [{"category": "buffering", "cnt": 30}]
            if "count(*)" in s:
                return [{"cnt": d.get("review_total", 150)}]

        # EPG
        if "epg" in s:
            if "channel" in s and "group by" in s:
                return [{"channel": "s_sport_1", "cnt": 500}]
            if "event_type = 'live_sport'" in s:
                return [{"cnt": 45}]
            if "pre_scale_required = 1" in s:
                return [{"cnt": 12}]
            if "count(*)" in s:
                return [{"cnt": d.get("epg_total", 2000)}]

        # CRM
        if "crm_subscriber" in s:
            if "avg(churn_risk)" in s:
                return [{"avg_cr": d.get("churn_avg", 0.35)}]
            if "churn_risk > 0.7" in s:
                return [{"cnt": d.get("at_risk", 1200)}]
            if "subscription_tier" in s and "group by" in s:
                return [{"subscription_tier": "premium", "cnt": 5000}, {"subscription_tier": "free", "cnt": 3000}]
            if "count(*)" in s:
                return [{"cnt": d.get("crm_total", 15000)}]

        # Billing
        if "billing" in s:
            if "sum(amount)" in s:
                return [{"total": d.get("revenue", 450000.0)}]
            if "payment_status = 'failed'" in s:
                return [{"cnt": d.get("failed", 120)}]
            if "event_type" in s and "group by" in s:
                return [{"event_type": "charge", "cnt": 8000}, {"event_type": "cancellation", "cnt": 50}]
            if "count(*)" in s:
                return [{"cnt": d.get("billing_total", 10000)}]

        # Data source stats
        if "count(*)" in s:
            return [{"cnt": 1000}]

        return []

    m = MagicMock()
    m.query = MagicMock(side_effect=mock_query)
    return m


class TestGetAppReviews:
    def test_returns_correct_shape(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_app_reviews
            result = get_app_reviews("t1", hours=168)
            assert result["total_reviews"] == 150
            assert result["avg_rating"] == 3.8
            assert "positive" in result["sentiment_breakdown"]


class TestGetEPGSchedule:
    def test_returns_channels_and_counts(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_epg_schedule
            result = get_epg_schedule("t1")
            assert result["total_programs"] == 2000
            assert result["live_sport_count"] == 45
            assert result["pre_scale_needed"] == 12


class TestGetChurnMetrics:
    def test_returns_tier_breakdown(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_churn_metrics
            result = get_churn_metrics("t1")
            assert result["total_subscribers"] == 15000
            assert result["avg_churn_risk"] == 0.35
            assert result["at_risk_count"] == 1200
            assert "premium" in result["tier_breakdown"]


class TestGetBillingSummary:
    def test_returns_revenue_and_failures(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_billing_summary
            result = get_billing_summary("t1", hours=720)
            assert result["total_transactions"] == 10000
            assert result["total_revenue_tl"] == 450000.0
            assert result["failed_count"] == 120


class TestGetDataSourceStats:
    def test_returns_all_13_sources(self):
        mock_db = _make_mock_db()
        with patch("shared.ingest.log_queries._get_logs_db", return_value=mock_db):
            from shared.ingest.log_queries import get_data_source_stats
            result = get_data_source_stats("t1")
            assert len(result["sources"]) == 13
            assert result["total_rows"] > 0
