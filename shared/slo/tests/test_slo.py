"""Tests for SLO calculator."""

from __future__ import annotations

import pytest

from shared.slo.slo_calculator import SLOCalculator, SLODefinition, SLOMeasurement


@pytest.fixture
def calculator() -> SLOCalculator:
    return SLOCalculator()


@pytest.fixture
def availability_slo() -> SLODefinition:
    return SLODefinition(id="slo_avail", tenant_id="t1", name="Availability",
                         metric="availability", target=0.999, operator="gte")


@pytest.fixture
def qoe_slo() -> SLODefinition:
    return SLODefinition(id="slo_qoe", tenant_id="t1", name="QoE",
                         metric="qoe_score", target=3.5, operator="gte")


@pytest.fixture
def cdn_slo() -> SLODefinition:
    return SLODefinition(id="slo_cdn", tenant_id="t1", name="CDN Error",
                         metric="cdn_error_rate", target=0.05, operator="lte")


def test_is_met_gte(calculator: SLOCalculator):
    assert calculator._is_met(0.9995, 0.999, "gte") is True
    assert calculator._is_met(0.998, 0.999, "gte") is False


def test_is_met_lte(calculator: SLOCalculator):
    assert calculator._is_met(0.03, 0.05, "lte") is True
    assert calculator._is_met(0.08, 0.05, "lte") is False


def test_error_budget_met(calculator: SLOCalculator):
    budget = calculator._error_budget(0.9995, 0.999, "gte")
    assert budget >= 100.0  # Met or exceeded target


def test_error_budget_breached(calculator: SLOCalculator):
    budget = calculator._error_budget(0.08, 0.05, "lte")
    assert budget < 100.0  # Under target


@pytest.mark.asyncio
async def test_calculate_availability(calculator: SLOCalculator, availability_slo: SLODefinition):
    m = await calculator.calculate(availability_slo, "t1", "sport_stream", 30)
    assert isinstance(m, SLOMeasurement)
    assert m.slo_id == "slo_avail"
    assert isinstance(m.is_met, bool)
    assert 0 <= m.measured_value <= 1.0


@pytest.mark.asyncio
async def test_calculate_all(calculator: SLOCalculator, availability_slo: SLODefinition, qoe_slo: SLODefinition):
    results = await calculator.calculate_all([availability_slo, qoe_slo], "t1", "sport_stream")
    assert len(results) == 2


def test_slo_definition_model():
    slo = SLODefinition(tenant_id="t1", name="Test", metric="availability", target=0.99, operator="gte")
    assert slo.window_days == 30
    assert slo.is_active is True


def test_slo_measurement_model():
    m = SLOMeasurement(slo_id="s1", tenant_id="t1", period_start="2026-03-01",
                       period_end="2026-03-30", measured_value=0.9995, target=0.999,
                       is_met=True, error_budget_pct=50.0)
    assert m.is_met is True
