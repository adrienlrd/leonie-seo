"""DataForSEO provider — real implementation of the Keywords Data API.

Activation:
    DATAFORSEO_LOGIN=<email>
    DATAFORSEO_PASSWORD=<api password>
    DATAFORSEO_ENABLED=true

If any of these is missing or `DATAFORSEO_ENABLED!=true`, the provider
reports `available = False` and the engine silently skips it.

Endpoint used:
    POST https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live

Cost: roughly $0.0005–0.001 per keyword. The engine deduplicates keywords
before calling the provider to minimise cost.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.market_analysis.providers.types import KeywordSignal

logger = logging.getLogger(__name__)

_API_URL = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
_DEFAULT_LOCATION_CODE = 2250  # France
_DEFAULT_LANGUAGE_CODE = "fr"
_HTTP_TIMEOUT = 30.0


def _to_difficulty(competition: float | None) -> int:
    """Map Google Ads competition (0.0–1.0) to a 0-100 difficulty score."""
    if competition is None:
        return 50
    competition = max(0.0, min(1.0, float(competition)))
    return int(round(competition * 100))


def _to_demand_bucket(volume: int | None) -> int:
    """Map raw monthly search volume to a 0-100 demand bucket."""
    if not volume or volume <= 0:
        return 5
    if volume >= 100000:
        return 100
    if volume >= 10000:
        return 90
    if volume >= 1000:
        return 75
    if volume >= 100:
        return 55
    if volume >= 10:
        return 30
    return 15


class DataForSEOProvider:
    """Real DataForSEO Keywords Data provider — env-gated, fails silently."""

    name = "dataforseo"

    def __init__(
        self,
        *,
        location_code: int = _DEFAULT_LOCATION_CODE,
        language_code: str = _DEFAULT_LANGUAGE_CODE,
    ) -> None:
        self._login = os.getenv("DATAFORSEO_LOGIN", "").strip()
        self._password = os.getenv("DATAFORSEO_PASSWORD", "").strip()
        self._enabled = os.getenv("DATAFORSEO_ENABLED", "false").strip().lower() == "true"
        self._location_code = location_code
        self._language_code = language_code

    @property
    def available(self) -> bool:
        return bool(self._enabled and self._login and self._password)

    def enrich(self, signals: list[KeywordSignal], *, shop: str) -> list[KeywordSignal]:  # noqa: ARG002
        if not self.available or not signals:
            return signals
        keywords = sorted({str(s.get("keyword", "")).strip() for s in signals if s.get("keyword")})
        if not keywords:
            return signals

        try:
            volumes = self._fetch_search_volumes(keywords)
        except Exception as exc:  # remote-call failure must never crash analysis
            logger.warning("DataForSEO call failed: %s", exc)
            return signals

        # Apply enrichment — replace estimated difficulty with API data
        for sig in signals:
            kw = str(sig.get("keyword", "")).strip().lower()
            data = volumes.get(kw)
            if not data:
                continue
            sig["search_volume"] = data.get("search_volume")
            sig["cpc"] = data.get("cpc")
            sig["ads_competition"] = data.get("competition_index")
            sig["difficulty_score"] = _to_difficulty(data.get("competition_index"))
            sig["difficulty_source"] = "dataforseo"
            sig["source"] = "dataforseo"
            sig["confidence"] = "high"
            notes = list(sig.get("notes", []))
            vol = data.get("search_volume")
            cpc = data.get("cpc")
            notes.append(
                f"DataForSEO: volume {vol if vol is not None else '—'} /mois, "
                f"CPC {cpc if cpc is not None else '—'}€, "
                f"concurrence Ads {data.get('competition_index')}"
            )
            sig["notes"] = notes
        return signals

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _fetch_search_volumes(self, keywords: list[str]) -> dict[str, dict[str, Any]]:
        """Call the DataForSEO Keywords Data API and return {keyword_lower: row}."""
        import requests  # noqa: PLC0415

        payload = [
            {
                "keywords": keywords[:1000],  # DataForSEO hard cap per call
                "location_code": self._location_code,
                "language_code": self._language_code,
            }
        ]
        resp = requests.post(
            _API_URL,
            json=payload,
            auth=(self._login, self._password),
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        out: dict[str, dict[str, Any]] = {}
        for task in body.get("tasks", []) or []:
            for result in task.get("result", []) or []:
                kw = str(result.get("keyword", "")).strip().lower()
                if not kw:
                    continue
                out[kw] = {
                    "search_volume": result.get("search_volume"),
                    "cpc": result.get("cpc"),
                    "competition_index": result.get("competition_index"),
                }
        return out
