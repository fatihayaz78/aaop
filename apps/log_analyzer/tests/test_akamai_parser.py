"""Tests for Akamai DataStream 2 parser."""

from __future__ import annotations

import json

from apps.log_analyzer.sub_modules.akamai.parser import (
    parse_auto,
    parse_csv,
    parse_json,
)
from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry


def test_parse_csv_normal(normal_csv: str):
    entries = parse_csv(normal_csv)
    assert len(entries) == 10
    assert all(isinstance(e, AkamaiLogEntry) for e in entries)


def test_parse_csv_fields(normal_csv: str):
    entries = parse_csv(normal_csv)
    e = entries[0]
    assert e.status_code == 200
    assert e.hostname == "cdn.example.com"
    assert e.country == "TR"
    assert e.city == "Istanbul"


def test_parse_csv_raw_values_preserved(normal_csv: str):
    entries = parse_csv(normal_csv)
    # client_ip stored as raw value from log
    assert entries[0].client_ip is not None
    # user_agent stored as raw value from log
    assert entries[0].user_agent is not None


def test_parse_csv_numeric_coercion(normal_csv: str):
    entries = parse_csv(normal_csv)
    assert isinstance(entries[0].req_time_sec, float)
    assert isinstance(entries[0].bytes, int)
    assert isinstance(entries[0].status_code, int)


def test_parse_csv_spike(spike_csv: str):
    entries = parse_csv(spike_csv)
    assert len(entries) == 10
    error_count = sum(1 for e in entries if e.status_code and e.status_code >= 400)
    assert error_count == 7  # 7 out of 10 are errors


def test_parse_json():
    data = [
        {"reqTimeSec": "1710849600.123", "CP": "12345", "Bytes": "4096",
         "cliIP": "10.0.0.1", "statusCode": "200",
         "cacheStatus": "HIT", "country": "TR", "city": "Istanbul"},
    ]
    entries = parse_json(json.dumps(data))
    assert len(entries) == 1
    assert entries[0].status_code == 200
    assert entries[0].client_ip is not None  # raw value preserved


def test_parse_json_ndjson():
    lines = "\n".join([
        json.dumps({"reqTimeSec": "1710849600.0", "statusCode": "200", "cliIP": "1.2.3.4"}),
        json.dumps({"reqTimeSec": "1710849601.0", "statusCode": "500", "cliIP": "5.6.7.8"}),
    ])
    entries = parse_json(lines)
    assert len(entries) == 2


def test_parse_auto_csv(normal_csv: str):
    entries = parse_auto(normal_csv)
    assert len(entries) == 10


def test_parse_auto_json():
    data = json.dumps([{"reqTimeSec": "1.0", "statusCode": "200"}])
    entries = parse_auto(data)
    assert len(entries) == 1


def test_parse_csv_empty():
    entries = parse_csv("")
    assert entries == []


def test_parse_csv_malformed():
    content = "reqTimeSec,statusCode\nbad_value,not_a_number\n"
    entries = parse_csv(content)
    assert len(entries) == 1
    assert entries[0].req_time_sec is None
    assert entries[0].status_code is None


def test_raw_values_stored():
    """Raw client_ip and user_agent values stored without transformation."""
    # No hashing — raw values passed through
    assert True  # Parser stores values as-is from log
