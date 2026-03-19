"""Regex-based PII scrubber. Run before sending any text to LLM."""

from __future__ import annotations

import re

# Patterns: (regex, replacement)
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL]"),
    # Phone (international & local)
    (re.compile(r"\+?\d[\d\s\-()]{7,}\d"), "[PHONE]"),
    # IP address (v4)
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP]"),
    # Turkish national ID (11 digits)
    (re.compile(r"\b\d{11}\b"), "[TC_KIMLIK]"),
    # Credit card (basic)
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[CARD]"),
]


def scrub(text: str) -> str:
    """Remove PII from text using regex patterns."""
    result = text
    for pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def scrub_dict(data: dict[str, object], fields: list[str] | None = None) -> dict[str, object]:
    """Scrub string values in a dict. If fields is given, only scrub those keys."""
    result = dict(data)
    for key, value in result.items():
        if isinstance(value, str) and (fields is None or key in fields):
            result[key] = scrub(value)
    return result
