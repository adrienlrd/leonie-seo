"""AI-powered product label generation — step 1 of the 2-step market analysis flow."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.llm import LLMError, get_router

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 30  # max products per LLM call


def _extract_description(product: dict[str, Any]) -> str:
    """Return first 200 chars of plain-text product description."""
    raw = product.get("body_html") or product.get("description") or ""
    plain = re.sub(r"<[^>]+>", " ", str(raw))
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:200]


def _extract_collections(product: dict[str, Any]) -> str:
    """Return comma-joined collection titles, handling REST and GraphQL shapes."""
    raw = product.get("collections")
    if not raw:
        return ""
    if isinstance(raw, dict):
        edges = raw.get("edges") or []
        items = [e.get("node", e) if isinstance(e, dict) else e for e in edges]
        if not items:
            items = raw.get("nodes") or []
        raw = items
    if not isinstance(raw, list):
        return ""
    titles = [
        c.get("title", "") if isinstance(c, dict) else str(c)
        for c in raw if c
    ]
    return ", ".join(t for t in titles if t)[:100]

_SYSTEM_PROMPT = (
    "Tu es un expert SEO pour boutiques Shopify. "
    "Réponds uniquement avec du JSON valide et rien d'autre."
)


def _build_label_prompt(items: list[dict[str, str]], niche_summary: str) -> str:
    return (
        f"NICHE: {niche_summary or 'non définie'}\n"
        "Pour chaque produit, génère un label court en français (3 à 6 mots) "
        "qui décrit concrètement CE QU'EST le produit — matière, type, usage — "
        "de façon SEO-friendly. "
        "NE PAS répéter le nom de marque ou le nom commercial. "
        "NE PAS utiliser le titre tel quel. "
        "Décrire le produit comme un client le rechercherait sur Google.\n"
        "Exemples :\n"
        "  Titre 'Le Léonie' → label 'pull en cachemire pour chat'\n"
        "  Titre 'Fontaine Premium' → label 'fontaine à eau filtrante pour chat'\n"
        "  Titre 'Bowl Set' → label 'bol en céramique pour chat'\n"
        "  Titre 'Couchette Royale' → label 'coussin orthopédique pour chat'\n"
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
                "description": _extract_description(p),
                "collections": _extract_collections(p),
                "tags": str(p.get("tags") or "")[:80],
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
