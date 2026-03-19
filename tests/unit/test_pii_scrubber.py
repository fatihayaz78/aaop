"""Tests for shared/utils/pii_scrubber.py."""

from __future__ import annotations

from shared.utils.pii_scrubber import scrub, scrub_dict


def test_scrub_email():
    assert scrub("Contact admin@example.com for help") == "Contact [EMAIL] for help"


def test_scrub_ip():
    assert scrub("Server at 192.168.1.100 is down") == "Server at [IP] is down"


def test_scrub_phone():
    result = scrub("Call +90 532 123 4567 now")
    assert "[PHONE]" in result


def test_scrub_tc_kimlik():
    result = scrub("TC: 12345678901")
    assert "12345678901" not in result


def test_scrub_no_pii():
    text = "Error rate is 5.2% on edge node cdn-eu-west"
    assert scrub(text) == text


def test_scrub_multiple():
    text = "User admin@test.com from 10.0.0.1 called"
    result = scrub(text)
    assert "[EMAIL]" in result
    assert "[IP]" in result


def test_scrub_dict_all_fields():
    data = {"name": "admin@test.com", "note": "From 10.0.0.1", "count": 5}
    result = scrub_dict(data)
    assert result["name"] == "[EMAIL]"
    assert "[IP]" in result["note"]
    assert result["count"] == 5


def test_scrub_dict_specific_fields():
    data = {"email": "a@b.com", "ip": "1.2.3.4", "keep": "a@b.com"}
    result = scrub_dict(data, fields=["email", "ip"])
    assert result["email"] == "[EMAIL]"
    assert result["ip"] == "[IP]"
    assert result["keep"] == "a@b.com"
