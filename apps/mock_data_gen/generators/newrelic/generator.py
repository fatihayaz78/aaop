"""New Relic APM generator — per-minute APM transactions, 60s infra, error events.

Output: newrelic/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz (one file per day)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import (
    get_anomaly_for_date,
    is_anomaly_active,
)

logger = structlog.get_logger(__name__)

# Service profiles: (normal_cpu, normal_mem, normal_pods, normal_apdex, normal_error_rate)
SERVICES: dict[str, dict] = {
    "api-gateway": {
        "cpu": (20, 35), "mem": (45, 60), "pods": 3, "apdex": 0.95,
        "error_rate": 0.01, "hosts": ["api-pod-01", "api-pod-02", "api-pod-03", "api-pod-04"],
        "transactions": ["/auth/login", "/auth/token/refresh", "/content/stream", "/subscription/check"],
    },
    "drm-service": {
        "cpu": (15, 25), "mem": (40, 55), "pods": 2, "apdex": 0.97,
        "error_rate": 0.005, "hosts": ["drm-pod-01", "drm-pod-02", "drm-pod-03"],
        "transactions": ["/drm/widevine/license", "/drm/fairplay/license", "/drm/validate"],
    },
    "stream-packager": {
        "cpu": (40, 60), "mem": (55, 70), "pods": 4, "apdex": 0.92,
        "error_rate": 0.02, "hosts": ["packager-01", "packager-02", "packager-03", "packager-04"],
        "transactions": ["/package/hls", "/package/dash", "/manifest/generate"],
    },
    "auth-service": {
        "cpu": (10, 20), "mem": (35, 50), "pods": 2, "apdex": 0.98,
        "error_rate": 0.005, "hosts": ["auth-pod-01", "auth-pod-02"],
        "transactions": ["/auth/verify", "/auth/refresh", "/auth/revoke"],
    },
    "subscription-service": {
        "cpu": (10, 18), "mem": (30, 45), "pods": 2, "apdex": 0.96,
        "error_rate": 0.008, "hosts": ["sub-pod-01", "sub-pod-02"],
        "transactions": ["/sub/check", "/sub/upgrade", "/sub/cancel"],
    },
}

# Derby overrides (04 Mart 18-21 UTC)
DERBY_OVERRIDES: dict[str, dict] = {
    "api-gateway": {"cpu": (75, 92), "pods": 12, "apdex": 0.78, "error_rate": 0.08},
    "drm-service": {"cpu": (70, 88), "pods": 8, "apdex": 0.82, "error_rate": 0.06},
    "stream-packager": {"cpu": (85, 96), "pods": 16, "apdex": 0.71, "error_rate": 0.12},
    "auth-service": {"cpu": (60, 78), "pods": 6, "apdex": 0.85, "error_rate": 0.04},
    "subscription-service": {"cpu": (50, 68), "pods": 4, "apdex": 0.88, "error_rate": 0.03},
}

ERROR_CLASSES = {
    "api-gateway": ("TimeoutException", "Gateway timeout — upstream service unresponsive"),
    "drm-service": ("DRMException", "DRM license server error"),
    "stream-packager": ("CDNUpstreamException", "CDN upstream connection failed"),
    "auth-service": ("AuthException", "Authentication service error"),
    "subscription-service": ("RateLimitException", "Subscription check rate limited"),
}


class NewRelicGenerator(BaseGenerator):
    """Generates New Relic APM monitoring data."""

    @property
    def source_name(self) -> str:
        return "newrelic"

    def _is_derby_peak(self, multiplier: float, hour: int) -> bool:
        return multiplier >= 2.5 and 18 <= hour <= 21

    def _is_pre_scale(self, multiplier: float, hour: int, minute: int) -> bool:
        """Pre-scale starts at 17:15 UTC for derby."""
        return multiplier >= 2.5 and (hour == 17 and minute >= 15 or hour >= 18)

    def _get_service_profile(self, svc_name: str, hour: int, minute: int,
                             multiplier: float, anomaly: str | None,
                             ts: datetime) -> dict:
        """Get service metrics for current conditions."""
        base = SERVICES[svc_name]
        cpu_lo, cpu_hi = base["cpu"]
        mem_lo, mem_hi = base["mem"]
        pods = base["pods"]
        apdex = base["apdex"]
        error_rate = base["error_rate"]

        # Derby peak
        if self._is_derby_peak(multiplier, hour):
            ovr = DERBY_OVERRIDES[svc_name]
            cpu_lo, cpu_hi = ovr["cpu"]
            pods = ovr["pods"]
            apdex = ovr["apdex"]
            error_rate = ovr["error_rate"]
            mem_lo = min(80, mem_hi + 10)
            mem_hi = min(95, mem_hi + 25)
        elif self._is_pre_scale(multiplier, hour, minute):
            # Ramping up
            ovr = DERBY_OVERRIDES[svc_name]
            pods = ovr["pods"]  # pre-scaled
            cpu_lo = int((cpu_lo + ovr["cpu"][0]) / 2)
            cpu_hi = int((cpu_hi + ovr["cpu"][1]) / 2)

        # CDN outage
        if anomaly == "cdn_outage" and svc_name == "stream-packager":
            tr_time = ts.replace(tzinfo=None) + timedelta(hours=3)
            if is_anomaly_active(tr_time, "cdn_outage"):
                error_rate = 0.87
                apdex = 0.12
                cpu_lo, cpu_hi = 90, 98

        # Holiday
        if anomaly == "holiday":
            cpu_lo, cpu_hi = 8, 15
            pods = max(1, pods // 2)

        return {
            "cpu": (cpu_lo, cpu_hi),
            "mem": (mem_lo, mem_hi),
            "pods": pods,
            "apdex": apdex,
            "error_rate": error_rate,
        }

    def generate_day(self, target_date: date) -> int:
        """Generate all New Relic events for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)

        all_records: list[dict] = []

        for hour in range(24):
            for minute in range(60):
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, minute, 0, tzinfo=timezone.utc,
                )

                for svc_name, svc_cfg in SERVICES.items():
                    profile = self._get_service_profile(
                        svc_name, hour, minute, multiplier, anomaly, ts,
                    )

                    # ── apm_transaction (per minute per service) ──
                    for txn in svc_cfg["transactions"]:
                        base_rpm = self.rng.randint(50, 200)
                        if self._is_derby_peak(multiplier, hour):
                            base_rpm = self.rng.randint(800, 3000)

                        all_records.append({
                            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                            "event_type": "apm_transaction",
                            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
                            "service_name": svc_name,
                            "transaction_name": txn,
                            "duration_ms": round(self.rng.uniform(10, 300), 1),
                            "error_rate": round(profile["error_rate"] + self.rng.uniform(-0.005, 0.005), 4),
                            "throughput_rpm": base_rpm,
                            "apdex_score": round(max(0, min(1, profile["apdex"] + self.rng.uniform(-0.03, 0.03))), 3),
                            "slow_query_count": self.rng.randint(0, 3) if profile["error_rate"] > 0.05 else 0,
                            "host": None, "cpu_pct": None, "memory_pct": None,
                            "disk_io_mbps": None, "network_mbps": None, "pod_count": None,
                            "error_class": None, "error_message": None,
                            "stack_trace_hash": None, "impacted_users": None,
                        })

                # ── infrastructure (every 60s, each host) ──
                for svc_name, svc_cfg in SERVICES.items():
                    profile = self._get_service_profile(
                        svc_name, hour, minute, multiplier, anomaly, ts,
                    )
                    cpu_lo, cpu_hi = profile["cpu"]
                    mem_lo, mem_hi = profile["mem"]

                    active_hosts = svc_cfg["hosts"][:profile["pods"]]
                    if not active_hosts:
                        active_hosts = svc_cfg["hosts"][:1]

                    for host in active_hosts:
                        all_records.append({
                            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                            "event_type": "infrastructure",
                            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
                            "service_name": svc_name,
                            "transaction_name": None,
                            "duration_ms": None, "error_rate": None,
                            "throughput_rpm": None, "apdex_score": None, "slow_query_count": None,
                            "host": host,
                            "cpu_pct": round(self.rng.uniform(cpu_lo, cpu_hi), 1),
                            "memory_pct": round(self.rng.uniform(mem_lo, mem_hi), 1),
                            "disk_io_mbps": round(self.rng.uniform(5, 50), 1),
                            "network_mbps": round(self.rng.uniform(10, 200), 1),
                            "pod_count": profile["pods"],
                            "error_class": None, "error_message": None,
                            "stack_trace_hash": None, "impacted_users": None,
                        })

                # ── error_event (when error_rate > 2%) ──
                for svc_name, svc_cfg in SERVICES.items():
                    profile = self._get_service_profile(
                        svc_name, hour, minute, multiplier, anomaly, ts,
                    )
                    if profile["error_rate"] > 0.02:
                        err_cls, err_msg = ERROR_CLASSES[svc_name]
                        impacted = int(profile["error_rate"] * self.rng.randint(5000, 50000))

                        all_records.append({
                            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                            "event_type": "error_event",
                            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
                            "service_name": svc_name,
                            "transaction_name": None,
                            "duration_ms": None, "error_rate": round(profile["error_rate"], 4),
                            "throughput_rpm": None, "apdex_score": None, "slow_query_count": None,
                            "host": None, "cpu_pct": None, "memory_pct": None,
                            "disk_io_mbps": None, "network_mbps": None, "pod_count": None,
                            "error_class": err_cls,
                            "error_message": err_msg,
                            "stack_trace_hash": hashlib.sha256(
                                f"{err_cls}_{svc_name}_{minute}".encode()
                            ).hexdigest()[:32],
                            "impacted_users": impacted,
                        })

        # Write single daily file
        all_records.sort(key=lambda r: r["timestamp"])
        self.write_jsonl_gz(
            all_records,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            target_date.strftime("%d"),
            filename=f"{target_date.isoformat()}.jsonl.gz",
        )

        total = len(all_records)
        logger.info(
            "newrelic_day_complete",
            date=target_date.isoformat(),
            records=total,
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    NewRelicGenerator().generate_all()
