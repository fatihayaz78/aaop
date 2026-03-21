"""Tests for Akamai chart generation."""

from __future__ import annotations

import plotly.graph_objects as go

from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.charts import CHART_DEFINITIONS, generate_all_charts
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry, AkamaiMetrics


def test_generate_all_charts(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    charts = generate_all_charts(metrics, normal_entries)
    assert len(charts) == 21
    for name, value in charts.items():
        assert isinstance(value, tuple), f"{name} is not a tuple"
        assert isinstance(value[0], go.Figure), f"{name}[0] is not a Figure"
        assert isinstance(value[1], list), f"{name}[1] is not a list"


def test_chart_names(analyzer: AkamaiAnalyzer, normal_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(normal_entries)
    charts = generate_all_charts(metrics, normal_entries)
    expected = set(CHART_DEFINITIONS.keys())
    assert set(charts.keys()) == expected


def test_charts_with_spike_data(analyzer: AkamaiAnalyzer, spike_entries: list[AkamaiLogEntry]):
    metrics = analyzer.calculate_metrics(spike_entries)
    charts = generate_all_charts(metrics, spike_entries)
    assert len(charts) == 21
    for name, value in charts.items():
        assert isinstance(value, tuple), f"{name} is not a tuple"
        assert isinstance(value[0], go.Figure), f"{name}[0] is not a Figure"


def test_charts_empty_data():
    metrics = AkamaiMetrics()
    charts = generate_all_charts(metrics, [])
    assert len(charts) == 21
    for name, value in charts.items():
        assert isinstance(value, tuple), f"{name} is not a tuple"
