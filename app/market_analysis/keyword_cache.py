"""Shared, cross-shop cache for keyword market data (volume/difficulty/SERP-PAA).

Keyword market data is identical for every shop — "harnais chien" has the same
French search volume regardless of which merchant asks. So this cache is keyed by
``data_type + location + language + keyword`` and is intentionally NOT scoped to a
shop: the first shop in a niche pays the provider call, every later shop (or rerun)
reads from cache. This is the main lever that keeps paid-provider cost flat as more
shops are onboarded.

TTL differs by data type: volume/difficulty are stable (long TTL), SERP/PAA change
faster (short TTL).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db_adapter import DB_PATH, get_conn

# Stable market data → long TTL; volatile SERP/PAA → short TTL. Env-overridable.
METRICS_TTL_DAYS = int(os.getenv("KEYWORD_CACHE_TTL_DAYS", "60"))
SERP_TTL_DAYS = int(os.getenv("SERP_CACHE_TTL_DAYS", "10"))

# data_type tags
METRICS = "kw_metrics"
SERP = "serp_intel"


def normalize_keyword(keyword: str) -> str:
    """Lowercase + collapse whitespace so cache keys are stable across callers."""
    return " ".join(str(keyword).lower().split())


def _cache_key(data_type: str, location_code: int, language_code: str, keyword: str) -> str:
    return f"{data_type}:{location_code}:{language_code}:{normalize_keyword(keyword)}"


def get_many(
    data_type: str,
    keywords: list[str],
    *,
    location_code: int,
    language_code: str,
    db_path=None,
) -> dict[str, Any]:
    """Return {normalized_keyword: payload} for the non-expired cached keywords."""
    if not keywords:
        return {}
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    out: dict[str, Any] = {}
    with get_conn(path) as conn:
        for keyword in keywords:
            norm = normalize_keyword(keyword)
            if not norm or norm in out:
                continue
            key = _cache_key(data_type, location_code, language_code, keyword)
            row = conn.execute(
                "SELECT payload_json FROM keyword_data_cache "
                "WHERE cache_key = ? AND expires_at > ?",
                (key, now),
            ).fetchone()
            if row:
                out[norm] = json.loads(row["payload_json"])
    return out


def set_many(
    data_type: str,
    payload_by_keyword: dict[str, Any],
    *,
    location_code: int,
    language_code: str,
    ttl_days: int,
    db_path=None,
) -> None:
    """Upsert cache entries for the given keywords with a TTL."""
    if not payload_by_keyword:
        return
    now = datetime.now(UTC)
    created = now.isoformat()
    expires = (now + timedelta(days=ttl_days)).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        for keyword, payload in payload_by_keyword.items():
            if not normalize_keyword(keyword):
                continue
            key = _cache_key(data_type, location_code, language_code, keyword)
            conn.execute(
                """INSERT INTO keyword_data_cache
                       (cache_key, data_type, payload_json, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(cache_key) DO UPDATE SET
                       payload_json = excluded.payload_json,
                       created_at = excluded.created_at,
                       expires_at = excluded.expires_at""",
                (key, data_type, json.dumps(payload, ensure_ascii=False), created, expires),
            )
