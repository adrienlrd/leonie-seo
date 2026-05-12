"""Google Trends fetcher via pytrends."""

from __future__ import annotations

import logging

from app.niche.signals.models import SignalKeyword

logger = logging.getLogger(__name__)


def _import_pytrends():
    try:
        from pytrends.request import TrendReq

        return TrendReq
    except ImportError as exc:
        raise ImportError(
            "pytrends is required for Trends signals. Install with: pip install 'leonie-seo[niche]'"
        ) from exc


def fetch_related_queries(
    keywords: list[str],
    *,
    geo: str = "FR",
    timeframe: str = "today 12-m",
    lang: str = "fr-FR",
) -> list[SignalKeyword]:
    """Fetch top and rising related queries from Google Trends.

    Args:
        keywords: Seed keywords (max 5 per Trends API call).
        geo: Country code for regional data.
        timeframe: Trends timeframe string.
        lang: Interface language.

    Returns:
        List of SignalKeyword from "top" and "rising" buckets.
        Returns [] on rate-limit or error (non-blocking).
    """
    if not keywords:
        return []

    try:
        TrendReq = _import_pytrends()
    except ImportError as exc:
        logger.warning("Google Trends unavailable: %s", exc)
        return []

    try:
        pytrends = TrendReq(hl=lang, tz=60, timeout=(10, 25))
        pytrends.build_payload(keywords[:5], timeframe=timeframe, geo=geo)
        related = pytrends.related_queries()
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Google Trends error: %s", exc)
        return []

    results: list[SignalKeyword] = []
    seen: set[str] = set()

    for seed in keywords[:5]:
        seed_data = related.get(seed, {})

        # Top queries — volume is absolute (0-100 index)
        top_df = seed_data.get("top")
        if top_df is not None and not top_df.empty:
            for _, row in top_df.iterrows():
                kw = str(row.get("query", "")).strip().lower()
                vol = int(row.get("value", 0))
                if kw and kw not in seen:
                    seen.add(kw)
                    results.append(
                        SignalKeyword(
                            keyword=kw,
                            source="trends_top",
                            volume_estimate=vol,
                            context=f"geo={geo} timeframe={timeframe}",
                            relevance_score=round(vol / 100.0, 3),
                        )
                    )

        # Rising queries — volume is relative growth (can be > 100, e.g. "Breakout")
        rising_df = seed_data.get("rising")
        if rising_df is not None and not rising_df.empty:
            for _, row in rising_df.iterrows():
                kw = str(row.get("query", "")).strip().lower()
                raw_val = row.get("value", 0)
                # "Breakout" strings map to 101 in pytrends; cap to 100 for scoring
                vol = min(int(raw_val) if isinstance(raw_val, (int, float)) else 0, 100)
                if kw and kw not in seen:
                    seen.add(kw)
                    results.append(
                        SignalKeyword(
                            keyword=kw,
                            source="trends_rising",
                            volume_estimate=vol,
                            context=f"geo={geo} rising",
                            relevance_score=round(min(vol / 100.0, 1.0), 3),
                        )
                    )

    return results
