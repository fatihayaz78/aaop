"""Akamai DataStream 2 sub-module."""

from __future__ import annotations

from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.parser import parse_auto, parse_csv
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiConfig, AkamaiLogEntry, AkamaiMetrics
from apps.log_analyzer.sub_modules.base_sub_module import BaseSubModule

__all__ = [
    "AkamaiAnalyzer",
    "AkamaiConfig",
    "AkamaiLogEntry",
    "AkamaiMetrics",
    "AkamaiSubModule",
    "parse_auto",
    "parse_csv",
]


class AkamaiSubModule(BaseSubModule):
    name = "akamai"
    display_name = "Akamai DataStream 2"

    def __init__(self) -> None:
        from apps.log_analyzer.config import LogAnalyzerConfig

        self._config = LogAnalyzerConfig()
        self._analyzer = AkamaiAnalyzer(self._config)

    async def configure(self, config: dict) -> None:
        self._akamai_config = AkamaiConfig(**config)

    async def fetch_logs(self, tenant_id: str, params: dict) -> list[dict]:
        import boto3

        s3 = boto3.client("s3")
        bucket = params.get("s3_bucket", self._config.s3_bucket)
        prefix = params.get("s3_prefix", self._config.s3_prefix)
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=100)
        results: list[dict] = []
        for obj in response.get("Contents", []):
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])
            content = body["Body"].read().decode("utf-8")
            entries = parse_auto(content)
            results.extend([e.model_dump() for e in entries])
        return results

    async def analyze(self, tenant_id: str, logs: list[dict]) -> dict:
        entries = [AkamaiLogEntry(**log) for log in logs]
        metrics = self._analyzer.calculate_metrics(entries)
        anomalies = self._analyzer.detect_anomalies(metrics)
        period_start, period_end = self._analyzer.get_period(entries)
        return {
            "metrics": metrics.model_dump(),
            "anomalies": [a.model_dump() for a in anomalies],
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

    async def generate_report(self, tenant_id: str, analysis: dict) -> str:
        from apps.log_analyzer.sub_modules.akamai.reporter import AkamaiReporter

        reporter = AkamaiReporter(self._config)
        metrics = AkamaiMetrics(**analysis["metrics"])
        from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiAnomaly

        anomalies = [AkamaiAnomaly(**a) for a in analysis["anomalies"]]
        return reporter.generate(tenant_id=tenant_id, metrics=metrics, anomalies=anomalies)


# Register with the SubModuleRegistry
from apps.log_analyzer.sub_modules import SubModuleRegistry  # noqa: E402

SubModuleRegistry.register(AkamaiSubModule)
