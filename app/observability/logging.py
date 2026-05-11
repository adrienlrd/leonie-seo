"""Structured JSON logging for the Léonie SEO app."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Copy extra fields attached via logger.info("...", extra={...})
        for key, value in record.__dict__.items():
            if key not in {
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "name",
                "message",
                "taskName",
            }:
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
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    if not any(
        isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _JsonFormatter)
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
