"""Tests for Akamai DataStream 2 parser."""

from __future__ import annotations

import json

from apps.log_analyzer.sub_modules.akamai.parser import (
    _hash_value,
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
    assert e.proto == "HTTP/2"
    assert e.req_host == "cdn.example.com"
    assert e.country == "TR"
    assert e.city == "Istanbul"


def test_parse_csv_pii_scrubbed(normal_csv: str):
    entries = parse_csv(normal_csv)
    # cliIP should be hashed, not raw
    assert entries[0].cli_ip_hash is not None
    assert entries[0].cli_ip_hash != "203.0.113.1"
    assert len(entries[0].cli_ip_hash) == 16  # SHA256 truncated

    # UA should be hashed
    assert entries[0].ua_hash is not None
    assert entries[0].ua_hash != "Mozilla/5.0"


def test_parse_csv_numeric_coercion(normal_csv: str):
    entries = parse_csv(normal_csv)
    assert isinstance(entries[0].req_time_sec, float)
    assert isinstance(entries[0].bytes, int)
    assert isinstance(entries[0].status_code, int)


def test_parse_csv_bool_coercion(normal_csv: str):
    entries = parse_csv(normal_csv)
    assert entries[0].cacheable is True
    assert entries[2].cacheable is False


def test_parse_csv_spike(spike_csv: str):
    entries = parse_csv(spike_csv)
    assert len(entries) == 10
    error_count = sum(1 for e in entries if e.status_code and e.status_code >= 400)
    assert error_count == 7  # 7 out of 10 are errors


def test_parse_json():
    data = [
        {"reqTimeSec": "1710849600.123", "CP": "12345", "Bytes": "4096",
         "cliIP": "10.0.0.1", "statusCode": "200", "proto": "HTTP/2",
         "cacheStatus": "HIT", "country": "TR", "city": "Istanbul"},
    ]
    entries = parse_json(json.dumps(data))
    assert len(entries) == 1
    assert entries[0].status_code == 200
    assert entries[0].cli_ip_hash != "10.0.0.1"  # PII scrubbed


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


def test_hash_value():
    h1 = _hash_value("test")
    h2 = _hash_value("test")
    h3 = _hash_value("other")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16
