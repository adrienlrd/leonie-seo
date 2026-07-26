"""Real-time world events (weather, news, calendar) for the shop's market, via
Gemini + Google Search grounding — paid plans (pro, agency) only.

Unlike `app/niche/signals/trends.py` (Google Trends, fixed 12-month window),
this fetches what is happening THIS WEEK, with cited sources, consistent with
the project rule that real, sourced data always outranks an AI estimate.

Deliberately asks nothing about the shop's niche: see `_build_prompt`. Crossing
these events with the catalog is done in Python by the callers.
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

# One grounded call per shop, so the cache mainly protects re-runs (scheduled
# reanalysis, a merchant clicking twice). World events do not change within half
# a day.
_CACHE_TTL_HOURS = 12

_EMPTY_SIGNALS: dict[str, Any] = {"events": [], "citations": []}

_SYSTEM_PROMPT = (
    "Tu es un veilleur. Tu réponds UNIQUEMENT avec des faits confirmés par une "
    "recherche web déclenchée maintenant, en citant tes sources. N'invente "
    "jamais un événement."
)

# Structuring the prose is a separate, cheap, ungrounded call — see
# `_build_prompt` for why the grounded call must not be asked for JSON.
_STRUCTURE_SYSTEM_PROMPT = (
    "Tu convertis un texte en JSON. Tu n'ajoutes AUCUN fait absent du texte "
    "fourni. Si le texte ne dit rien sur un point, tu n'inventes rien."
)


def _build_prompt(language: str = "fr") -> str:
    """Ask, in prose, ONLY about the state of the world — never about the niche,
    and never for JSON.

    Two things were measured live on 2026-07-26, and both shape this prompt:

    - A niche question ("what is trending for cat accessories?") triggers zero
      web searches: the model believes it knows, answers from memory and invents
      source URLs. Asking what the weather / news / school calendar is right now
      fires reliably, with real sources (meteofrance.com, service-public.gouv.fr).
      The model searches only when it knows it cannot know.
    - Asking for JSON suppresses the search entirely: the same prose question
      scored 3 searches / 6-8 citations, and 0 / 0 as soon as a JSON schema was
      requested — with or without a system prompt. The model treats a schema as a
      formatting task. Hence prose here, and `_structure_events()` afterwards.

    The niche linkage is not asked of the model either: `_event_ideas`
    (`app/blog/idea_generator.py`) and the Pass 1 prompt cross these events with
    the real catalog deterministically, in Python.
    """
    from app.llm.language_context import grounding_market  # noqa: PLC0415

    country, lang_label = grounding_market(language)
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    return (
        f"Nous sommes le {today}. Cherche sur le web en {lang_label} et réponds pour "
        f"le pays suivant : {country}. Réponds en trois courts paragraphes, un par question, "
        f"en citant tes sources.\n\n"
        "1. Quelles conditions météo notables touchent ce pays cette semaine "
        "(canicule, vague de froid, tempête, fortes pluies) et dans quelles régions ?\n"
        "2. Quelle actualité grand public marque ce pays cette semaine ?\n"
        "3. Quelles vacances scolaires, jours fériés ou grands événements ont lieu "
        "dans les 3 prochaines semaines ?"
    )


def _build_structure_prompt(summary: str, language: str) -> str:
    from app.llm.language_context import output_instruction  # noqa: PLC0415

    return (
        "Voici une synthèse d'actualité issue d'une recherche web :\n\n"
        f"{summary}\n\n"
        "Convertis-la en JSON strict avec ce schéma exact :\n"
        "{\n"
        '  "events": [{"title": str, "description": str, "kind": "weather"|"news"|"calendar"}]\n'
        "}\n\n"
        "Un événement par fait distinct, maximum 6. title : court (max 60 caractères). "
        "description : une phrase reprise du texte. N'ajoute aucun fait absent du texte.\n"
        f"{output_instruction(language)}"
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
        logger.warning("realtime_signals: could not parse the structured JSON response")
        return None
    if not isinstance(parsed, dict):
        return None
    events = parsed.get("events")
    if not isinstance(events, list):
        return None
    kinds = {"weather", "news", "calendar"}
    out: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        kind = str(item.get("kind") or "").strip().lower()
        out.append(
            {
                "title": title,
                "description": str(item.get("description") or "").strip(),
                "kind": kind if kind in kinds else "news",
            }
        )
    # The prompt asks for 6; the model sometimes returns more.
    return {"events": out[:6]}


def _structure_events(shop: str, summary: str, language: str) -> dict[str, Any] | None:
    """Turn the grounded prose into the events schema, or None if unusable.

    Deliberately the default (ungrounded, cheaper) chain: this call invents
    nothing, it only reshapes text that a grounded call already produced.
    """
    try:
        result = get_router(shop=shop).complete(
            _build_structure_prompt(summary, language),
            system=_STRUCTURE_SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.0,
            json_mode=True,
        )
    except LLMError as exc:
        logger.warning("realtime_signals: structuring call failed for %s: %s", shop, exc)
        return None
    return _parse_signals(result.text)


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
    *,
    db_path: Path | None = None,
    force: bool = False,
    status_out: dict[str, Any] | None = None,
    language: str = "fr",
) -> dict[str, Any] | None:
    """Fetch and persist a snapshot of what is happening in the shop's market.

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

    One call per shop, not per product: the question is about the country, not
    about a product, so a whole catalog analysis costs a single grounded call.
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

    try:
        router = get_router(shop=shop, tier="grounded")
        result = router.complete(
            _build_prompt(language),
            system=_SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.2,
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

    summary = result.text.strip()
    parsed = _structure_events(shop, summary, language)
    if parsed is None or not parsed["events"]:
        _set_status(status_out, "parse_error")
        return None

    signals: dict[str, Any] = {
        **parsed,
        # The prose the grounded call actually returned. Kept so the merchant can
        # read what the sources said, rather than only the structured summary.
        "summary": summary,
        "citations": result.citations,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    _persist(shop, signals, db_path=db_path)
    _set_status(status_out, "ok")
    return signals


def _persist(shop: str, signals: dict[str, Any], *, db_path: Path | None = None) -> None:
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / _FILE_NAME).write_text(json.dumps(signals, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.error("realtime_signals: failed to write file for %s: %s", shop, exc)
    # DB mirror so the signal survives an ephemeral-disk restart (Render Free).
    save_artifact(shop, _ARTIFACT_TYPE, signals, db_path=db_path)


def realtime_signals_state(shop: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Why the merchant is or isn't seeing real-time trends, without calling out.

    Derived from state we already have, so no new storage: the plan, the key,
    and the age of the persisted snapshot. `state` is one of
    ``plan_not_eligible`` | ``no_gemini_key`` | ``never_measured`` | ``stale`` |
    ``fresh``. Grounding is probabilistic — an eligible shop legitimately shows
    ``never_measured`` when no analysis has produced a grounded answer yet, and
    that must read as "not measured", never as "no trends exist".
    """
    if get_plan_for_shop(shop, db_path) not in GROUNDED_PLANS:
        return {"state": "plan_not_eligible", "fetched_at": None}
    if not os.getenv("GEMINI_API_KEY"):
        return {"state": "no_gemini_key", "fetched_at": None}
    signals = load_realtime_signals(shop, db_path=db_path)
    if not signals:
        return {"state": "never_measured", "fetched_at": None}
    fetched_at = str(signals.get("fetched_at") or "") or None
    fresh = _fresh_cached_signals(shop, db_path=db_path) is not None
    return {"state": "fresh" if fresh else "stale", "fetched_at": fetched_at}


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
