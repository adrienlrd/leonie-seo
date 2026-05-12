"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging

from app.observability.logging import JsonFormatter


def _record_with_extra(extra: dict) -> logging.LogRecord:
    record = logging.LogRecord(
        name="leonie.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="event happened",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_allowed_extra_fields() -> None:
    record = _record_with_extra({"shop": "a.myshopify.com", "job_id": "job-1"})
    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "event happened"
    assert payload["shop"] == "a.myshopify.com"
    assert payload["job_id"] == "job-1"


def test_json_formatter_drops_sensitive_extra_fields() -> None:
    record = _record_with_extra(
        {
            "shop": "a.myshopify.com",
            "access_token": "shpat_secret",
            "password": "super-secret",
            "api_key": "key",
        }
    )
    raw = JsonFormatter().format(record)
    payload = json.loads(raw)

    assert payload["shop"] == "a.myshopify.com"
    assert "access_token" not in payload
    assert "password" not in payload
    assert "api_key" not in payload
    assert "shpat_secret" not in raw
