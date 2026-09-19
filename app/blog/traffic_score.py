"""Expected-traffic scoring for blog ideas.

Ranks ideas by the clicks per day an article targeting their keyword can
realistically bring, so the daily publisher writes the one that matters instead
of whichever angle happened to come first.

Source priority is deliberate: Search Console first (what this shop actually
gets), then DataForSEO volume, then the coarse demand bucket. Every score
carries the source it came from and a confidence level — an estimate built on a
bucket must never look like a measurement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.api.deps import _RAW_DIR

# Organic CTR by position. Mid-range of the public studies (Advanced Web
# Ranking, Sistrix); exact values differ per niche, the shape does not.
_CTR_BY_POSITION: dict[int, float] = {
    1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.07,
    6: 0.05, 7: 0.04, 8: 0.035, 9: 0.03, 10: 0.025,
}
_CTR_BEYOND_PAGE_ONE = 0.01

# Where a fresh article on an established domain realistically lands. Anything
# more optimistic turns the ranking into wishful thinking.
_NEW_ARTICLE_POSITION = 8

# Floor of each demand_score bucket (see engine._volume_bucket). The floor, not
# the midpoint: a guess should under-promise.
_BUCKET_TO_VOLUME: dict[int, int] = {100: 100000, 90: 10000, 75: 1000, 55: 100, 30: 10, 10: 1}

_DEFAULT_GSC_WINDOW_DAYS = 28
_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2, "none": 3}


def _normalize(query: str) -> str:
    return " ".join(str(query or "").split()).casefold()


def _ctr_at(position: float) -> float:
    if position < 1:
        return _CTR_BY_POSITION[1]
    if position > 10:
        return _CTR_BEYOND_PAGE_ONE
    return _CTR_BY_POSITION[round(position)]


def load_gsc_index(shop: str, *, raw_dir: Path | None = None) -> tuple[dict[str, dict], int]:
    """Return ``({normalized query: row}, window_days)`` from the newest export.

    ``_load_gsc_query_rows`` drops the window length, and clicks per *day* is the
    whole point here, so this reads the raw export instead.
    """
    shop_dir = (raw_dir or _RAW_DIR) / shop
    if not shop_dir.exists():
        return {}, _DEFAULT_GSC_WINDOW_DAYS
    for path in sorted(shop_dir.glob("gsc_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data if isinstance(data, list) else data.get("rows") or []
        window_days = int((data if isinstance(data, dict) else {}).get("days") or 0)
        index: dict[str, dict] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            query = _normalize(row.get("query") or "")
            if not query:
                continue
            # query+page rows repeat a query per URL — sum the query's total.
            entry = index.setdefault(query, {"impressions": 0, "clicks": 0, "position": 0.0})
            entry["impressions"] += int(row.get("impressions") or 0)
            entry["clicks"] += int(row.get("clicks") or 0)
            entry["position"] = max(entry["position"], float(row.get("position") or 0))
        return index, window_days or _DEFAULT_GSC_WINDOW_DAYS
    return {}, _DEFAULT_GSC_WINDOW_DAYS


def _keyword_row(query: str, product: dict[str, Any]) -> dict[str, Any] | None:
    target = _normalize(query)
    for keyword in product.get("seo_keywords") or []:
        if isinstance(keyword, dict) and _normalize(keyword.get("query")) == target:
            return keyword
    return None


def score_idea(
    idea: dict[str, Any],
    *,
    product: dict[str, Any] | None,
    gsc_index: dict[str, dict],
    window_days: int = _DEFAULT_GSC_WINDOW_DAYS,
) -> dict[str, Any]:
    """Estimate the clicks per day an article on this idea could bring."""
    query = str(idea.get("target_keyword") or "").strip()
    if not query:
        return _empty_score("no_keyword")

    gsc_row = gsc_index.get(_normalize(query))
    if gsc_row and gsc_row["impressions"] > 0:
        demand_per_day = gsc_row["impressions"] / max(1, window_days)
        current = gsc_row["position"] or _NEW_ARTICLE_POSITION
        # The domain already surfaces on this query, so the article can aim at
        # least as high as the page that ranks today.
        position = min(float(current), float(_NEW_ARTICLE_POSITION))
        return _score(demand_per_day, position, "gsc", "high")

    keyword = _keyword_row(query, product or {})
    if keyword:
        volume = keyword.get("search_volume")
        if volume is not None and int(volume) > 0:
            return _score(int(volume) / 30, _NEW_ARTICLE_POSITION, "dataforseo", "medium")
        bucket = int(keyword.get("demand_score") or 0)
        if bucket:
            volume = _BUCKET_TO_VOLUME.get(bucket, 1)
            return _score(volume / 30, _NEW_ARTICLE_POSITION, "demand_score", "low")

    return _empty_score("no_demand_data")


def _score(demand_per_day: float, position: float, source: str, confidence: str) -> dict[str, Any]:
    ctr = _ctr_at(position)
    return {
        "expected_clicks_per_day": round(demand_per_day * ctr, 3),
        "demand_per_day": round(demand_per_day, 2),
        "assumed_position": round(position, 1),
        "ctr": ctr,
        "traffic_source": source,
        "confidence": confidence,
    }


def _empty_score(reason: str) -> dict[str, Any]:
    return {
        "expected_clicks_per_day": 0.0,
        "demand_per_day": 0.0,
        "assumed_position": None,
        "ctr": 0.0,
        "traffic_source": reason,
        "confidence": "none",
    }


def rank_blog_ideas(
    ideas: list[dict[str, Any]],
    *,
    products_by_id: dict[str, dict[str, Any]],
    gsc_index: dict[str, dict],
    window_days: int = _DEFAULT_GSC_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Return the ideas scored and sorted, best expected traffic first.

    Ties keep their incoming order, which is the angle priority
    (`build_blog_idea_suggestions`) — a sensible fallback when no idea has data.
    """
    scored: list[dict[str, Any]] = []
    for rank, idea in enumerate(ideas):
        product = products_by_id.get(str(idea.get("product_id") or ""))
        score = score_idea(idea, product=product, gsc_index=gsc_index, window_days=window_days)
        scored.append({**idea, "traffic_score": score, "_rank": rank})
    scored.sort(
        key=lambda item: (
            -item["traffic_score"]["expected_clicks_per_day"],
            _CONFIDENCE_RANK.get(item["traffic_score"]["confidence"], 3),
            item["_rank"],
        )
    )
    for item in scored:
        item.pop("_rank", None)
    return scored
