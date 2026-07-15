"""Real-time market signals (events, rising queries, competitor moves) via
Gemini + Google Search grounding — Grande boutique (agency) plan only.

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
from app.billing.subscription_store import get_plan_for_shop
from app.llm import LLMError, get_router
from app.paths import data_dir

logger = logging.getLogger(__name__)

_DATA_DIR = data_dir()
_ARTIFACT_TYPE = "realtime_signals"
_FILE_NAME = "realtime_signals.json"

_EMPTY_SIGNALS: dict[str, Any] = {
    "events": [],
    "rising_queries": [],
    "competitor_moves": [],
    "citations": [],
}

_SYSTEM_PROMPT = (
    "Tu es un veilleur e-commerce. Tu réponds UNIQUEMENT avec des faits que tu "
    "peux confirmer par une recherche web récente, avec leurs sources. "
    "N'invente jamais un événement ou une tendance sans pouvoir citer une URL."
)


def _build_prompt(niche_summary: str, product_titles: list[str]) -> str:
    products_text = ", ".join(product_titles[:5]) if product_titles else "non renseigné"
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    return (
        f"Nous sommes le {today}. Boutique e-commerce française. "
        f"Niche : {niche_summary or 'non renseignée'}. Exemples de produits : {products_text}.\n\n"
        "Cherche sur le web francophone (France) et réponds en JSON strict avec ce schéma exact :\n"
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


def fetch_realtime_signals(
    shop: str,
    niche_hypothesis: dict[str, Any] | None,
    product_titles: list[str],
    *,
    db_path: Path | None = None,
    force: bool = False,
    status_out: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Fetch and persist a real-time market signal snapshot for `shop`.

    Gated to the "agency" plan and a configured GEMINI_API_KEY — returns None
    immediately (no HTTP call, no cost) for every other shop. Fail-open on any
    error (network, parsing, missing grounding) so an analysis job never fails
    because this optional signal could not be fetched.

    ``force`` skips the plan gate (still requires GEMINI_API_KEY) — used only
    by the internal Pro/Grande boutique comparison tool so the agency branch
    is exercised even when the shop isn't actually on that plan. Never write
    the shop's real billing state.

    ``status_out`` (optional), populated with why the call did or didn't run:
    ``status`` one of ``no_gemini_key`` | ``plan_not_agency`` | ``llm_error`` |
    ``parse_error`` | ``ok``, plus ``detail``. Lets callers (and the plan
    comparison export) show *why* grounding was silent instead of guessing.
    """
    if not force and get_plan_for_shop(shop, db_path) != "agency":
        _set_status(status_out, "plan_not_agency")
        return None
    if not os.getenv("GEMINI_API_KEY"):
        _set_status(status_out, "no_gemini_key")
        return None

    niche_hypothesis = niche_hypothesis or {}
    # "primary_niche" is the field engine.py itself reads off niche_hypothesis
    # (see run_market_analysis's niche_summary local) — no separate brand_name
    # field exists on this dict, so the prompt just omits it when absent.
    niche_summary = str(niche_hypothesis.get("primary_niche") or "")

    try:
        router = get_router(shop=shop, tier="grounded")
        result = router.complete(
            _build_prompt(niche_summary, product_titles),
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

    parsed = _parse_signals(result.text)
    if parsed is None:
        _set_status(status_out, "parse_error")
        return None

    signals: dict[str, Any] = {
        **parsed,
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


_VERIFY_SYSTEM_PROMPT = (
    "Tu es un analyste marché e-commerce. Pour chaque mot-clé, indique si une "
    "recherche web récente confirme qu'il est réellement recherché/pertinent "
    "sur le marché français en ce moment. Ne te base QUE sur des résultats de "
    "recherche réels — jamais une estimation ou une intuition."
)

_MAX_VERIFY_KEYWORDS = 30


def _build_verify_prompt(keywords: list[str], niche_summary: str) -> str:
    kw_list = "\n".join(f"- {k}" for k in keywords)
    return (
        f"Niche : {niche_summary or 'non renseignée'}.\n"
        f"Mots-clés à vérifier sur le marché français actuel :\n{kw_list}\n\n"
        "Pour CHAQUE mot-clé de la liste, cherche sur le web et réponds en JSON "
        "strict avec ce schéma exact :\n"
        "{\n"
        '  "verifications": [\n'
        '    {"query": str, "market_evidence": "confirmed"|"rising"|"declining"|"no_signal", '
        '"evidence_note": str, "source_url": str}\n'
        "  ]\n"
        "}\n\n"
        "market_evidence :\n"
        '- "confirmed" : recherche/intérêt réel et stable constaté.\n'
        '- "rising" : tendance à la hausse constatée récemment.\n'
        '- "declining" : intérêt en baisse constaté.\n'
        '- "no_signal" : aucune preuve web trouvée — n\'invente RIEN dans ce cas, '
        "laisse evidence_note et source_url vides.\n"
        "Une entrée par mot-clé de la liste, dans le même ordre si possible."
    )


def _parse_verifications(text: str) -> dict[str, dict[str, Any]] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("verify_keywords_against_market: could not parse Gemini JSON response")
        return None
    if not isinstance(parsed, dict):
        return None
    items = parsed.get("verifications")
    if not isinstance(items, list):
        return None
    by_query: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip().lower()
        evidence = str(item.get("market_evidence") or "no_signal").strip().lower()
        if not query or evidence not in {"confirmed", "rising", "declining", "no_signal"}:
            continue
        by_query[query] = {
            "evidence": evidence,
            "note": str(item.get("evidence_note") or ""),
            "source_url": str(item.get("source_url") or ""),
        }
    return by_query


def verify_keywords_against_market(
    shop: str,
    keywords: list[str],
    niche_summary: str,
    *,
    db_path: Path | None = None,
    force: bool = False,
    status_out: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]] | None:
    """Cross-check a batch of target keywords against the real current market.

    One grounded call per full-catalog job (never per product) — verifies, for
    each keyword, whether real web search evidence confirms it's actually
    searched/relevant right now, distinct from the LLM's own estimate. Returns
    ``{query_lowercased: {evidence, note, source_url}}`` or None (fail-open:
    gating, network, parsing — same guarantees as `fetch_realtime_signals`).

    Capped at `_MAX_VERIFY_KEYWORDS` keywords to keep the call — and its
    token cost — bounded regardless of catalog size.
    """
    if not force and get_plan_for_shop(shop, db_path) != "agency":
        _set_status(status_out, "plan_not_agency")
        return None
    if not os.getenv("GEMINI_API_KEY"):
        _set_status(status_out, "no_gemini_key")
        return None

    deduped = list(dict.fromkeys(k.strip() for k in keywords if k and k.strip()))[:_MAX_VERIFY_KEYWORDS]
    if not deduped:
        _set_status(status_out, "no_signal", "no keywords to verify")
        return None

    try:
        router = get_router(shop=shop, tier="grounded")
        result = router.complete(
            _build_verify_prompt(deduped, niche_summary),
            system=_VERIFY_SYSTEM_PROMPT,
            max_tokens=4096,
            temperature=0.2,
            json_mode=True,
        )
    except LLMError as exc:
        logger.warning("verify_keywords_against_market: LLM call failed for %s: %s", shop, exc)
        _set_status(status_out, "llm_error", str(exc))
        return None
    except Exception as exc:  # noqa: BLE001 — optional signal, never fail the analysis job for it
        logger.warning("verify_keywords_against_market: unexpected error for %s: %s", shop, exc)
        _set_status(status_out, "llm_error", str(exc))
        return None

    verifications = _parse_verifications(result.text)
    if verifications is None:
        _set_status(status_out, "parse_error")
        return None
    _set_status(status_out, "ok")
    return verifications


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
