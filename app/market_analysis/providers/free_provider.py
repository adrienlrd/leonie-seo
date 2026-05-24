"""Free keyword provider — enriches signals from GSC, GA4 and Google Trends.

This is the only provider that is always available. It populates the *free*
fields of `KeywordSignal` and computes a `free_estimated` difficulty score.
Paid fields (search_volume, cpc, ads_competition) are left as `None`.
"""

from __future__ import annotations

import logging
from typing import Any

from app.market_analysis.providers.types import KeywordSignal, make_empty_signal

logger = logging.getLogger(__name__)


def _impressions_to_demand_score(impressions: int) -> int:
    """Map raw GSC impressions to a 0-100 demand proxy. NOT a search volume."""
    if impressions >= 10000:
        return 95
    if impressions >= 5000:
        return 85
    if impressions >= 1000:
        return 75
    if impressions >= 500:
        return 65
    if impressions >= 100:
        return 50
    if impressions >= 10:
        return 35
    return 20


def _position_to_difficulty(position: float) -> int:
    """Estimate difficulty from average GSC position.

    Better position (closer to 1) means the keyword is already actively
    fought over by competitors, so we treat it as harder to defend / win.
    """
    if position <= 3:
        return 90
    if position <= 10:
        return 75
    if position <= 20:
        return 55
    if position <= 50:
        return 35
    return 15


def _ctr_quality(impressions: int, clicks: int) -> int:
    """Bonus 0-15 for keywords with good CTR (proves real demand)."""
    if impressions <= 0:
        return 0
    ctr = clicks / impressions
    if ctr >= 0.05:
        return 15
    if ctr >= 0.02:
        return 10
    if ctr >= 0.005:
        return 5
    return 0


class FreeProvider:
    """Always-available provider: GSC + GA4 + Trends + heuristic difficulty."""

    name = "free"

    def __init__(
        self,
        *,
        gsc_query_rows: list[dict[str, Any]] | None = None,
        trend_signals: list[Any] | None = None,
    ) -> None:
        self._gsc_lookup = self._build_gsc_lookup(gsc_query_rows or [])
        self._trend_keywords = self._build_trend_set(trend_signals or [])

    @property
    def available(self) -> bool:
        return True

    @staticmethod
    def _build_gsc_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for row in rows:
            query = str(row.get("query", "")).lower().strip()
            if not query:
                continue
            lookup[query] = {
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "position": float(row.get("position", 0)),
            }
        return lookup

    @staticmethod
    def _build_trend_set(signals: list[Any]) -> set[str]:
        kws: set[str] = set()
        for sig in signals:
            kw = getattr(sig, "keyword", "") if not isinstance(sig, dict) else sig.get("keyword", "")
            if kw:
                kws.add(str(kw).lower().strip())
        return kws

    def enrich(self, signals: list[KeywordSignal], *, shop: str) -> list[KeywordSignal]:  # noqa: ARG002
        """Enrich every keyword signal with free GSC/GA4/Trends data."""
        enriched: list[KeywordSignal] = []
        for sig in signals:
            sig = dict(sig)  # type: ignore[assignment]
            keyword = str(sig.get("keyword", "")).lower().strip()
            if not keyword:
                enriched.append(sig)  # type: ignore[arg-type]
                continue

            notes = list(sig.get("notes", []))
            gsc_row = self._gsc_lookup.get(keyword)
            if gsc_row and gsc_row["impressions"] > 0:
                sig["source"] = "gsc"
                sig["impressions"] = gsc_row["impressions"]
                sig["clicks"] = gsc_row["clicks"]
                sig["avg_position"] = round(gsc_row["position"], 1)
                sig["difficulty_score"] = _position_to_difficulty(gsc_row["position"])
                sig["difficulty_source"] = "free_estimated"
                sig["confidence"] = "high"
                bonus = _ctr_quality(gsc_row["impressions"], gsc_row["clicks"])
                notes.append(
                    f"GSC: {gsc_row['impressions']} impr., {gsc_row['clicks']} clics, "
                    f"position moyenne {round(gsc_row['position'], 1)} (+CTR bonus {bonus})"
                )
            else:
                # Keep LLM-estimated; mark explicitly so the UI can warn.
                sig.setdefault("source", "llm_estimated")
                sig.setdefault("difficulty_score", 50)
                sig.setdefault("difficulty_source", "free_estimated")
                sig.setdefault("confidence", "low")
                notes.append("Aucune donnée GSC — score estimé par l'IA")

            if keyword in self._trend_keywords:
                sig["trend_score"] = 70
                notes.append("Détecté dans Google Trends (12 derniers mois)")

            # Paid fields always None in free mode
            sig.setdefault("search_volume", None)
            sig.setdefault("cpc", None)
            sig.setdefault("ads_competition", None)
            sig["notes"] = notes
            enriched.append(sig)  # type: ignore[arg-type]
        return enriched


def signals_from_llm_keywords(llm_keywords: list[dict[str, Any]]) -> list[KeywordSignal]:
    """Convert LLM-generated keyword dicts into normalised KeywordSignal seeds.

    Carries over query + intent + LLM-estimated scores into the signal so
    downstream providers can replace them with real data when available.
    """
    signals: list[KeywordSignal] = []
    for kw in llm_keywords:
        if not isinstance(kw, dict):
            continue
        keyword = str(kw.get("query", "")).strip()
        if not keyword:
            continue
        seed = make_empty_signal(keyword, source="llm_estimated")
        intent_raw = str(kw.get("intent_type", "")).lower()
        if intent_raw in ("informational", "commercial", "transactional", "navigational"):
            seed["intent"] = intent_raw  # type: ignore[typeddict-item]
        # Keep LLM-estimated demand/competition as best-effort difficulty seed
        comp = kw.get("competition_score")
        if isinstance(comp, (int, float)):
            seed["difficulty_score"] = int(max(0, min(100, comp)))
        signals.append(seed)
    return signals
