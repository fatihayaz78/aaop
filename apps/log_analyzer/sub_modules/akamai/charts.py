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


# ── 1. transfer_time_trend ──
def _chart_transfer_time_trend(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    avgs = []
    for h in hours:
        vals = [e.transfer_time_ms for e in buckets[h] if e.transfer_time_ms is not None]
        avgs.append(sum(vals) / len(vals) if vals else 0)
    fig = go.Figure(go.Scatter(x=hours, y=avgs, mode="lines+markers", line={"color": ACCENT}))
    _apply_layout(fig, "Transfer Time Trend (hourly avg ms)")
    summary = [{"hour": h, "avg_ms": round(a, 2)} for h, a in zip(hours[:5], avgs[:5], strict=False)]
    return fig, summary


# ── 2. dns_latency_distribution ──
def _chart_dns_latency_distribution(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    values = [e.dns_lookup_time_ms for e in logs if e.dns_lookup_time_ms is not None]
    fig = go.Figure(go.Histogram(x=values, nbinsx=50, marker_color=ACCENT))
    _apply_layout(fig, "DNS Latency Distribution (ms)")
    avg_val = sum(values) / len(values) if values else 0
    summary = [{"metric": "count", "value": len(values)}, {"metric": "avg_ms", "value": round(avg_val, 2)}]
    return fig, summary


# ── 3. turnaround_time_trend ──
def _chart_turnaround_time_trend(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    avgs = []
    for h in hours:
        vals = [e.turn_around_time_ms for e in buckets[h] if e.turn_around_time_ms is not None]
        avgs.append(sum(vals) / len(vals) if vals else 0)
    fig = go.Figure(go.Scatter(x=hours, y=avgs, mode="lines+markers", line={"color": ACCENT3}))
    _apply_layout(fig, "Turnaround Time Trend (hourly avg ms)")
    summary = [{"hour": h, "avg_ms": round(a, 2)} for h, a in zip(hours[:5], avgs[:5], strict=False)]
    return fig, summary


# ── 4. latency_correlation ──
def _chart_latency_correlation(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    transfer = [e.transfer_time_ms or 0 for e in logs if e.transfer_time_ms is not None and e.turn_around_time_ms is not None]
    turnaround = [e.turn_around_time_ms or 0 for e in logs if e.transfer_time_ms is not None and e.turn_around_time_ms is not None]
    fig = go.Figure(go.Scatter(x=transfer, y=turnaround, mode="markers", marker={"color": ACCENT, "opacity": 0.6}))
    _apply_layout(fig, "Latency Correlation: Transfer vs Turnaround")
    summary = [{"metric": "points", "value": len(transfer)}]
    return fig, summary


# ── 5. bandwidth_trend ──
def _chart_bandwidth_trend(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    values = [sum(e.bytes or 0 for e in buckets[h]) / (1024**3) for h in hours]
    fig = go.Figure(go.Bar(x=hours, y=values, marker_color=ACCENT))
    _apply_layout(fig, "Bandwidth Trend (GB/hour)")
    summary = [{"hour": h, "gb": round(v, 4)} for h, v in zip(hours[:5], values[:5], strict=False)]
    return fig, summary


# ── 6. bytes_vs_clientbytes ──
def _chart_bytes_vs_clientbytes(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    server_bytes = [sum(e.bytes or 0 for e in buckets[h]) / (1024**2) for h in hours]
    client_bytes = [sum(e.client_bytes or 0 for e in buckets[h]) / (1024**2) for h in hours]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hours, y=server_bytes, name="Server Bytes (MB)", marker_color=ACCENT))
    fig.add_trace(go.Bar(x=hours, y=client_bytes, name="Client Bytes (MB)", marker_color=ACCENT2))
    fig.update_layout(barmode="group")
    _apply_layout(fig, "Bytes vs Client Bytes (MB/hour)")
    total_s = sum(server_bytes)
    total_c = sum(client_bytes)
    summary = [{"metric": "total_server_mb", "value": round(total_s, 2)}, {"metric": "total_client_mb", "value": round(total_c, 2)}]
    return fig, summary


# ── 7. response_size_distribution ──
def _chart_response_size_distribution(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    small = sum(1 for e in logs if e.response_body_size is not None and e.response_body_size < 1_048_576)
    medium = sum(1 for e in logs if e.response_body_size is not None and 1_048_576 <= e.response_body_size < 10_485_760)
    large = sum(1 for e in logs if e.response_body_size is not None and e.response_body_size >= 10_485_760)
    labels = ["<1MB", "1-10MB", ">10MB"]
    values = [small, medium, large]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=[ACCENT, ACCENT3, ACCENT2]))
    _apply_layout(fig, "Response Size Distribution")
    summary = [{"bucket": label, "count": v} for label, v in zip(labels, values, strict=False)]
    return fig, summary


# ── 8. status_code_distribution ──
def _chart_status_code_distribution(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    groups: dict[str, int] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
    for e in logs:
        if e.status_code:
            bucket = f"{e.status_code // 100}xx"
            if bucket in groups:
                groups[bucket] += 1
    fig = go.Figure(go.Pie(labels=list(groups.keys()), values=list(groups.values()), hole=0.4))
    _apply_layout(fig, "HTTP Status Code Distribution")
    total = sum(groups.values()) or 1
    summary = [{"status": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in groups.items()]
    return fig, summary


# ── 9. error_rate_trend ──
def _chart_error_rate_trend(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    rates = []
    for h in hours:
        entries = buckets[h]
        errs = sum(1 for e in entries if e.status_code and e.status_code >= 400)
        rates.append(errs / len(entries) if entries else 0)
    fig = go.Figure(go.Scatter(x=hours, y=rates, mode="lines+markers", line={"color": ACCENT2}))
    _apply_layout(fig, "Error Rate (hourly)")
    summary = [{"hour": h, "rate": round(r, 4)} for h, r in zip(hours[:5], rates[:5], strict=False)]
    return fig, summary


# ── 10. error_code_breakdown ──
def _chart_error_code_breakdown(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.status_code and e.status_code >= 400 and e.error_code:
            counter[e.error_code] += 1
    top = counter.most_common(10)
    codes = [c for c, _ in top]
    counts = [n for _, n in top]
    fig = go.Figure(go.Bar(x=counts, y=codes, orientation="h", marker_color=ACCENT2))
    _apply_layout(fig, "Error Code Breakdown (Top 10)")
    summary = [{"code": c, "count": n} for c, n in top[:5]]
    return fig, summary


# ── 11. cache_hit_ratio_trend ──
def _chart_cache_hit_ratio_trend(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    rates = []
    for h in hours:
        entries = buckets[h]
        hits = sum(1 for e in entries if e.cache_hit == 1)
        total = sum(1 for e in entries if e.cache_hit is not None)
        rates.append(hits / total if total else 0)
    fig = go.Figure(go.Scatter(x=hours, y=rates, mode="lines+markers", line={"color": ACCENT3}))
    _apply_layout(fig, "Cache Hit Ratio (hourly)")
    summary = [{"hour": h, "ratio": round(r, 4)} for h, r in zip(hours[:5], rates[:5], strict=False)]
    return fig, summary


# ── 12. cache_status_breakdown ──
def _chart_cache_status_breakdown(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    status_labels = {0: "MISS", 1: "HIT", 2: "STALE", 3: "REVALIDATED"}
    traces_data: dict[int, list[int]] = {s: [] for s in status_labels}
    for h in hours:
        entries = buckets[h]
        counts: Counter[int] = Counter()
        for e in entries:
            if e.cache_status is not None:
                counts[e.cache_status] += 1
        for s in status_labels:
            traces_data[s].append(counts.get(s, 0))
    fig = go.Figure()
    colors = [ACCENT2, ACCENT3, ACCENT, "#FFD93D"]
    for (s, label), color in zip(status_labels.items(), colors, strict=False):
        fig.add_trace(go.Bar(x=hours, y=traces_data[s], name=label, marker_color=color))
    fig.update_layout(barmode="stack")
    _apply_layout(fig, "Cache Status Breakdown (hourly)")
    summary = [{"status": label, "total": sum(traces_data[s])} for s, label in status_labels.items()]
    return fig, summary


# ── 13. cache_vs_error ──
def _chart_cache_vs_error(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    miss_rates = []
    error_rates = []
    for h in hours:
        entries = buckets[h]
        total_cache = sum(1 for e in entries if e.cache_hit is not None)
        misses = sum(1 for e in entries if e.cache_hit == 0)
        errs = sum(1 for e in entries if e.status_code and e.status_code >= 400)
        miss_rates.append(misses / total_cache if total_cache else 0)
        error_rates.append(errs / len(entries) if entries else 0)
    fig = go.Figure(go.Scatter(x=miss_rates, y=error_rates, mode="markers", marker={"color": ACCENT2, "size": 10}))
    _apply_layout(fig, "Cache Miss vs Error Rate Correlation")
    summary = [{"metric": "hours_analyzed", "value": len(hours)}]
    return fig, summary


# ── 14. geographic_distribution ──
def _chart_geographic_distribution(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.country:
            counter[e.country] += 1
    top = counter.most_common(15)
    countries = [c for c, _ in top]
    counts = [n for _, n in top]
    fig = go.Figure(go.Bar(x=countries, y=counts, marker_color=ACCENT))
    _apply_layout(fig, "Geographic Distribution (Top 15)")
    summary = [{"country": c, "requests": n} for c, n in top[:5]]
    return fig, summary


# ── 15. city_top20 ──
def _chart_city_top20(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.city:
            counter[e.city] += 1
    top = counter.most_common(20)
    cities = [c for c, _ in top]
    counts = [n for _, n in top]
    fig = go.Figure(go.Bar(x=cities, y=counts, marker_color=ACCENT3))
    _apply_layout(fig, "Top 20 Cities")
    summary = [{"city": c, "requests": n} for c, n in top[:5]]
    return fig, summary


# ── 16. content_type_breakdown ──
def _chart_content_type_breakdown(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.content_type:
            counter[e.content_type] += 1
    top = counter.most_common(15)
    labels = [c for c, _ in top]
    values = [n for _, n in top]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
    _apply_layout(fig, "Content Type Breakdown")
    summary = [{"content_type": c, "count": n} for c, n in top[:5]]
    return fig, summary


# ── 17. top_urls ──
def _chart_top_urls(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.req_path:
            counter[e.req_path] += 1
    top = counter.most_common(20)
    paths = [p for p, _ in top]
    counts = [n for _, n in top]
    fig = go.Figure(go.Bar(x=counts, y=paths, orientation="h", marker_color=ACCENT))
    _apply_layout(fig, "Top 20 URLs")
    summary = [{"path": p, "requests": n} for p, n in top[:5]]
    return fig, summary


# ── 18. top_client_ips ──
def _chart_top_client_ips(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.client_ip:
            counter[e.client_ip] += 1
    top = counter.most_common(20)
    ips = [ip for ip, _ in top]
    counts = [n for _, n in top]
    fig = go.Figure(go.Bar(x=counts, y=ips, orientation="h", marker_color=ACCENT))
    _apply_layout(fig, "Top 20 Client IPs (hashed)")
    summary = [{"client_ip": ip, "requests": n} for ip, n in top[:5]]
    return fig, summary


# ── 19. edge_server_load ──
def _chart_edge_server_load(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[str] = Counter()
    for e in logs:
        if e.edge_ip:
            counter[e.edge_ip] += 1
    top = counter.most_common(20)
    edges = [ip for ip, _ in top]
    counts = [n for _, n in top]
    fig = go.Figure(go.Bar(x=edges, y=counts, marker_color=ACCENT))
    _apply_layout(fig, "Edge Server Load Distribution")
    summary = [{"edge_ip": ip, "requests": n} for ip, n in top[:5]]
    return fig, summary


# ── 20. peak_hour_heatmap ──
def _chart_peak_hour_heatmap(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    counter: Counter[int] = Counter()
    for e in logs:
        if e.req_time_sec:
            h = datetime.fromtimestamp(e.req_time_sec, tz=UTC).hour
            counter[h] += 1
    hours = sorted(counter.keys())
    counts = [counter[h] for h in hours]
    fig = go.Figure(go.Bar(x=hours, y=counts, marker_color=ACCENT))
    _apply_layout(fig, "Peak Hour Heatmap (request density)")
    summary = [{"hour": h, "requests": counter[h]} for h in hours[:5]]
    return fig, summary


# ── 21. anomaly_timeline ──
def _chart_anomaly_timeline(logs: list[AkamaiLogEntry]) -> tuple[go.Figure, list[dict]]:
    buckets = _hourly_buckets(logs)
    hours = sorted(buckets.keys())
    error_rates = []
    cache_miss_rates = []
    for h in hours:
        entries = buckets[h]
        errs = sum(1 for e in entries if e.status_code and e.status_code >= 400)
        error_rates.append(errs / len(entries) if entries else 0)
        total_cache = sum(1 for e in entries if e.cache_hit is not None)
        misses = sum(1 for e in entries if e.cache_hit == 0)
        cache_miss_rates.append(misses / total_cache if total_cache else 0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=error_rates, mode="lines", name="Error Rate", line={"color": ACCENT2}))
    fig.add_trace(go.Scatter(x=hours, y=cache_miss_rates, mode="lines", name="Cache Miss Rate", line={"color": ACCENT}))
    fig.add_hline(y=0.05, line_dash="dash", line_color=ACCENT2, annotation_text="Error Threshold")
    _apply_layout(fig, "Anomaly Timeline")
    summary = [{"hour": h, "error_rate": round(er, 4), "miss_rate": round(mr, 4)} for h, er, mr in zip(hours[:5], error_rates[:5], cache_miss_rates[:5], strict=False)]
    return fig, summary


# ── Chart definitions mapping ──
CHART_DEFINITIONS: dict[str, str] = {
    "transfer_time_trend": "transfer_time_ms hourly avg line chart",
    "dns_latency_distribution": "dns_lookup_time_ms histogram",
    "turnaround_time_trend": "turn_around_time_ms hourly avg line",
    "latency_correlation": "transfer_time vs turn_around_time scatter",
    "bandwidth_trend": "bytes hourly sum in GB, bar",
    "bytes_vs_clientbytes": "bytes vs client_bytes comparison bar",
    "response_size_distribution": "response_body_size histogram (3 buckets)",
    "status_code_distribution": "status_code pie 2xx/3xx/4xx/5xx",
    "error_rate_trend": "(4xx+5xx)/total hourly line",
    "error_code_breakdown": "error_code top 10 bar",
    "cache_hit_ratio_trend": "cache_hit (0/1) hourly ratio line",
    "cache_status_breakdown": "cache_status (0/1/2/3) stacked bar by hour",
    "cache_vs_error": "cache_hit=0 correlated with error_rate scatter",
    "geographic_distribution": "country top 15 bar",
    "city_top20": "city top 20 bar",
    "content_type_breakdown": "content_type pie",
    "top_urls": "req_path top 20 bar",
    "top_client_ips": "client_ip (hashed) top 20 bar",
    "edge_server_load": "edge_ip request distribution bar",
    "peak_hour_heatmap": "req_time_sec hour bar (request density)",
    "anomaly_timeline": "error_rate + cache_miss overlaid line",
}

_CHART_FUNCTIONS = {
    "transfer_time_trend": _chart_transfer_time_trend,
    "dns_latency_distribution": _chart_dns_latency_distribution,
    "turnaround_time_trend": _chart_turnaround_time_trend,
    "latency_correlation": _chart_latency_correlation,
    "bandwidth_trend": _chart_bandwidth_trend,
    "bytes_vs_clientbytes": _chart_bytes_vs_clientbytes,
    "response_size_distribution": _chart_response_size_distribution,
    "status_code_distribution": _chart_status_code_distribution,
    "error_rate_trend": _chart_error_rate_trend,
    "error_code_breakdown": _chart_error_code_breakdown,
    "cache_hit_ratio_trend": _chart_cache_hit_ratio_trend,
    "cache_status_breakdown": _chart_cache_status_breakdown,
    "cache_vs_error": _chart_cache_vs_error,
    "geographic_distribution": _chart_geographic_distribution,
    "city_top20": _chart_city_top20,
    "content_type_breakdown": _chart_content_type_breakdown,
    "top_urls": _chart_top_urls,
    "top_client_ips": _chart_top_client_ips,
    "edge_server_load": _chart_edge_server_load,
    "peak_hour_heatmap": _chart_peak_hour_heatmap,
    "anomaly_timeline": _chart_anomaly_timeline,
}


def generate_all_charts(
    metrics: AkamaiMetrics, logs: list[AkamaiLogEntry],
) -> dict[str, tuple[go.Figure, list[dict]]]:
    """Generate all 21 charts and return as dict of name -> (Figure, summary_table)."""
    results: dict[str, tuple[go.Figure, list[dict]]] = {}
    for name, func in _CHART_FUNCTIONS.items():
        results[name] = func(logs)
    return results
