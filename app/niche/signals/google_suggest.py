"""Google Autocomplete / Suggest fetcher."""

from __future__ import annotations

import logging
import time

import requests

from app.niche.signals.models import SignalKeyword

logger = logging.getLogger(__name__)

_SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
_REQUEST_DELAY = 0.5  # seconds between requests to avoid rate-limiting
_TIMEOUT = 10


def fetch_suggestions(
    seed: str,
    *,
    lang: str = "fr",
    country: str = "FR",
    session: requests.Session | None = None,
) -> list[SignalKeyword]:
    """Fetch Google autocomplete suggestions for a seed keyword.

    Args:
        seed: Base keyword (e.g. "harnais chien").
        lang: Language code for suggestions.
        country: Country code for regional results.
        session: Optional requests.Session for connection pooling / mocking.

    Returns:
        List of SignalKeyword, scored by position (first = highest relevance).
        Returns [] on any network or parse error (non-blocking).
    """
    requester = session or requests
    try:
        resp = requester.get(
            _SUGGEST_URL,
            params={"client": "firefox", "q": seed, "hl": lang, "gl": country},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Response format: [seed, [suggestion1, suggestion2, ...], ...]
        suggestions: list[str] = data[1] if len(data) > 1 else []
    except Exception as exc:
        logger.warning("Google Suggest error for '%s': %s", seed, exc)
        return []

    results = []
    n = max(len(suggestions), 1)
    for i, suggestion in enumerate(suggestions):
        if suggestion.lower() == seed.lower():
            continue
        score = 1.0 - (i / n)  # position-based: first suggestion = highest score
        results.append(
            SignalKeyword(
                keyword=suggestion,
                source="google_suggest",
                volume_estimate=None,
                context=f"autocomplete position {i + 1}",
                relevance_score=score,
            )
        )

    return results


def fetch_suggestions_bulk(
    seeds: list[str],
    *,
    lang: str = "fr",
    country: str = "FR",
    delay: float = _REQUEST_DELAY,
) -> list[SignalKeyword]:
    """Fetch suggestions for multiple seeds with polite rate-limiting.

    Args:
        seeds: List of seed keywords.
        lang: Language code.
        country: Country code.
        delay: Seconds to wait between requests.

    Returns:
        Deduplicated list of SignalKeyword across all seeds.
    """
    seen: set[str] = set()
    results: list[SignalKeyword] = []
    session = requests.Session()

    for i, seed in enumerate(seeds):
        if i > 0:
            time.sleep(delay)
        for kw in fetch_suggestions(seed, lang=lang, country=country, session=session):
            if kw.keyword not in seen:
                seen.add(kw.keyword)
                results.append(kw)

    return results
