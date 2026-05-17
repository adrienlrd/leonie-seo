"""Semantic content analysis and E-E-A-T scoring for Shopify products."""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db

router = APIRouter(prefix="/api", tags=["semantics"])

# ---------------------------------------------------------------------------
# Built-in E-E-A-T signal lists — generic e-commerce, no tenant config needed
# ---------------------------------------------------------------------------

_EEAT: dict[str, list[str]] = {
    "experience": [
        "testé", "utilisé", "expérience", "durée", "longévité", "après", "pratique",
        "utilise au quotidien", "terrain", "réel", "dans la vie", "adopté",
        "tested", "used", "daily", "experience", "field", "real", "after",
    ],
    "expertise": [
        "fabriqué", "matière", "composition", "certification", "norme", "technique",
        "résistance", "qualité", "spécification", "dimensionné", "conçu",
        "material", "certified", "standard", "specification", "engineered", "quality",
    ],
    "authority": [
        "recommandé", "vétérinaire", "expert", "professionnel", "approuvé", "référence",
        "reconnu", "marque", "distinction", "avis", "note", "élu",
        "recommended", "veterinarian", "expert", "approved", "endorsed", "award",
    ],
    "trust": [
        "garanti", "garantie", "satisfait", "remboursé", "retour", "secure", "sécurisé",
        "paiement", "livraison", "service client", "contact", "support",
        "guaranteed", "warranty", "satisfaction", "refund", "return", "secure",
    ],
}

# Generic content quality signals
_CONTENT_SIGNALS = [
    "pourquoi", "comment", "idéal", "parfait", "recommandé", "compatible",
    "taille", "poids", "matière", "couleur", "livraison", "garantie",
    "why", "how", "ideal", "perfect", "size", "weight", "material", "delivery", "warranty",
]

_DESC_WORDS_WARN = 30
_DESC_WORDS_OK = 80
_SEO_TITLE_MIN = 30
_SEO_TITLE_MAX = 70
_SEO_DESC_MIN = 70
_SEO_DESC_MAX = 160


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------


