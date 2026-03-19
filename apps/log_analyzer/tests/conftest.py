"""Log analyzer test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.log_analyzer.config import LogAnalyzerConfig
from apps.log_analyzer.sub_modules.akamai.analyzer import AkamaiAnalyzer
from apps.log_analyzer.sub_modules.akamai.parser import parse_csv
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def log_analyzer_config(tmp_path: Path) -> LogAnalyzerConfig:
    return LogAnalyzerConfig(
        docx_reports_dir=str(tmp_path / "reports"),
        logs_cache_dir=str(tmp_path / "logs"),
    )


@pytest.fixture
def normal_csv() -> str:
    return (FIXTURES_DIR / "sample_akamai_normal.csv").read_text()


@pytest.fixture
def spike_csv() -> str:
    return (FIXTURES_DIR / "sample_akamai_spike.csv").read_text()


@pytest.fixture
def normal_entries(normal_csv: str) -> list[AkamaiLogEntry]:
    return parse_csv(normal_csv)


@pytest.fixture
def spike_entries(spike_csv: str) -> list[AkamaiLogEntry]:
    return parse_csv(spike_csv)


@pytest.fixture
def analyzer(log_analyzer_config: LogAnalyzerConfig) -> AkamaiAnalyzer:
    return AkamaiAnalyzer(log_analyzer_config)
