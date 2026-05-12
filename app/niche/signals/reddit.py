"""Reddit signal fetcher — uses the public JSON API (no PRAW required)."""

from __future__ import annotations

import logging
import re

import requests

from app.niche.signals.models import SignalKeyword

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.reddit.com/search.json"
_SUBREDDIT_URL = "https://www.reddit.com/r/{subreddit}/search.json"
_TIMEOUT = 15
# Reddit requires a descriptive User-Agent (bot-like generic agents return 429)
_USER_AGENT = "leonie-seo/0.1 (research; contact: contact@leoniedelacroix.com)"

# French and international pet subreddits
_DEFAULT_SUBREDDITS = ["chiens", "chat_fr", "dogs", "cats", "petadvice"]

_MIN_UPVOTES = 5  # ignore posts with very few upvotes


def _extract_keywords_from_title(title: str) -> list[str]:
    """Extract meaningful noun phrases from a Reddit post title."""
    # Simple heuristic: find 2-3 word sequences after question markers or key verbs
    title = title.lower()
    # Remove common Reddit noise
    title = re.sub(r"\[.*?\]|\(.*?\)", "", title)
    words = re.findall(r"[a-záàâéèêëîïôùûüç]{3,}", title)
    # Return bigrams as keyword candidates
    bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    return bigrams[:3]  # max 3 candidates per title


def fetch_reddit_keywords(
    query: str,
    *,
    subreddits: list[str] | None = None,
    limit: int = 25,
    session: requests.Session | None = None,
) -> list[SignalKeyword]:
    """Search Reddit for posts about a topic and extract keyword signals.

    Args:
        query: Search query (e.g. "harnais chien").
        subreddits: List of subreddits to search (defaults to pet subreddits).
        limit: Maximum posts per subreddit.
        session: Optional requests.Session for mocking in tests.

    Returns:
        List of SignalKeyword extracted from post titles.
        Returns [] on any network or parse error (non-blocking).
    """
    targets = subreddits or _DEFAULT_SUBREDDITS
    requester = session or requests
    results: list[SignalKeyword] = []
    seen: set[str] = set()

    for subreddit in targets:
        try:
            resp = requester.get(
                _SUBREDDIT_URL.format(subreddit=subreddit),
                params={"q": query, "sort": "top", "t": "year", "limit": limit},
                headers={"User-Agent": _USER_AGENT},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning("Reddit error for subreddit r/%s query '%s': %s", subreddit, query, exc)
            continue

        posts = data.get("data", {}).get("children", [])
        max_score = max((p["data"].get("score", 0) for p in posts), default=1) or 1

        for post in posts:
            post_data = post.get("data", {})
            score = post_data.get("score", 0)
            if score < _MIN_UPVOTES:
                continue

            title = post_data.get("title", "")
            relevance = round(score / max_score, 3)

            for kw in _extract_keywords_from_title(title):
                if kw not in seen and len(kw) > 4:
                    seen.add(kw)
                    results.append(
                        SignalKeyword(
                            keyword=kw,
                            source="reddit",
                            volume_estimate=None,
                            context=f"r/{subreddit}",
                            relevance_score=relevance,
                        )
                    )

    return sorted(results, key=lambda k: k.relevance_score, reverse=True)