def _strip_html(html: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _count_signals(text: str, signals: list[str]) -> tuple[int, list[str]]:
    norm = text.lower()
    found = [s for s in signals if s in norm]
    missing = [s for s in signals if s not in norm]
    return len(found), missing


def _score_product(product: dict[str, Any]) -> dict[str, Any]:
    """Compute semantic and E-E-A-T scores for a single product."""
    pid = product.get("id", "")
    title = product.get("title", "")
    handle = product.get("handle", "")
    seo = product.get("seo") or {}
    meta_title = (seo.get("title") or "").strip()
    meta_desc = (seo.get("description") or "").strip()
    body_raw = product.get("descriptionHtml") or product.get("description") or ""
    description = _strip_html(body_raw)
    word_count = len(description.split()) if description else 0
    text = f"{title} {description}"

    # Content richness
    content_found, content_missing = _count_signals(text, _CONTENT_SIGNALS)
    content_score = round(content_found / max(len(_CONTENT_SIGNALS), 1), 2)

    # E-E-A-T dimensions
    dim_scores: dict[str, float] = {}
    dim_missing: dict[str, list[str]] = {}
    for dim, signals in _EEAT.items():
        found, missing = _count_signals(text, signals)
        dim_scores[dim] = round(found / max(len(signals), 1), 2)
        dim_missing[dim] = missing[:3]

    eeat_global = round(
        0.20 * dim_scores["experience"]
        + 0.30 * dim_scores["expertise"]
        + 0.25 * dim_scores["authority"]
        + 0.25 * dim_scores["trust"],
        2,
    )

    # Description length grade
    if word_count == 0:
        desc_grade = "missing"
    elif word_count < _DESC_WORDS_WARN:
        desc_grade = "too_short"
    elif word_count < _DESC_WORDS_OK:
        desc_grade = "short"
    else:
        desc_grade = "ok"

    # SEO fields health
    seo_issues: list[str] = []
    if not meta_title:
        seo_issues.append("missing_meta_title")
    elif len(meta_title) < _SEO_TITLE_MIN:
        seo_issues.append("short_meta_title")
    elif len(meta_title) > _SEO_TITLE_MAX:
        seo_issues.append("long_meta_title")

    if not meta_desc:
        seo_issues.append("missing_meta_description")
    elif len(meta_desc) < _SEO_DESC_MIN:
        seo_issues.append("short_meta_description")
    elif len(meta_desc) > _SEO_DESC_MAX:
        seo_issues.append("long_meta_description")

    # Global content score: 40% description richness, 40% eeat, 20% seo health
    seo_health = 1.0 - (len(seo_issues) / 4)
    global_score = round(0.40 * content_score + 0.40 * eeat_global + 0.20 * seo_health, 2)

    # Priority recommendations
    recommendations: list[str] = []
    if desc_grade in ("missing", "too_short"):
        recommendations.append("Enrichir la description produit (minimum 80 mots recommandés)")
    if "missing_meta_title" in seo_issues:
        recommendations.append("Ajouter un méta title (30-70 caractères)")
    if "missing_meta_description" in seo_issues:
        recommendations.append("Ajouter une méta description (70-160 caractères)")
    if dim_scores["trust"] < 0.15:
        recommendations.append(f"Ajouter des signaux de confiance : {', '.join(dim_missing['trust'][:2])}")
    if dim_scores["expertise"] < 0.15:
        recommendations.append(f"Renforcer l'expertise : {', '.join(dim_missing['expertise'][:2])}")
    if content_score < 0.25 and desc_grade not in ("missing", "too_short"):
        recommendations.append(f"Ajouter des informations clés : {', '.join(content_missing[:3])}")

    return {
        "id": pid,
        "handle": handle,
        "title": title,
        "word_count": word_count,
        "desc_grade": desc_grade,
        "content_score": content_score,
        "eeat_global": eeat_global,
        "experience_score": dim_scores["experience"],
        "expertise_score": dim_scores["expertise"],
        "authority_score": dim_scores["authority"],
        "trust_score": dim_scores["trust"],
        "global_score": global_score,
        "seo_issues": seo_issues,
        "missing_experience": dim_missing["experience"],
        "missing_expertise": dim_missing["expertise"],
        "missing_authority": dim_missing["authority"],
        "missing_trust": dim_missing["trust"],
        "recommendations": recommendations[:3],
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/audit/semantics")
async def get_semantics(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 50,
) -> dict:
    """Return E-E-A-T and semantic content scores per product.

    Scores are computed from built-in e-commerce signal lists — no niche
    config required. Each product gets a global score (0-1) and per-dimension
    E-E-A-T scores with top missing signals and prioritised recommendations.

    Args:
        shop: Shopify shop domain.
        top: Max products to return (default 50, sorted by global_score asc).
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    products = snapshot.get("products", [])
    if not products:
        return {
            "shop": ctx.shop,
            "available": True,
            "total": 0,
            "summary": {},
            "products": [],
        }

    scored = [_score_product(p) for p in products]
    scored.sort(key=lambda r: r["global_score"])  # worst first

    # Summary
    total = len(scored)
    avg_global = round(sum(r["global_score"] for r in scored) / total, 2)
    avg_eeat = round(sum(r["eeat_global"] for r in scored) / total, 2)
    needs_desc = sum(1 for r in scored if r["desc_grade"] in ("missing", "too_short"))
    no_seo = sum(1 for r in scored if r["seo_issues"])

    return {
        "shop": ctx.shop,
        "available": True,
        "total": total,
        "summary": {
            "avg_global_score": avg_global,
            "avg_eeat_score": avg_eeat,
            "products_needing_description": needs_desc,
            "products_with_seo_issues": no_seo,
            "signal_note": "Scores basés sur des signaux e-commerce génériques — configurez votre niche pour affiner.",
        },
        "products": scored[:top],
    }
