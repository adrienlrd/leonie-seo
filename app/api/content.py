"""Content generation — FAQ suggestions and blog brief outlines."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db

router = APIRouter(prefix="/api", tags=["content"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"

# ---------------------------------------------------------------------------
# Generic FAQ templates — filled with product title at runtime
# ---------------------------------------------------------------------------

_FAQ_TEMPLATES: list[tuple[str, str]] = [
    (
        "Comment entretenir {title} ?",
        "Pour prolonger la durée de vie de {title}, nettoyez-le régulièrement avec un chiffon doux humide. "
        "Évitez les produits abrasifs et rangez-le à l'abri de l'humidité.",
    ),
    (
        "Quelle taille choisir pour {title} ?",
        "Consultez le guide des tailles disponible sur la fiche produit de {title}. "
        "En cas de doute entre deux tailles, optez pour la plus grande pour plus de confort.",
    ),
    (
        "{title} est-il adapté à tous les animaux ?",
        "{title} a été conçu pour s'adapter à la majorité des animaux domestiques. "
        "Vérifiez les dimensions et le poids recommandé dans la fiche produit.",
    ),
    (
        "Quelle est la durée de livraison pour {title} ?",
        "La livraison de {title} est estimée entre 3 et 5 jours ouvrés en France métropolitaine. "
        "Un email de suivi vous est envoyé dès l'expédition.",
    ),
    (
        "{title} est-il garanti ?",
        "Oui, {title} est couvert par notre garantie satisfait ou remboursé pendant 30 jours. "
        "En cas de problème, contactez notre service client.",
    ),
]

# ---------------------------------------------------------------------------
# Blog brief templates — informational keyword patterns
# ---------------------------------------------------------------------------

_QUESTION_WORDS = {
    "fr": [
        "comment",
        "pourquoi",
        "quelle",
        "quel",
        "quels",
        "quelles",
        "combien",
        "meilleur",
        "meilleure",
        "guide",
        "conseil",
        "astuce",
        "choisir",
    ],
    "en": ["how", "why", "what", "which", "best", "guide", "tips", "choose", "when"],
}

_H2_TEMPLATES: list[str] = [
    "Pourquoi choisir {keyword} pour votre animal ?",
    "Les critères essentiels pour bien choisir",
    "Comment utiliser et entretenir votre {keyword}",
    "Nos conseils d'experts",
    "Questions fréquentes sur {keyword}",
]


def _strip_html(html: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


# ---------------------------------------------------------------------------
# FAQ generation
# ---------------------------------------------------------------------------


def _build_faq_for_product(product: dict[str, Any]) -> list[dict[str, str]]:
    title = product.get("title", "")
    return [{"q": q.format(title=title), "a": a.format(title=title)} for q, a in _FAQ_TEMPLATES]


def _build_jsonld(faq: list[dict[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in faq
        ],
    }


# ---------------------------------------------------------------------------
# Blog brief generation
# ---------------------------------------------------------------------------


def _load_gsc_queries(shop: str) -> list[dict]:
    """Load GSC query data from per-shop CSV."""
    path = _DATA_DIR / shop / "gsc_performance.csv"
    if not path.exists():
        return []
    try:
        reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
        return [dict(r) for r in reader]
    except (OSError, csv.Error):
        return []


def _is_informational(query: str) -> bool:
    q = query.lower()
    for words in _QUESTION_WORDS.values():
        if any(q.startswith(w) or f" {w} " in q for w in words):
            return True
    return False


def _build_brief(query: str, impressions: int, products: list[dict]) -> dict:
    """Build a blog brief skeleton for an informational query."""
    keyword = query.strip()
    h2s = [h.format(keyword=keyword) for h in _H2_TEMPLATES]

    # Find relevant internal links from snapshot
    kw_words = set(keyword.lower().split())
    internal_links: list[dict] = []
    for p in products:
        title_words = set((p.get("title") or "").lower().split())
        if kw_words & title_words and p.get("handle"):
            internal_links.append({"title": p["title"], "path": f"/products/{p['handle']}"})
    internal_links = internal_links[:4]

    return {
        "target_keyword": keyword,
        "impressions": impressions,
        "suggested_title": f"Guide complet : {keyword.capitalize()}",
        "word_count_target": 800,
        "h2_sections": h2s,
        "internal_links": internal_links,
        "call_to_action": "Découvrez notre sélection",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/content/faq")
async def get_faq_suggestions(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 30,
) -> dict:
    """Return FAQ suggestions per product with Schema.org JSON-LD.

    Generates generic e-commerce FAQ from product titles — no niche config
    required. FAQ entries are ready to embed in product pages or blog articles.

    Args:
        shop: Shopify shop domain.
        top: Max products to include (default 30).
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    products = snapshot.get("products", [])[:top]
    items = []
    for p in products:
        if not p.get("title") or not p.get("handle"):
            continue
        faq = _build_faq_for_product(p)
        items.append(
            {
                "product_id": p.get("id", ""),
                "handle": p["handle"],
                "title": p["title"],
                "faq_count": len(faq),
                "faq": faq,
                "jsonld": _build_jsonld(faq),
            }
        )

    return {
        "shop": ctx.shop,
        "available": True,
        "total": len(items),
        "note": "FAQ générées à partir de templates e-commerce génériques. Personnalisez les réponses avant publication.",
        "items": items,
    }


@router.get("/shops/{shop}/content/briefs")
async def get_blog_briefs(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 20,
    min_impressions: int = 10,
) -> dict:
    """Return blog brief outlines from informational GSC queries.

    Identifies question-type and informational queries in GSC data (how, why,
    best, guide…) and builds a brief skeleton with H2 structure, word count
    target, and internal link suggestions from the product catalog.

    Args:
        shop: Shopify shop domain.
        top: Max briefs to return (default 20).
        min_impressions: Minimum GSC impressions to include a query (default 10).
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    products = snapshot.get("products", []) if snapshot else []

    gsc_rows = _load_gsc_queries(ctx.shop)

    informational = []
    for row in gsc_rows:
        query = row.get("query", "").strip()
        if not query or not _is_informational(query):
            continue
        try:
            impr = int(float(row.get("impressions", 0)))
        except (ValueError, TypeError):
            impr = 0
        if impr < min_impressions:
            continue
        informational.append((query, impr))

    informational.sort(key=lambda x: -x[1])
    informational = informational[:top]

    briefs = [_build_brief(q, impr, products) for q, impr in informational]

    return {
        "shop": ctx.shop,
        "available": True,
        "gsc_connected": bool(gsc_rows),
        "total": len(briefs),
        "note": (
            "Briefs générés depuis les requêtes GSC informationnelles. "
            "Personnalisez le contenu avant rédaction."
            if gsc_rows
            else "Aucune donnée GSC disponible. Connectez Google Search Console pour des briefs basés sur vos vraies requêtes."
        ),
        "briefs": briefs,
    }
