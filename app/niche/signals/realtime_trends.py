"""Real-time market signals (events, rising queries, competitor moves) via
Gemini + Google Search grounding — paid plans (pro, agency) only.

Unlike `app/niche/signals/trends.py` (Google Trends, fixed 12-month window),
this fetches what is happening THIS WEEK, with cited sources, consistent with
the project rule that real, sourced data always outranks an AI estimate.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.analysis_artifacts import load_artifact, save_artifact
from app.billing.quotas import GROUNDED_PLANS
from app.billing.subscription_store import get_plan_for_shop
from app.llm import CompletionResult, LLMError, get_router
from app.paths import data_dir

logger = logging.getLogger(__name__)

_DATA_DIR = data_dir()
_ARTIFACT_TYPE = "realtime_signals"
_FILE_NAME = "realtime_signals.json"

# A grounded fetch runs per product, so a full catalog analysis costs one call
# per product. Reusing a snapshot younger than this collapses a whole re-run
# (e.g. the scheduled reanalysis) to zero grounded calls — the signals are
# weekly events and rising queries, they do not change within half a day.
_CACHE_TTL_HOURS = 12

_EMPTY_SIGNALS: dict[str, Any] = {
    "events": [],
    "rising_queries": [],
    "competitor_moves": [],
    "citations": [],
}

_SYSTEM_PROMPT = (
    "Tu es un veilleur e-commerce. Tu DOIS effectuer une recherche web réelle "
    "avant de répondre — ne réponds JAMAIS uniquement depuis ta mémoire ou tes "
    "connaissances d'entraînement, même si le sujet te semble familier. Tu "
    "réponds UNIQUEMENT avec des faits que tu peux confirmer par une recherche "
    "web déclenchée maintenant, avec leurs sources. N'invente jamais un "
    "événement ou une tendance sans pouvoir citer une URL réelle et vérifiable."
)


def _build_prompt(niche_summary: str, product_titles: list[str], language: str = "fr") -> str:
    from app.llm.language_context import grounding_market  # noqa: PLC0415

    country, lang_label = grounding_market(language)
    products_text = ", ".join(product_titles[:5]) if product_titles else "non renseigné"
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    return (
        f"Nous sommes précisément le {today}. Toute information que tu fournis doit être "
        f"vérifiable à cette date exacte — effectue une recherche web maintenant, "
        f"ne réponds pas depuis ta mémoire. Boutique e-commerce vendant sur le marché : {country}. "
        f"Niche : {niche_summary or 'non renseignée'}. Exemples de produits : {products_text}.\n\n"
        f"Cherche sur le web en {lang_label} (marché {country}) et réponds en JSON strict avec ce schéma exact :\n"
        "{\n"
        '  "events": [{"title": str, "description": str, "source_url": str}],\n'
        '  "rising_queries": [{"query": str, "why": str, "source_url": str}],\n'
        '  "competitor_moves": [{"summary": str, "source_url": str}]\n'
        "}\n\n"
        "events: actualité/contexte SAISONNIER de cette semaine touchant cette niche "
        "(météo, actualité, jours fériés) — maximum 3.\n"
        "rising_queries: requêtes ou produits en hausse en ce moment dans cette niche — maximum 5.\n"
        "competitor_moves: contenus récents notables de concurrents dans cette niche — maximum 3.\n"
        "Chaque élément DOIT avoir un source_url réel et vérifiable. "
        "Si tu ne trouves rien de fiable pour une catégorie, renvoie une liste vide pour elle."
    )


def _parse_signals(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("realtime_signals: could not parse Gemini JSON response")
        return None
    if not isinstance(parsed, dict):
        return None
    return {
        "events": parsed.get("events") if isinstance(parsed.get("events"), list) else [],
        "rising_queries": parsed.get("rising_queries")
        if isinstance(parsed.get("rising_queries"), list)
        else [],
        "competitor_moves": parsed.get("competitor_moves")
        if isinstance(parsed.get("competitor_moves"), list)
        else [],
    }


def _set_status(status_out: dict[str, Any] | None, status: str, detail: str = "") -> None:
    if status_out is not None:
        status_out.clear()
        status_out.update({"status": status, "detail": detail})


def _fresh_cached_signals(shop: str, *, db_path: Path | None) -> dict[str, Any] | None:
    """Return the persisted snapshot if it is younger than `_CACHE_TTL_HOURS`.

    A snapshot with an unparseable or absent `fetched_at` is treated as
    expired: better one extra grounded call than serving stale events as
    current ones.
    """
    cached = load_realtime_signals(shop, db_path=db_path)
    if not cached:
        return None
    try:
        fetched_at = datetime.fromisoformat(str(cached.get("fetched_at") or ""))
    except ValueError:
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    age_hours = (datetime.now(UTC) - fetched_at).total_seconds() / 3600
    return cached if 0 <= age_hours < _CACHE_TTL_HOURS else None


def _grounding_failure(result: CompletionResult) -> str:
    """Return "" when the answer is backed by a real web search, else why not.

    Two distinct ways an answer arrives ungrounded, both of which produce
    invented `source_url` values because the prompt demands one per item:

    - the "grounded" router fell back to the default chain (no web access);
    - Gemini answered from memory without calling the search tool at all.
      Enabling the tool only makes search *available*; the model decides. The
      prompts insist on searching, and measured live 2026-07-26 that changes
      nothing: the verification prompt triggered zero searches in 4/4 runs yet
      still returned confident verdicts with plausible-looking URLs.

    `groundingMetadata` is the only trustworthy witness — the model cannot
    forge `webSearchQueries`/`groundingChunks`, only prose. Sourced-looking
    fabrications are worse than no signal at all (project rule: real data
    first, sources always shown), so an unwitnessed answer is discarded.
    """
    if result.provider != "gemini":
        return f"fallback provider: {result.provider}"
    if not result.search_queries and not result.citations:
        return "gemini answered without running a web search"
    return ""


def fetch_realtime_signals(
    shop: str,
    niche_hypothesis: dict[str, Any] | None,
    product_titles: list[str],
    *,
    db_path: Path | None = None,
    force: bool = False,
    status_out: dict[str, Any] | None = None,
    persist: bool = True,
    language: str = "fr",
) -> dict[str, Any] | None:
    """Fetch (and, by default, persist) a real-time market signal snapshot.

    Gated to `GROUNDED_PLANS` and a configured GEMINI_API_KEY — returns None
    immediately (no HTTP call, no cost) for every other shop. Fail-open on any
    error (network, parsing, missing grounding) so an analysis job never fails
    because this optional signal could not be fetched.

    A snapshot younger than `_CACHE_TTL_HOURS` is returned as-is (status
    ``cached``, no API call): re-analysing the same shop twice in a day must
    not pay for the same weekly signal twice.

    ``force`` skips the plan gate (still requires GEMINI_API_KEY) — used only
    by the internal Pro/Grande boutique comparison tool so the agency branch
    is exercised even when the shop isn't actually on that plan. Never write
    the shop's real billing state.

    ``status_out`` (optional), populated with why the call did or didn't run:
    ``status`` one of ``no_gemini_key`` | ``plan_not_eligible`` | ``llm_error``
    | ``parse_error`` | ``not_grounded`` | ``cached`` | ``ok``, plus ``detail``.
    Lets callers (and the plan comparison export) show *why* grounding was
    silent instead of guessing.

    ``persist`` (default True): when a caller invokes this once per product
    (engine.py's per-product grounding loop), pass False and merge + persist
    the combined catalog signal once yourself — otherwise each product's call
    would silently overwrite the previous one's saved snapshot.
    """
    if not force and get_plan_for_shop(shop, db_path) not in GROUNDED_PLANS:
        _set_status(status_out, "plan_not_eligible")
        return None
    if not os.getenv("GEMINI_API_KEY"):
        _set_status(status_out, "no_gemini_key")
        return None

    cached = _fresh_cached_signals(shop, db_path=db_path)
    if cached is not None:
        _set_status(status_out, "cached", str(cached.get("fetched_at") or ""))
        return cached

    niche_hypothesis = niche_hypothesis or {}
    # "primary_niche" is the field engine.py itself reads off niche_hypothesis
    # (see run_market_analysis's niche_summary local) — no separate brand_name
    # field exists on this dict, so the prompt just omits it when absent.
    niche_summary = str(niche_hypothesis.get("primary_niche") or "")

    try:
        router = get_router(shop=shop, tier="grounded")
        result = router.complete(
            _build_prompt(niche_summary, product_titles, language),
            system=_SYSTEM_PROMPT,
            # Grounding redirect URLs (vertexaisearch.cloud.google.com/grounding-api-
            # redirect/...) are ~150-200 chars each; up to 11 items (events + rising
            # queries + competitor moves) each carrying one easily exceeds 1024 tokens
            # and truncates the JSON mid-string — verified live. 4096 gives headroom.
            max_tokens=4096,
            temperature=0.2,
            json_mode=True,
        )
    except LLMError as exc:
        logger.warning("realtime_signals: LLM call failed for %s: %s", shop, exc)
        _set_status(status_out, "llm_error", str(exc))
        return None
    except Exception as exc:  # noqa: BLE001 — this signal is optional, never fail the analysis job for it
        logger.warning("realtime_signals: unexpected error for %s: %s", shop, exc)
        _set_status(status_out, "llm_error", str(exc))
        return None

    ungrounded = _grounding_failure(result)
    if ungrounded:
        logger.warning("realtime_signals: discarded ungrounded answer (%s)", ungrounded)
        _set_status(status_out, "not_grounded", ungrounded)
        return None

    parsed = _parse_signals(result.text)
    if parsed is None:
        _set_status(status_out, "parse_error")
        return None

    signals: dict[str, Any] = {
        **parsed,
        "citations": result.citations,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    if persist:
        _persist(shop, signals, db_path=db_path)
    _set_status(status_out, "ok")
    return signals


def persist_realtime_signals(
    shop: str, signals: dict[str, Any], *, db_path: Path | None = None
) -> None:
    """Public entry point for a caller merging multiple per-product signal
    fetches (each with ``persist=False``) into one combined snapshot and
    saving it once — see `fetch_realtime_signals`'s `persist` param.
    """
    _persist(shop, signals, db_path=db_path)


def _persist(shop: str, signals: dict[str, Any], *, db_path: Path | None = None) -> None:
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / _FILE_NAME).write_text(json.dumps(signals, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.error("realtime_signals: failed to write file for %s: %s", shop, exc)
    # DB mirror so the signal survives an ephemeral-disk restart (Render Free).
    save_artifact(shop, _ARTIFACT_TYPE, signals, db_path=db_path)


def load_realtime_signals(shop: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    """Load the last persisted real-time signal snapshot, or None if unavailable.

    Read-only — never triggers a new grounded call. Used by the blog idea
    generator and the dashboard/API surface.
    """
    path = _DATA_DIR / shop / _FILE_NAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return load_artifact(shop, _ARTIFACT_TYPE, db_path=db_path)
