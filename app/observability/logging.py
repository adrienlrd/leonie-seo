"""Structured JSON logging for the Léonie SEO app."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_ALLOWED_EXTRA_FIELDS = frozenset(
    {
        "shop",
        "tenant_id",
        "request_id",
        "job_id",
        "queue",
        "status",
        "provider",
        "model",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "latency_ms",
        "duration_ms",
        "resource_id",
        "resource_type",
        "endpoint",
        "plan",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Copy only safe, structured fields attached via logger.info("...", extra={...}).
        # This prevents accidental token/secret leakage through arbitrary extras.
        for key, value in record.__dict__.items():
            if key in _ALLOWED_EXTRA_FIELDS:
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(level: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON on stdout.

    Should be called once at application startup. Safe to call multiple times.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    if not any(
        isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JsonFormatter)
        for h in root.handlers
    ):
        root.addHandler(handler)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    The logger emits JSON if configure_json_logging() has been called,
    otherwise falls back to stdlib default format.

    Args:
        name: Logger name (typically __name__).
    """
    return logging.getLogger(name)
