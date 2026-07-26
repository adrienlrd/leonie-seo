"""AI visibility measurement: which sources does an AI answer engine cite when
a shopper asks a buying question in this shop's niche — and is the shop cited?

This is the one grounded use case where Gemini is the right instrument rather
than a data provider. Measured live 2026-07-26: a real buyer question ("quelle
fontaine à eau pour chat choisir ?") triggers a web search 6 times out of 8,
and the domains come back in `groundingMetadata`, which the model cannot forge.
We are not asking Gemini for an opinion about the market — we are observing what
an AI engine actually surfaces, which is the thing the merchant wants to know.

Consistent with `app/api/ai_visibility.py`: a measured signal, never a promise
of appearing in AI engines.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.analysis_artifacts import load_artifact, save_artifact
from app.llm import LLMError, get_router
from app.paths import data_dir

logger = logging.getLogger(__name__)

_DATA_DIR = data_dir()
_ARTIFACT_TYPE = "ai_visibility"
_FILE_NAME = "ai_visibility.json"

# One grounded call per question, so keep the set small and stable.
_MAX_QUESTIONS = 5

_SYSTEM_PROMPT = (
    "Tu réponds comme un assistant qui conseille un acheteur. Cherche sur le web "
    "avant de répondre et cite tes sources."
)


def _build_prompt(question: str) -> str:
    """Ask the buyer question in prose, exactly as a shopper would.

    No JSON, no schema, no instruction about sources beyond citing them:
    measured live, requesting a structured answer drops the web-search rate to
    zero (see `app/niche/signals/realtime_trends.py::_build_prompt`). The answer
    text itself is not what we keep — the grounding citations are.
    """
    return question


def _domain_of(citation: dict[str, Any]) -> str:
    """Best-effort publisher domain for one grounding citation.

    Gemini returns redirect URLs on `vertexaisearch.cloud.google.com`, so the
    hostname is useless; the chunk `title` carries the real publisher domain.
    """
    title = str(citation.get("title") or "").strip().lower()
    if title and "." in title and " " not in title:
        return re.sub(r"^www\.", "", title)
    host = urlparse(str(citation.get("url") or "")).netloc.lower()
    if host and "vertexaisearch" not in host:
        return re.sub(r"^www\.", "", host)
    return title


def measure_ai_visibility(
    shop: str,
    questions: list[str],
    shop_domains: list[str],
    *,
    db_path: Path | None = None,
    persist: bool = True,
) -> dict[str, Any] | None:
    """Ask each buying question and record which domains the AI engine cited.

    Returns ``{questions: [...], top_domains: [...], shop_cited_count,
    questions_measured, measured_at}`` or None when nothing could be measured
    (fail-open: this is an optional signal, it never breaks its caller).

    A question whose answer carried no grounding metadata is reported with
    ``grounded: False`` and contributes no domains — the model answered from
    memory, so it observed nothing.
    """
    asked = [q.strip() for q in questions if q and q.strip()][:_MAX_QUESTIONS]
    if not asked:
        return None
    own = {re.sub(r"^www\.", "", d.strip().lower()) for d in shop_domains if d and d.strip()}

    try:
        router = get_router(shop=shop, tier="grounded")
    except LLMError as exc:
        logger.warning("ai_visibility: no router for %s: %s", shop, exc)
        return None

    results: list[dict[str, Any]] = []
    domain_counts: dict[str, int] = {}
    for question in asked:
        try:
            result = router.complete(
                _build_prompt(question), system=_SYSTEM_PROMPT, max_tokens=1536, temperature=0.2
            )
        except LLMError as exc:
            logger.warning("ai_visibility: call failed for %s: %s", shop, exc)
            continue
        except Exception as exc:  # noqa: BLE001 — optional signal, never fail the caller
            logger.warning("ai_visibility: unexpected error for %s: %s", shop, exc)
            continue

        grounded = result.provider == "gemini" and bool(result.search_queries or result.citations)
        domains: list[str] = []
        if grounded:
            for citation in result.citations:
                domain = _domain_of(citation)
                if domain and domain not in domains:
                    domains.append(domain)
            for domain in domains:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        results.append(
            {
                "question": question,
                "grounded": grounded,
                "domains": domains,
                "shop_cited": any(d in own for d in domains),
            }
        )

    measured = [r for r in results if r["grounded"]]
    if not measured:
        return None

    visibility: dict[str, Any] = {
        "questions": results,
        "top_domains": [
            {"domain": d, "citations": n}
            for d, n in sorted(domain_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        ],
        "questions_measured": len(measured),
        "questions_asked": len(results),
        "shop_cited_count": sum(1 for r in measured if r["shop_cited"]),
        "measured_at": datetime.now(UTC).isoformat(),
    }
    if persist:
        _persist(shop, visibility, db_path=db_path)
    return visibility


def _persist(shop: str, visibility: dict[str, Any], *, db_path: Path | None = None) -> None:
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / _FILE_NAME).write_text(
            json.dumps(visibility, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.error("ai_visibility: failed to write file for %s: %s", shop, exc)
    # DB mirror so the measurement survives an ephemeral-disk restart (Render Free).
    save_artifact(shop, _ARTIFACT_TYPE, visibility, db_path=db_path)


def load_ai_visibility(shop: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    """Load the last persisted measurement, or None. Never triggers a call."""
    path = _DATA_DIR / shop / _FILE_NAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return load_artifact(shop, _ARTIFACT_TYPE, db_path=db_path)
