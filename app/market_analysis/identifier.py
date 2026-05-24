"""AI-powered product label generation — step 1 of the 2-step market analysis flow."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm import LLMError, get_router

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 30  # max products per LLM call

_SYSTEM_PROMPT = (
    "Tu es un expert SEO pour boutiques Shopify. "
    "Réponds uniquement avec du JSON valide et rien d'autre."
)


def _build_label_prompt(items: list[dict[str, str]], niche_summary: str) -> str:
    return (
        f"NICHE: {niche_summary or 'non définie'}\n"
        "Pour chaque produit, génère un label court en français (3 à 6 mots) "
        "qui décrit précisément le produit de façon SEO-friendly.\n"
        "Exemples corrects : 'bol en céramique pour chat', 'fontaine à eau sans fil pour chat', "
        "'pull en cachemire pour chat'.\n"
        f"PRODUITS: {json.dumps(items, ensure_ascii=False)}\n"
        'Réponds uniquement avec un JSON valide : {"<product_id>": "<label>", ...}'
    )


def _parse_labels(raw: str, fallback: dict[str, str]) -> dict[str, str]:
    """Parse LLM JSON output; fall back to original titles on any error."""
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, ValueError):
        pass
    return fallback


def generate_product_labels(
    products: list[dict[str, Any]],
    shop: str,
    niche_summary: str = "",
) -> dict[str, str]:
    """Generate short French SEO labels for all products via LLM (one call per chunk).

    Falls back to the raw Shopify title if the LLM call fails or returns invalid JSON.
    """
    try:
        router = get_router(shop=shop)
    except LLMError:
        router = None

    fallback: dict[str, str] = {
        str(p.get("id", "")): p.get("title", "") for p in products
    }

    if router is None:
        return fallback

    results: dict[str, str] = {}

    chunks = [products[i : i + _CHUNK_SIZE] for i in range(0, len(products), _CHUNK_SIZE)]

    for chunk in chunks:
        items = [
            {
                "id": str(p.get("id", "")),
                "title": p.get("title", ""),
                "collections": ", ".join(
                    c.get("title", "") if isinstance(c, dict) else str(c)
                    for c in (p.get("collections") or [])
                )[:100],
                "tags": str(p.get("tags", ""))[:80],
            }
            for p in chunk
            if isinstance(p, dict)
        ]

        chunk_fallback = {item["id"]: item["title"] for item in items}
        prompt = _build_label_prompt(items, niche_summary)

        try:
            raw = router.complete(
                system=_SYSTEM_PROMPT,
                user=prompt,
                max_tokens=1024,
            )
            chunk_labels = _parse_labels(raw, chunk_fallback)
            results.update(chunk_labels)
        except Exception as exc:
            logger.warning("Label generation failed for chunk: %s", exc)
            results.update(chunk_fallback)

    # Fill any product not returned by LLM
    for pid, title in fallback.items():
        results.setdefault(pid, title)

    return results
