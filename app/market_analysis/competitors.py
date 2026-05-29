"""Competitor signals for the market analysis.

Free-mode sources:
  - manual: domains entered by the merchant in the Settings page
  - gsc: domains the merchant's site already competes with for top queries
         (derived from query overlap — heuristic only)

Paid-mode source (future): the SERP API of DataForSEO will return the real
top-10 competitors per keyword.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.market_analysis.providers.types import CompetitorSignal
from app.paths import data_dir

logger = logging.getLogger(__name__)

_DATA_DIR = data_dir()


# ── Persistence ──────────────────────────────────────────────────────────────


def _competitors_path(shop: str) -> Path:
    return _DATA_DIR / shop / "market_analysis_competitors.json"


def load_competitors(shop: str) -> list[dict[str, Any]]:
    """Load merchant-entered competitors, or [] if none."""
    path = _competitors_path(shop)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict)]
        return []
    except (OSError, json.JSONDecodeError):
        return []


def save_competitors(shop: str, competitors: list[dict[str, Any]]) -> None:
    """Persist a deduplicated list of competitor entries to disk."""
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        cleaned = _normalise_competitors(competitors)
        _competitors_path(shop).write_text(
            json.dumps(cleaned, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Failed to persist competitors for %s: %s", shop, exc)


def _normalise_competitors(competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in competitors:
        if not isinstance(raw, dict):
            continue
        domain = _extract_domain(str(raw.get("domain", raw.get("url", "")))).lower()
        if not domain or domain in seen:
            continue
        seen.add(domain)
        out.append({
            "domain": domain,
            "url": str(raw.get("url", "")).strip() or None,
            "note": str(raw.get("note", "")).strip() or None,
        })
    return out


def _extract_domain(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


# ── Signal building ──────────────────────────────────────────────────────────


def build_competitor_signals(
    shop: str,
    *,
    keywords: list[str] | None = None,
) -> list[CompetitorSignal]:
    """Build a list of CompetitorSignal entries from free sources.

    keywords: optional list of target keywords used to populate
              `matched_keyword` with a best-effort guess (first keyword).
    """
    manual = load_competitors(shop)
    matched_kw = (keywords or [""])[0] if keywords else ""

    signals: list[CompetitorSignal] = []
    for entry in manual:
        domain = entry.get("domain", "")
        if not domain:
            continue
        sig: CompetitorSignal = {
            "domain": domain,
            "url": entry.get("url"),
            "matched_keyword": matched_kw,
            "detected_from": "manual",
            "content_angle": entry.get("note") or "",
            "estimated_strength": 50,  # neutral — we have no real metric in free mode
            "confidence": "medium",
        }
        signals.append(sig)
    return signals
