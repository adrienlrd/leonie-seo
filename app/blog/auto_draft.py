"""Auto-generate minimal blog drafts for orphan products.

Called at the end of a full market analysis run. Creates one draft per orphan
product that doesn't already have one, pre-populated with the best blog idea
and a guaranteed link back to the product. Fail-open: errors are logged and
never block the analysis result.
"""

from __future__ import annotations

import logging
from typing import Any

from app.blog.internal_links import build_source_product_link, select_blog_internal_links
from app.blog.store import list_drafts, save_draft

logger = logging.getLogger(__name__)


def auto_create_orphan_drafts(shop: str, analysis_result: dict[str, Any]) -> int:
    """Create blog drafts for orphan products that have no draft yet.

    Returns the number of drafts created.
    """
    orphan_pids: set[str] = set(analysis_result.get("orphan_products") or [])
    if not orphan_pids:
        return 0

    try:
        existing_pids: set[str] = {
            str(d.get("product_id") or "")
            for d in list_drafts(shop)
            if d.get("product_id")
        }
    except Exception as exc:
        logger.warning("auto_create_orphan_drafts: could not load drafts for %s: %s", shop, exc)
        return 0

    products_by_id: dict[str, dict[str, Any]] = {
        str(p.get("product_id") or ""): p
        for p in (analysis_result.get("products") or [])
        if isinstance(p, dict)
    }

    created = 0
    for pid in orphan_pids:
        if pid in existing_pids:
            continue
        product = products_by_id.get(pid)
        if not product:
            continue
        try:
            draft = _minimal_draft(product)
            save_draft(shop, draft)
            created += 1
            logger.info("auto_create_orphan_drafts: created draft for product %s (%s)", pid, shop)
        except Exception as exc:
            logger.warning(
                "auto_create_orphan_drafts: failed for product %s in %s: %s", pid, shop, exc
            )

    return created


def _minimal_draft(product: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal draft pre-populated from the product's best blog idea."""
    pack = product.get("content_test_pack") or {}
    blog_ideas = [
        idea for idea in (pack.get("proposed_blog_ideas") or []) if isinstance(idea, dict)
    ]

    selected_idea: dict[str, Any] = blog_ideas[0] if blog_ideas else {}

    blog_title = (
        selected_idea.get("title")
        or pack.get("proposed_blog_title")
        or f"{product.get('product_title', '')} — guide et conseils"
    )
    intro = selected_idea.get("intro") or pack.get("proposed_blog_intro") or ""
    outline: list[str] = list(selected_idea.get("outline") or pack.get("proposed_blog_outline") or [])

    source_link = build_source_product_link(product, selected_idea)
    raw_links = [source_link] if source_link else []
    raw_links += list(pack.get("recommended_internal_links") or product.get("recommended_internal_links") or [])

    return {
        "product_id": str(product.get("product_id") or ""),
        "product_title": str(product.get("product_title") or ""),
        "product_summary": str(product.get("product_summary") or ""),
        "target_customer": str(product.get("target_customer") or ""),
        "blog_title": str(blog_title),
        "intro": str(intro),
        "summary": str(intro)[:200],
        "outline": outline,
        "sections": [],
        "internal_links": select_blog_internal_links(raw_links),
        "confirmed_facts": list(pack.get("confirmed_facts") or []),
        "tags": [],
        "author_type": "Organization",
        "author_name": "",
    }
