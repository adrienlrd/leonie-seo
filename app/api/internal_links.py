"""Internal linking opportunities endpoint — read-only, no Shopify writes."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from scripts.report.detect_internal_links import (
    _anchor_from_keyword,
    _tokenize,
    load_keywords,
)

router = APIRouter(tags=["internal_links"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"
_KEYWORDS_PATH = Path(__file__).parents[2] / "config" / "keywords.yaml"


def _detect_opportunities(
    keywords: dict[str, list[str]],
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    base_url: str,
) -> list[dict[str, Any]]:
    """Generic token-overlap opportunity detection — works for any shop."""
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for category, kw_list in keywords.items():
        if category == "brand":
            continue
        for keyword in kw_list:
            kw_tokens = _tokenize(keyword)
            if not kw_tokens:
                continue

            for product in products:
                handle = product.get("handle", "")
                title = product.get("title", "")
                if not handle:
                    continue
                title_tokens = _tokenize(title)
                overlap = len(kw_tokens & title_tokens)
                if overlap == 0:
                    continue
                score = round(overlap / len(kw_tokens), 2)
                target_url = f"{base_url}/products/{handle}"
                key = (keyword, target_url)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "source_keyword": keyword,
                        "source_category": category,
                        "target_type": "product",
                        "target_title": title,
                        "target_url": target_url,
                        "anchor_text": _anchor_from_keyword(keyword, title),
                        "relevance_score": score,
                    }
                )

            for coll in collections:
                chandle = coll.get("handle", "")
                ctitle = coll.get("title", chandle)
                if not chandle:
                    continue
                ctokens = _tokenize(ctitle)
                overlap = len(kw_tokens & ctokens)
                if overlap == 0:
                    continue
                score = round(overlap / len(kw_tokens), 2)
                target_url = f"{base_url}/collections/{chandle}"
                key = (keyword, target_url)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "source_keyword": keyword,
                        "source_category": category,
                        "target_type": "collection",
                        "target_title": ctitle,
                        "target_url": target_url,
                        "anchor_text": _anchor_from_keyword(keyword, ctitle),
                        "relevance_score": score,
                    }
                )

    return sorted(results, key=lambda x: -x["relevance_score"])


def _detect_orphans(
    products: list[dict[str, Any]],
    gsc_urls: set[str],
    base_url: str,
) -> list[dict[str, Any]]:
    """Products with zero GSC impressions — candidates for incoming links."""
    orphans = []
    for p in products:
        handle = p.get("handle", "")
        if not handle:
            continue
        url = f"{base_url}/products/{handle}"
        if url not in gsc_urls:
            orphans.append(
                {
                    "title": p.get("title", handle),
                    "url": url,
                    "handle": handle,
                    "recommendation": "Créer un lien interne depuis un article de blog ou une page collection.",
                }
            )
    return orphans


def _load_gsc_urls(shop: str) -> set[str]:
    path = _DATA_DIR / shop / "gsc_performance.csv"
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path)
        if "impressions" in df.columns and "url" in df.columns:
            return set(df[df["impressions"] > 0]["url"].tolist())
    except Exception:
        pass
    return set()


@router.get("/api/shops/{shop}/audit/internal-links")
async def get_internal_links(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 50,
) -> dict:
    """Return internal linking opportunities and orphan pages.

    Read-only — no Shopify writes.
    Requires keywords.yaml and a Shopify snapshot.
    GSC data enriches orphan detection when available.
    """
    if not _KEYWORDS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="keywords.yaml not found. Add config/keywords.yaml to enable internal link analysis.",
        )

    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No Shopify snapshot found. Run an SEO audit first.",
        )

    keywords = load_keywords(str(_KEYWORDS_PATH))
    products = snapshot.get("products", [])
    collections = snapshot.get("collections", [])
    base_url = f"https://{ctx.shop}"
    gsc_urls = _load_gsc_urls(ctx.shop)

    opportunities = _detect_opportunities(keywords, products, collections, base_url)
    orphans = _detect_orphans(products, gsc_urls, base_url) if gsc_urls else []

    return {
        "shop": ctx.shop,
        "available": True,
        "total_opportunities": len(opportunities),
        "total_orphans": len(orphans),
        "gsc_connected": bool(gsc_urls),
        "summary": {
            "product_links": sum(1 for o in opportunities if o["target_type"] == "product"),
            "collection_links": sum(1 for o in opportunities if o["target_type"] == "collection"),
            "orphans": len(orphans),
        },
        "opportunities": opportunities[:top],
        "orphans": orphans,
    }
