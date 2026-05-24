"""Normalised data structures shared by all providers.

Every provider returns or mutates `KeywordSignal` dicts so the engine and
frontend only ever speak a single vocabulary. Fields that require a paid
source (search_volume, cpc, ads_competition) stay `None` in free mode —
they MUST NOT be invented.
"""

from __future__ import annotations

from typing import Literal, TypedDict

KeywordSource = Literal["gsc", "ga4", "trends", "shopify", "llm_estimated", "dataforseo", "google_ads"]
IntentType = Literal["informational", "commercial", "transactional", "navigational", "unknown"]
Confidence = Literal["high", "medium", "low"]
DifficultySource = Literal["free_estimated", "dataforseo", "google_ads"]


class KeywordSignal(TypedDict, total=False):
    """Normalised representation of a single keyword's signals.

    Free fields (always populated when available):
      keyword, source, intent, impressions, clicks, avg_position, trend_score,
      difficulty_score, difficulty_source, confidence, notes

    Paid fields (None in free mode — populated only by paid providers):
      search_volume, cpc, ads_competition
    """

    keyword: str
    source: KeywordSource
    intent: IntentType
    impressions: int | None
    clicks: int | None
    avg_position: float | None
    trend_score: int | None
    search_volume: int | None
    cpc: float | None
    ads_competition: float | None
    difficulty_score: int
    difficulty_source: DifficultySource
    confidence: Confidence
    notes: list[str]


CompetitorDetectionSource = Literal["manual", "gsc", "merchant_input", "paid_provider"]


class CompetitorSignal(TypedDict, total=False):
    """Normalised representation of a single competitor signal."""

    domain: str
    url: str | None
    matched_keyword: str
    detected_from: CompetitorDetectionSource
    content_angle: str
    estimated_strength: int
    confidence: Confidence


def make_empty_signal(keyword: str, source: KeywordSource = "llm_estimated") -> KeywordSignal:
    """Return a KeywordSignal with only free fields populated to safe defaults."""
    return {
        "keyword": keyword,
        "source": source,
        "intent": "unknown",
        "impressions": None,
        "clicks": None,
        "avg_position": None,
        "trend_score": None,
        "search_volume": None,
        "cpc": None,
        "ads_competition": None,
        "difficulty_score": 50,
        "difficulty_source": "free_estimated",
        "confidence": "low",
        "notes": [],
    }
