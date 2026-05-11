"""Signal aggregator — combines all sources and deduplicates results."""

from __future__ import annotations

import logging

from app.niche.signals.models import SignalKeyword

logger = logging.getLogger(__name__)

_ALL_SOURCES = ("google_suggest", "trends", "reddit")


def fetch_all_signals(
    seed_keywords: list[str],
    *,
    sources: list[str] | None = None,
    geo: str = "FR",
    lang: str = "fr",
    reddit_subreddits: list[str] | None = None,
) -> list[SignalKeyword]:
    """Fetch keyword signals from all configured sources.

    Sources run independently — a failure in one does not abort others.

    Args:
        seed_keywords: Base keywords to expand (e.g. cluster names or GSC queries).
        sources: Subset of sources to run. Defaults to all: google_suggest, trends, reddit.
                 Pass ["google_suggest"] to skip trends (avoids pytrends import).
        geo: Country code for regional signals (used by Trends and Suggest).
        lang: Language code for Suggest.
        reddit_subreddits: Override default subreddit list.

    Returns:
        Deduplicated list of SignalKeyword, sorted by relevance_score descending.
        Seeds themselves are excluded from results.
    """
    active = set(sources) if sources else set(_ALL_SOURCES)
    seed_set = {s.strip().lower() for s in seed_keywords}
    all_keywords: list[SignalKeyword] = []

    if "google_suggest" in active:
        try:
            from app.niche.signals.google_suggest import fetch_suggestions_bulk

            suggestions = fetch_suggestions_bulk(seed_keywords, lang=lang, country=geo)
            all_keywords.extend(suggestions)
            logger.info("Google Suggest: %d keywords fetched", len(suggestions))
        except Exception as exc:
            logger.warning("Google Suggest source failed: %s", exc)

    if "trends" in active:
        try:
            from app.niche.signals.trends import fetch_related_queries

            trend_kws = fetch_related_queries(seed_keywords, geo=geo)
            all_keywords.extend(trend_kws)
            logger.info("Google Trends: %d keywords fetched", len(trend_kws))
        except Exception as exc:
            logger.warning("Google Trends source failed: %s", exc)

    if "reddit" in active:
        try:
            from app.niche.signals.reddit import fetch_reddit_keywords

            reddit_kws = []
            for seed in seed_keywords:
                reddit_kws.extend(
                    fetch_reddit_keywords(seed, subreddits=reddit_subreddits)
                )
            all_keywords.extend(reddit_kws)
            logger.info("Reddit: %d keywords fetched", len(reddit_kws))
        except Exception as exc:
            logger.warning("Reddit source failed: %s", exc)

    # Deduplicate: keep highest relevance_score per keyword
    deduped: dict[str, SignalKeyword] = {}
    for kw in all_keywords:
        if kw.keyword in seed_set:
            continue  # exclude the seeds themselves
        existing = deduped.get(kw.keyword)
        if existing is None or kw.relevance_score > existing.relevance_score:
            deduped[kw.keyword] = kw

    return sorted(deduped.values(), key=lambda k: k.relevance_score, reverse=True)
