"""DataForSEO provider — Keywords Data, Keyword Difficulty, SERP, Keyword Ideas, Domain Competitors.

Activation (same credentials for all APIs):
    DATAFORSEO_LOGIN=<email>
    DATAFORSEO_PASSWORD=<api password>
    DATAFORSEO_ENABLED=true

APIs used:
    1. POST /v3/keywords_data/google_ads/search_volume/live  (OPT-IN, off by default)
       → real search volume, CPC, ads competition per keyword. ~10x the cost of the
         Labs endpoints and largely redundant with keyword_ideas (which already
         returns volume/CPC). Enable with DATAFORSEO_SEARCH_VOLUME_ENABLED=true.
    2. POST /v3/dataforseo_labs/google/bulk_keyword_difficulty/live
       → true SEO difficulty 0–100 per keyword
    3. POST /v3/serp/google/organic/live/advanced
       → real French SERP: top-10 competitors, featured snippet, PAA (~$0.003/kw)
    4. POST /v3/dataforseo_labs/google/keyword_ideas/live
       → new keyword suggestions with real metrics per product (~$0.0075/task)
    5. POST /v3/dataforseo_labs/google/competitors_domain/live
       → domains competing with the merchant's shop on Google (~$0.01/call)

If any credential is missing or DATAFORSEO_ENABLED!=true, the provider
reports available=False and the engine silently skips it.

All remote calls fail silently — analysis continues with free signals only.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.market_analysis import keyword_cache
from app.market_analysis.providers.types import CompetitorSignal, KeywordSignal

logger = logging.getLogger(__name__)

_VOLUME_URL = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
_DIFFICULTY_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/bulk_keyword_difficulty/live"
_SERP_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
_KEYWORD_IDEAS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
_DOMAIN_COMPETITORS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/competitors_domain/live"

_DEFAULT_LOCATION_CODE = 2250  # France
_DEFAULT_LANGUAGE_CODE = "fr"
_HTTP_TIMEOUT = 45.0
_SERP_TIMEOUT = 60.0
_SERP_MAX_KEYWORDS = 50  # cost cap per analysis run


def _to_difficulty(competition: float | None) -> int:
    """Map Google Ads competition (0.0–1.0) to a 0-100 difficulty score (fallback only)."""
    if competition is None:
        return 50
    return int(round(max(0.0, min(1.0, float(competition))) * 100))


def _to_demand_bucket(volume: int | None) -> int:
    """Map raw monthly search volume to a 0-100 demand bucket."""
    if not volume or volume <= 0:
        return 5
    if volume >= 100_000:
        return 100
    if volume >= 10_000:
        return 90
    if volume >= 1_000:
        return 75
    if volume >= 100:
        return 55
    if volume >= 10:
        return 30
    return 15


def _serp_strength(rank: int) -> int:
    """Estimate competitor strength (0–100) from SERP rank position."""
    return max(10, 100 - (rank - 1) * 7)


class DataForSEOProvider:
    """DataForSEO provider — env-gated, fails silently on any remote error."""

    name = "dataforseo"

    def __init__(
        self,
        *,
        location_code: int = _DEFAULT_LOCATION_CODE,
        language_code: str = _DEFAULT_LANGUAGE_CODE,
        cache_db_path=None,
    ) -> None:
        self._login = os.getenv("DATAFORSEO_LOGIN", "").strip()
        self._password = os.getenv("DATAFORSEO_PASSWORD", "").strip()
        self._enabled = os.getenv("DATAFORSEO_ENABLED", "false").strip().lower() == "true"
        # The Google Ads search-volume endpoint costs ~10x the Labs endpoints and is
        # largely redundant: keyword_ideas already returns volume/CPC for discovered
        # keywords. Off by default; enable only when exact Ads volume/CPC is needed.
        self._search_volume_enabled = (
            os.getenv("DATAFORSEO_SEARCH_VOLUME_ENABLED", "false").strip().lower() == "true"
        )
        self._location_code = location_code
        self._language_code = language_code
        self._cache_db_path = cache_db_path

    @property
    def available(self) -> bool:
        return bool(self._enabled and self._login and self._password)

    # ── Shared cache (fail-open: a cache error must never break enrichment) ────

    def _cache_get(self, data_type: str, keywords: list[str]) -> dict[str, Any]:
        try:
            return keyword_cache.get_many(
                data_type,
                keywords,
                location_code=self._location_code,
                language_code=self._language_code,
                db_path=self._cache_db_path,
            )
        except Exception as exc:  # pragma: no cover - cache is best-effort
            logger.debug("keyword cache read failed (non-fatal): %s", exc)
            return {}

    def _cache_set(self, data_type: str, payloads: dict[str, Any], ttl_days: int) -> None:
        if not payloads:
            return
        try:
            keyword_cache.set_many(
                data_type,
                payloads,
                location_code=self._location_code,
                language_code=self._language_code,
                ttl_days=ttl_days,
                db_path=self._cache_db_path,
            )
        except Exception as exc:  # pragma: no cover - cache is best-effort
            logger.debug("keyword cache write failed (non-fatal): %s", exc)

    # ── Public API used by the engine ────────────────────────────────────────

    def enrich(self, signals: list[KeywordSignal], *, shop: str) -> list[KeywordSignal]:  # noqa: ARG002
        """Enrich keyword signals with real volume, CPC, and SEO difficulty."""
        if not self.available or not signals:
            return signals
        keywords = sorted({str(s.get("keyword", "")).strip() for s in signals if s.get("keyword")})
        if not keywords:
            return signals

        # Shared cache first; only call the paid API for keywords not seen before
        # (by any shop). The first shop in a niche pays, later shops read the cache.
        metrics = self._cache_get(keyword_cache.METRICS, keywords)
        misses = [k for k in keywords if keyword_cache.normalize_keyword(k) not in metrics]

        if misses:
            volumes: dict[str, dict[str, Any]] = {}
            difficulties: dict[str, int] = {}
            vol_ok = diff_ok = False
            # Skip the costly Google Ads search-volume call unless explicitly enabled —
            # keyword_ideas already carries volume/CPC for the keywords that matter.
            if self._search_volume_enabled:
                try:
                    volumes = self._fetch_search_volumes(misses)
                    vol_ok = True
                except Exception as exc:
                    logger.warning("DataForSEO search volume call failed: %s", exc)
            try:
                difficulties = self._fetch_keyword_difficulty(misses)
                diff_ok = True
            except Exception as exc:
                logger.warning("DataForSEO keyword difficulty call failed: %s", exc)

            # Only cache when at least one call succeeded, so transient failures are
            # not frozen as "no data". A genuine no-data result IS cached (None values)
            # to avoid re-querying obscure terms.
            if vol_ok or diff_ok:
                fresh: dict[str, dict[str, Any]] = {}
                for kw in misses:
                    norm = keyword_cache.normalize_keyword(kw)
                    vol_data = volumes.get(norm) or {}
                    fresh[norm] = {
                        "search_volume": vol_data.get("search_volume"),
                        "cpc": vol_data.get("cpc"),
                        "competition_index": vol_data.get("competition_index"),
                        "difficulty": difficulties.get(norm),
                    }
                self._cache_set(keyword_cache.METRICS, fresh, keyword_cache.METRICS_TTL_DAYS)
                metrics = {**metrics, **fresh}

        for sig in signals:
            norm = keyword_cache.normalize_keyword(str(sig.get("keyword", "")))
            payload = metrics.get(norm)
            if not payload:
                continue
            vol = payload.get("search_volume")
            cpc = payload.get("cpc")
            comp = payload.get("competition_index")
            difficulty = payload.get("difficulty")
            has_volume = vol is not None or cpc is not None or comp is not None
            if not (has_volume or difficulty is not None):
                continue
            sig["source"] = "dataforseo"
            sig["confidence"] = "high"
            notes = list(sig.get("notes", []))
            if has_volume:
                sig["search_volume"] = vol
                sig["cpc"] = cpc
                sig["ads_competition"] = comp
                if vol is not None:
                    sig["difficulty_score"] = _to_demand_bucket(vol)
                notes.append(
                    f"DataForSEO: {vol if vol is not None else '—'} rech./mois, "
                    f"CPC {cpc if cpc is not None else '—'}€, "
                    f"concurrence Ads {comp}"
                )
                sig["notes"] = notes
            # Real SEO difficulty overrides ads competition mapping
            if difficulty is not None:
                sig["difficulty_score"] = difficulty
                sig["difficulty_source"] = "dataforseo"

        return signals

    def fetch_serp_competitors(self, keywords: list[str]) -> list[CompetitorSignal]:
        """Fetch real French SERP for top keywords and return competitor signals.

        Capped at _SERP_MAX_KEYWORDS per analysis run to control cost.
        Returns [] on any error — never raises.
        """
        if not self.available or not keywords:
            return []
        capped = list(dict.fromkeys(keywords))[:_SERP_MAX_KEYWORDS]
        try:
            serp_data = self._fetch_serp(capped)
        except Exception as exc:
            logger.warning("DataForSEO SERP call failed: %s", exc)
            return []
        return _parse_serp_competitors(serp_data)

    def fetch_serp_intelligence(self, keywords: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch SERP signals usable to inform LLM content generation.

        Returns {keyword_lower: {"paa": list[str], "top_competitors":
        list[{domain, title, url, rank}], "featured_snippet": str | None}}.
        Capped at _SERP_MAX_KEYWORDS per run. Returns {} if unavailable or on error.

        Unlike fetch_serp_competitors (which deduplicates to a domain-level
        competitor list), this keeps the People-Also-Ask questions and per-keyword
        top organic titles so the engine can feed them into the content prompt.
        """
        if not self.available or not keywords:
            return {}
        capped = list(dict.fromkeys(keywords))[:_SERP_MAX_KEYWORDS]

        # Shared cache (short TTL — SERP/PAA move faster than volume/difficulty).
        cached = self._cache_get(keyword_cache.SERP, capped)
        misses = [k for k in capped if keyword_cache.normalize_keyword(k) not in cached]
        if not misses:
            return cached

        try:
            serp_data = self._fetch_serp(misses)
        except Exception as exc:
            logger.warning("DataForSEO SERP intelligence call failed: %s", exc)
            return cached
        parsed = _parse_serp_intelligence(serp_data)
        fresh = {keyword_cache.normalize_keyword(k): v for k, v in parsed.items()}
        self._cache_set(keyword_cache.SERP, fresh, keyword_cache.SERP_TTL_DAYS)
        return {**cached, **fresh}

    # ── Internal HTTP calls ──────────────────────────────────────────────────

    def _fetch_search_volumes(self, keywords: list[str]) -> dict[str, dict[str, Any]]:
        """POST to Keywords Data API. Returns {keyword_lower: {search_volume, cpc, competition_index}}."""
        import requests  # noqa: PLC0415

        payload = [{
            "keywords": keywords[:1000],
            "location_code": self._location_code,
            "language_code": self._language_code,
        }]
        resp = requests.post(
            _VOLUME_URL,
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
                if kw:
                    out[kw] = {
                        "search_volume": result.get("search_volume"),
                        "cpc": result.get("cpc"),
                        "competition_index": result.get("competition_index"),
                    }
        return out

    def _fetch_keyword_difficulty(self, keywords: list[str]) -> dict[str, int]:
        """POST to DataForSEO Labs Bulk Keyword Difficulty. Returns {keyword_lower: difficulty_0_100}."""
        import requests  # noqa: PLC0415

        payload = [{
            "keywords": keywords[:1000],
            "location_code": self._location_code,
            "language_code": self._language_code,
        }]
        resp = requests.post(
            _DIFFICULTY_URL,
            json=payload,
            auth=(self._login, self._password),
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        out: dict[str, int] = {}
        for task in body.get("tasks", []) or []:
            for result in task.get("result", []) or []:
                kw = str(result.get("keyword", "")).strip().lower()
                difficulty = result.get("keyword_difficulty")
                if kw and difficulty is not None:
                    out[kw] = int(difficulty)
        return out

    def fetch_keyword_ideas(self, seeds: list[str], *, limit: int = 20) -> list[dict[str, Any]]:
        """Return new keyword suggestions with real metrics for the given seed keywords.

        Each returned dict is shaped like an seo_keyword entry (query, demand_score,
        competition_score, search_volume, cpc, difficulty_score, data_source).
        Returns [] on any error — never raises.
        """
        if not self.available or not seeds:
            return []
        try:
            return self._fetch_keyword_ideas(seeds, limit=limit)
        except Exception as exc:
            logger.warning("DataForSEO keyword ideas call failed: %s", exc)
            return []

    def fetch_domain_competitors(self, domain: str, *, limit: int = 20) -> list[CompetitorSignal]:
        """Return domains competing with `domain` on Google (shop-level view).

        Returns [] on any error — never raises.
        """
        if not self.available or not domain:
            return []
        try:
            return self._fetch_domain_competitors(domain, limit=limit)
        except Exception as exc:
            logger.warning("DataForSEO domain competitors call failed: %s", exc)
            return []

    def _fetch_keyword_ideas(self, seeds: list[str], *, limit: int) -> list[dict[str, Any]]:
        """POST to DataForSEO Labs Keyword Ideas. Returns enriched keyword dicts."""
        import requests  # noqa: PLC0415

        payload = [{
            "keywords": seeds[:100],
            "location_code": self._location_code,
            "language_code": self._language_code,
            "limit": limit,
        }]
        resp = requests.post(
            _KEYWORD_IDEAS_URL,
            json=payload,
            auth=(self._login, self._password),
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        out: list[dict[str, Any]] = []
        for task in body.get("tasks", []) or []:
            for result in task.get("result", []) or []:
                for item in result.get("items", []) or []:
                    kw = str(item.get("keyword", "")).strip()
                    if not kw:
                        continue
                    info = item.get("keyword_info") or {}
                    props = item.get("keyword_properties") or {}
                    vol = info.get("search_volume")
                    cpc = info.get("cpc")
                    comp = info.get("competition")
                    difficulty = props.get("keyword_difficulty")
                    out.append({
                        "query": kw,
                        "intent_type": "unknown",
                        "demand_score": _to_demand_bucket(vol),
                        "competition_score": int(difficulty) if difficulty is not None else _to_difficulty(comp),
                        "product_fit_score": 0,
                        "reason": f"Suggestion DataForSEO — {vol if vol is not None else '—'} rech./mois",
                        "data_source": "dataforseo",
                        "difficulty_source": "dataforseo" if difficulty is not None else "free_estimated",
                        "search_volume": vol,
                        "cpc": cpc,
                        "ads_competition": comp,
                        "notes": [f"Idée DataForSEO Labs — volume {vol}, CPC {cpc}€, difficulté {difficulty}"],
                    })
        return out

    def _fetch_domain_competitors(self, domain: str, *, limit: int) -> list[CompetitorSignal]:
        """POST to DataForSEO Labs Competitors Domain. Returns CompetitorSignal list."""
        import requests  # noqa: PLC0415

        clean_domain = domain.removeprefix("https://").removeprefix("http://").split("/")[0].strip()
        payload = [{
            "target": clean_domain,
            "location_code": self._location_code,
            "language_code": self._language_code,
            "limit": limit,
        }]
        resp = requests.post(
            _DOMAIN_COMPETITORS_URL,
            json=payload,
            auth=(self._login, self._password),
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        out: list[CompetitorSignal] = []
        for task in body.get("tasks", []) or []:
            for result in task.get("result", []) or []:
                for item in result.get("items", []) or []:
                    comp_domain = str(item.get("domain", "")).strip().lower()
                    if not comp_domain or comp_domain == clean_domain.lower():
                        continue
                    intersections = item.get("intersections", 0) or 0
                    avg_pos = item.get("avg_position") or 0
                    strength = max(10, min(100, int(100 - avg_pos * 5 + intersections // 10)))
                    out.append({
                        "domain": comp_domain,
                        "url": None,
                        "matched_keyword": f"{intersections} mots-clés communs",
                        "detected_from": "paid_provider",
                        "content_angle": f"Position moyenne {avg_pos:.1f} — {intersections} intersections",
                        "estimated_strength": strength,
                        "confidence": "high",
                    })
        return out

    def _fetch_serp(self, keywords: list[str]) -> dict[str, list[dict[str, Any]]]:
        """POST to SERP Google Organic Advanced. Returns {keyword_lower: items_list}."""
        import requests  # noqa: PLC0415

        payload = [
            {
                "keyword": kw,
                "location_code": self._location_code,
                "language_code": self._language_code,
                "device": "desktop",
                "os": "windows",
                "depth": 10,
            }
            for kw in keywords
        ]
        resp = requests.post(
            _SERP_URL,
            json=payload,
            auth=(self._login, self._password),
            timeout=_SERP_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        out: dict[str, list[dict[str, Any]]] = {}
        for task in body.get("tasks", []) or []:
            task_kw = str((task.get("data") or {}).get("keyword", "")).strip().lower()
            items: list[dict[str, Any]] = []
            for result in task.get("result", []) or []:
                items.extend(result.get("items", []) or [])
            if task_kw:
                out[task_kw] = items
        return out


# ── SERP parsing (pure function — easier to test) ────────────────────────────

def _parse_serp_competitors(serp_data: dict[str, list[dict[str, Any]]]) -> list[CompetitorSignal]:
    """Convert raw SERP items into deduplicated CompetitorSignal list.

    Priority: featured_snippet (strength 100) > organic by rank.
    One signal per domain — keeps the best (highest strength) occurrence.
    """
    best: dict[str, CompetitorSignal] = {}  # domain → signal

    for kw, items in serp_data.items():
        paa_questions: list[str] = []

        # First pass: collect PAA questions for this keyword
        for item in items:
            if item.get("type") == "people_also_ask":
                q = item.get("title", "").strip()
                if q:
                    paa_questions.append(q)

        # Second pass: build competitor signals
        for item in items:
            item_type = item.get("type", "")
            domain = str(item.get("domain", "")).strip().lower()
            if not domain:
                continue

            if item_type == "featured_snippet":
                sig: CompetitorSignal = {
                    "domain": domain,
                    "url": item.get("url"),
                    "matched_keyword": kw,
                    "detected_from": "paid_provider",
                    "content_angle": f"[Featured Snippet] {item.get('title', '').strip()}",
                    "estimated_strength": 100,
                    "confidence": "high",
                }
                existing = best.get(domain)
                if existing is None or (existing.get("estimated_strength", 0) < 100):
                    best[domain] = sig

            elif item_type == "organic":
                rank = int(item.get("rank_absolute", 10))
                strength = _serp_strength(rank)
                angle = item.get("title", "").strip()
                if paa_questions:
                    angle += f" | PAA: {paa_questions[0]}"
                sig = {
                    "domain": domain,
                    "url": item.get("url"),
                    "matched_keyword": kw,
                    "detected_from": "paid_provider",
                    "content_angle": angle,
                    "estimated_strength": strength,
                    "confidence": "high",
                }
                existing = best.get(domain)
                if existing is None or (existing.get("estimated_strength", 0) < strength):
                    best[domain] = sig

    return sorted(best.values(), key=lambda s: s.get("estimated_strength", 0), reverse=True)


def _parse_serp_intelligence(
    serp_data: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Extract per-keyword PAA questions, top organic titles and featured snippet.

    Unlike _parse_serp_competitors, the People-Also-Ask question strings are
    kept here so they can seed the content prompt's FAQ and GEO questions.
    """
    out: dict[str, dict[str, Any]] = {}
    for kw, items in serp_data.items():
        paa: list[str] = []
        top_competitors: list[dict[str, Any]] = []
        featured_snippet: str | None = None

        for item in items:
            item_type = item.get("type", "")
            if item_type == "people_also_ask":
                question = str(item.get("title", "")).strip()
                if question and question not in paa:
                    paa.append(question)
            elif item_type == "featured_snippet":
                if featured_snippet is None:
                    title = str(item.get("title", "")).strip()
                    if title:
                        featured_snippet = title
            elif item_type == "organic":
                domain = str(item.get("domain", "")).strip().lower()
                title = str(item.get("title", "")).strip()
                if domain and len(top_competitors) < 5:
                    top_competitors.append({
                        "domain": domain,
                        "title": title,
                        "url": item.get("url"),
                        "rank": int(item.get("rank_absolute", 0) or 0),
                    })

        out[kw] = {
            "paa": paa,
            "top_competitors": top_competitors,
            "featured_snippet": featured_snippet,
        }
    return out
