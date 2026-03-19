"""21 Plotly charts for Akamai analysis. Dark theme. kaleido==0.2.1 for image export."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import plotly.graph_objects as go

from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry, AkamaiMetrics

# Dark theme colors
BG = "#04080F"
PAPER = "#080E1A"
TEXT = "#E8EFF8"
ACCENT = "#00E5FF"
ACCENT2 = "#FF6B6B"
ACCENT3 = "#69DB7C"
GRID = "#1a1f36"

_LAYOUT_DEFAULTS = {
    "template": "plotly_dark",
    "paper_bgcolor": PAPER,
    "plot_bgcolor": BG,
    "font": {"color": TEXT, "size": 12},
    "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
}


def _apply_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(title=title, **_LAYOUT_DEFAULTS)
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def _hourly_buckets(logs: list[AkamaiLogEntry]) -> dict[int, list[AkamaiLogEntry]]:
    buckets: dict[int, list[AkamaiLogEntry]] = {}
    for e in logs:
        if e.req_time_sec:
            h = datetime.fromtimestamp(e.req_time_sec, tz=UTC).hour
            buckets.setdefault(h, []).append(e)
    return buckets


def _chart_error_rate_ts(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    rates = []
    for h in hours:
        entries = buckets[h]
        errs = sum(1 for e in entries if e.status_code and e.status_code >= 400)
        rates.append(errs / len(entries) if entries else 0)
    fig = go.Figure(go.Scatter(x=hours, y=rates, mode="lines+markers", line={"color": ACCENT2}))
    return _apply_layout(fig, "Error Rate (hourly)")


def _chart_cache_hit_ts(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    rates = []
    for h in hours:
        entries = buckets[h]
        hits = sum(1 for e in entries if e.cache_status and e.cache_status.upper() == "HIT")
        total = sum(1 for e in entries if e.cache_status is not None)
        rates.append(hits / total if total else 0)
    fig = go.Figure(go.Scatter(x=hours, y=rates, mode="lines+markers", line={"color": ACCENT3}))
    return _apply_layout(fig, "Cache Hit Rate (hourly)")


def _chart_bytes(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    values = [sum(e.bytes or 0 for e in buckets[h]) / (1024 * 1024) for h in hours]
    fig = go.Figure(go.Bar(x=hours, y=values, marker_color=ACCENT))
    return _apply_layout(fig, "Byte Transfer Volume (MB/hour)")


def _chart_requests(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    counts = [len(buckets[h]) for h in hours]
    fig = go.Figure(go.Bar(x=hours, y=counts, marker_color=ACCENT))
    return _apply_layout(fig, "Request Volume (hourly)")


def _chart_ttfb_hist(logs: list[AkamaiLogEntry]) -> go.Figure:
    values = [e.req_time_sec * 1000 for e in logs if e.req_time_sec]
    fig = go.Figure(go.Histogram(x=values, nbinsx=50, marker_color=ACCENT))
    return _apply_layout(fig, "TTFB Distribution (ms)")


def _chart_status_pie(metrics: AkamaiMetrics) -> go.Figure:
    labels = [str(k) for k in metrics.status_breakdown]
    values = list(metrics.status_breakdown.values())
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
    return _apply_layout(fig, "HTTP Status Code Distribution")


def _chart_top_edges(metrics: AkamaiMetrics) -> go.Figure:
    edges = [e["edge"][:16] for e in metrics.edge_breakdown]
    reqs = [e["requests"] for e in metrics.edge_breakdown]
    fig = go.Figure(go.Bar(x=reqs, y=edges, orientation="h", marker_color=ACCENT))
    return _apply_layout(fig, "Top 10 Edge Servers")


def _chart_geo(metrics: AkamaiMetrics) -> go.Figure:
    countries = [g["country"] for g in metrics.geo_breakdown[:15]]
    reqs = [g["requests"] for g in metrics.geo_breakdown[:15]]
    fig = go.Figure(go.Bar(x=countries, y=reqs, marker_color=ACCENT))
    return _apply_layout(fig, "Geographic Distribution")


def _chart_tls(metrics: AkamaiMetrics) -> go.Figure:
    labels = list(metrics.tls_breakdown.keys())
    values = list(metrics.tls_breakdown.values())
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
    return _apply_layout(fig, "TLS Version Distribution")


def _chart_protocol(metrics: AkamaiMetrics) -> go.Figure:
    labels = list(metrics.protocol_breakdown.keys())
    values = list(metrics.protocol_breakdown.values())
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
    return _apply_layout(fig, "Protocol Distribution")


def _chart_error_paths(logs: list[AkamaiLogEntry]) -> go.Figure:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.status_code and e.status_code >= 400 and e.req_path:
            counter[e.req_path] += 1
    top = counter.most_common(20)
    paths = [p for p, _ in top]
    counts = [c for _, c in top]
    fig = go.Figure(go.Bar(x=counts, y=paths, orientation="h", marker_color=ACCENT2))
    return _apply_layout(fig, "Top 20 Error Paths")


def _chart_cache_status(metrics: AkamaiMetrics) -> go.Figure:
    # Derive from edge_breakdown as proxy
    fig = go.Figure(go.Bar(
        x=[e["edge"][:16] for e in metrics.edge_breakdown],
        y=[e["requests"] for e in metrics.edge_breakdown],
        marker_color=ACCENT3,
    ))
    return _apply_layout(fig, "Cache Status Breakdown")


def _chart_bw_error(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    bw = [sum(e.bytes or 0 for e in buckets[h]) / (1024 * 1024) for h in hours]
    errs = [sum(1 for e in buckets[h] if e.status_code and e.status_code >= 400) for h in hours]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hours, y=bw, name="Bandwidth (MB)", marker_color=ACCENT))
    fig.add_trace(go.Scatter(x=hours, y=errs, name="Errors", yaxis="y2", line={"color": ACCENT2}))
    fig.update_layout(yaxis2={"overlaying": "y", "side": "right", "title": "Errors"})
    return _apply_layout(fig, "Bandwidth vs Error Rate")


def _chart_peak_hours(metrics: AkamaiMetrics) -> go.Figure:
    hours = [p["hour"] for p in metrics.peak_hours]
    reqs = [p["requests"] for p in metrics.peak_hours]
    fig = go.Figure(go.Bar(x=hours, y=reqs, marker_color=ACCENT))
    return _apply_layout(fig, "Peak Hour Heatmap")


def _chart_origin_edge(metrics: AkamaiMetrics) -> go.Figure:
    edges = [e["edge"][:16] for e in metrics.edge_breakdown]
    requests = [e["requests"] for e in metrics.edge_breakdown]
    errors = [e["errors"] for e in metrics.edge_breakdown]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=edges, y=requests, name="Requests", marker_color=ACCENT))
    fig.add_trace(go.Bar(x=edges, y=errors, name="Errors", marker_color=ACCENT2))
    fig.update_layout(barmode="group")
    return _apply_layout(fig, "Origin vs Edge Ratio")


def _chart_req_size(logs: list[AkamaiLogEntry]) -> go.Figure:
    sizes = [e.headers_size or 0 for e in logs if e.headers_size]
    fig = go.Figure(go.Histogram(x=sizes, nbinsx=30, marker_color=ACCENT))
    return _apply_layout(fig, "Request Size Distribution")


def _chart_resp_size(logs: list[AkamaiLogEntry]) -> go.Figure:
    sizes = [e.body_size or 0 for e in logs if e.body_size]
    fig = go.Figure(go.Histogram(x=sizes, nbinsx=30, marker_color=ACCENT))
    return _apply_layout(fig, "Response Size Distribution")


def _chart_error_by_edge(metrics: AkamaiMetrics) -> go.Figure:
    edges = [e["edge"][:16] for e in metrics.edge_breakdown]
    rates = [e["errors"] / e["requests"] if e["requests"] > 0 else 0 for e in metrics.edge_breakdown]
    fig = go.Figure(go.Bar(x=edges, y=rates, marker_color=ACCENT2))
    return _apply_layout(fig, "Error Rate by Edge")


def _chart_ttfb_trend(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    avgs = []
    for h in hours:
        vals = [e.req_time_sec * 1000 for e in buckets[h] if e.req_time_sec]
        avgs.append(sum(vals) / len(vals) if vals else 0)
    fig = go.Figure(go.Scatter(x=hours, y=avgs, mode="lines+markers", line={"color": ACCENT}))
    return _apply_layout(fig, "TTFB Trend (hourly avg)")


def _chart_req_by_content_type(logs: list[AkamaiLogEntry]) -> go.Figure:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.req_path:
            ext = e.req_path.rsplit(".", 1)[-1][:10] if "." in e.req_path else "unknown"
            counter[ext] += 1
    top = counter.most_common(15)
    fig = go.Figure(go.Bar(x=[t[0] for t in top], y=[t[1] for t in top], marker_color=ACCENT))
    return _apply_layout(fig, "Request Rate by Content Type")


def _chart_anomaly_timeline(logs: list[AkamaiLogEntry]) -> go.Figure:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    error_rates = []
    for h in hours:
        entries = buckets[h]
        errs = sum(1 for e in entries if e.status_code and e.status_code >= 400)
        error_rates.append(errs / len(entries) if entries else 0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=error_rates, mode="lines", name="Error Rate", line={"color": ACCENT2}))
    fig.add_hline(y=0.05, line_dash="dash", line_color=ACCENT2, annotation_text="Threshold")
    return _apply_layout(fig, "Anomaly Timeline")


def generate_all_charts(metrics: AkamaiMetrics, logs: list[AkamaiLogEntry]) -> dict[str, go.Figure]:
    """Generate all 21 charts and return as dict of name → Figure."""
    return {
        "error_rate_timeseries": _chart_error_rate_ts(logs),
        "cache_hit_rate": _chart_cache_hit_ts(logs),
        "byte_transfer": _chart_bytes(logs),
        "request_volume": _chart_requests(logs),
        "ttfb_histogram": _chart_ttfb_hist(logs),
        "http_status_pie": _chart_status_pie(metrics),
        "top_edges": _chart_top_edges(metrics),
        "geo_distribution": _chart_geo(metrics),
        "tls_version": _chart_tls(metrics),
        "protocol_dist": _chart_protocol(metrics),
        "top_error_paths": _chart_error_paths(logs),
        "cache_status": _chart_cache_status(metrics),
        "bandwidth_vs_error": _chart_bw_error(logs),
        "peak_hour_heatmap": _chart_peak_hours(metrics),
        "origin_vs_edge": _chart_origin_edge(metrics),
        "request_size_dist": _chart_req_size(logs),
        "response_size_dist": _chart_resp_size(logs),
        "error_rate_by_edge": _chart_error_by_edge(metrics),
        "ttfb_trend": _chart_ttfb_trend(logs),
        "request_by_content_type": _chart_req_by_content_type(logs),
        "anomaly_timeline": _chart_anomaly_timeline(logs),
    }
