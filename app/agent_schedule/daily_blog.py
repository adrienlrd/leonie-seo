"""One blog article per day, chosen for the traffic it can bring.

Orchestration only. The ranking lives in `app.blog.traffic_score`, the draft
assembly (cover image from the product, link back to the product, CTA, JSON-LD)
in `app.api.blog`, and the writing in `app.blog.section_generator` — this module
decides *which* idea ships today and drives the existing pieces.

Opt-in per shop: the ``blog_article`` auto-publish scope. Off by default, so no
merchant starts publishing daily without asking for it.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.billing.quotas import QuotaExceeded, check_quota, record_usage
from app.blog.idea_generator import build_blog_idea_suggestions
from app.blog.store import list_drafts, save_draft
from app.blog.traffic_score import load_gsc_index, rank_blog_ideas
from app.language import get_shop_language
from app.learning.models import LearningMode
from app.learning.store import get_settings
from app.market_analysis.jobs import load_latest_result

logger = logging.getLogger(__name__)

BLOG_SCOPE = "blog_article"


def _normalized_title(title: str) -> str:
    return " ".join(str(title or "").split()).casefold()


def _already_written(shop: str) -> set[str]:
    """Titles already drafted or published — never write the same article twice."""
    try:
        return {_normalized_title(d.get("blog_title")) for d in list_drafts(shop)}
    except Exception as exc:  # noqa: BLE001 — a missing draft store must not block
        logger.warning("daily_blog: could not list drafts for %s: %s", shop, exc)
        return set()


def _published_today(shop: str, today: date) -> bool:
    try:
        drafts = list_drafts(shop)
    except Exception:  # noqa: BLE001
        return False
    for draft in drafts:
        if draft.get("status") != "published_to_shopify":
            continue
        stamp = str(draft.get("updated_at") or "")[:10]
        if stamp == today.isoformat():
            return True
    return False


def _candidate_ideas(shop: str, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Every idea the app can propose, from both generators, tagged with its product."""
    products = [p for p in (analysis.get("products") or []) if isinstance(p, dict)]
    ideas: list[dict[str, Any]] = []
    for product in products:
        pack = product.get("content_test_pack") or {}
        for idea in pack.get("proposed_blog_ideas") or []:
            if isinstance(idea, dict) and idea.get("title"):
                ideas.append({**idea, "product_id": str(product.get("product_id") or "")})
    ideas += build_blog_idea_suggestions(
        products=products,
        competitor_signals=analysis.get("competitor_signals") or [],
        language=get_shop_language(shop),
    )
    return ideas


def _write_sections(shop: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
    from app.blog.section_generator import generate_all_sections  # noqa: PLC0415

    return generate_all_sections(
        blog_title=str(draft.get("blog_title") or ""),
        h2_questions=[str(q) for q in (draft.get("outline") or []) if str(q).strip()],
        product_title=str(draft.get("product_title") or ""),
        product_summary=str(draft.get("product_summary") or ""),
        confirmed_facts=list(draft.get("confirmed_facts") or []),
        target_customer=str(draft.get("target_customer") or ""),
        keywords=str(draft.get("target_keyword") or ""),
        shop=shop,
    )


def run_daily_blog(
    shop: str,
    *,
    access_token: str | None,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Write and publish today's article for `shop`. Returns a status dict.

    Never raises: a blog failure must not take the daily learning cycle down
    with it.
    """
    current = now or datetime.now(UTC)
    settings = get_settings(shop, db_path=db_path)
    if settings.mode != LearningMode.AUTO_APPLY:
        return {"status": "skipped", "reason": "manual_mode"}
    if BLOG_SCOPE not in settings.auto_publish_scopes:
        return {"status": "skipped", "reason": "scope_disabled"}
    if not access_token:
        return {"status": "skipped", "reason": "no_access_token"}
    if _published_today(shop, current.date()):
        return {"status": "skipped", "reason": "already_published_today"}

    try:
        check_quota(shop, "blog", db_path)
    except QuotaExceeded:
        return {"status": "skipped", "reason": "blog_quota_exceeded"}

    analysis = load_latest_result(shop)
    if not analysis:
        return {"status": "skipped", "reason": "no_market_analysis"}

    ideas = _candidate_ideas(shop, analysis)
    written = _already_written(shop)
    ideas = [i for i in ideas if _normalized_title(i.get("title")) not in written]
    if not ideas:
        return {"status": "skipped", "reason": "no_new_idea"}

    products_by_id = {
        str(p.get("product_id") or ""): p
        for p in (analysis.get("products") or [])
        if isinstance(p, dict)
    }
    gsc_index, window_days = load_gsc_index(shop)
    ranked = rank_blog_ideas(
        ideas, products_by_id=products_by_id, gsc_index=gsc_index, window_days=window_days
    )
    best = ranked[0]
    product_id = str(best.get("product_id") or "")
    if not product_id:
        return {"status": "skipped", "reason": "idea_without_product"}

    try:
        from app.api.blog import _draft_from_product, publish_draft_to_shopify  # noqa: PLC0415

        draft = _draft_from_product(shop, product_id, idea_override=best)
        draft["sections"] = _write_sections(shop, draft)
        draft["traffic_score"] = best["traffic_score"]
        saved = save_draft(shop, draft)
        published = publish_draft_to_shopify(
            shop, access_token, str(saved["id"]), published=True
        )
    except Exception as exc:  # noqa: BLE001 — reported, never fatal for the cycle
        logger.exception("daily_blog failed for %s", shop)
        return {"status": "error", "error": str(exc)}

    record_usage(shop, "blog", db_path)
    article = published.get("article") or {}
    return {
        "status": "published",
        "draft_id": str(saved["id"]),
        "title": draft.get("blog_title"),
        "product_id": product_id,
        "article_handle": article.get("handle"),
        "traffic_score": best["traffic_score"],
    }
