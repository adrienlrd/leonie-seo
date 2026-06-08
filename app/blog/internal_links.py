"""Internal links for generated blog articles.

Market analysis already computes deterministic link recommendations per product.
This module adapts those recommendations to blog drafts and renders a compact
HTML block that Shopify can store in the draft article body.
"""

from __future__ import annotations

from html import escape
from typing import Any

_MAX_BLOG_LINKS = 5
_DYNAMIC_SIM_THRESHOLD = 0.3
_CLUSTER_SIM_THRESHOLD = 0.5


def build_source_product_link(
    product: dict[str, Any],
    selected_idea: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build the canonical blog→product link for a draft (public version)."""
    selected_idea = selected_idea or {}
    target_url = str(product.get("product_url") or "").strip()
    if not target_url:
        handle = str(product.get("product_handle") or "").strip()
        target_url = f"/products/{handle}" if handle else ""
    if not target_url:
        return None
    title = str(product.get("product_title") or "").strip()
    anchor = str(selected_idea.get("target_keyword") or "").strip() or title
    if not anchor:
        return None
    return {
        "target_url": target_url,
        "target_title": title or anchor,
        "anchors": [anchor],
        "reason": "source_product",
    }


def select_blog_internal_links(
    recommendations: list[dict[str, Any]] | None,
    *,
    max_links: int = _MAX_BLOG_LINKS,
) -> list[dict[str, str]]:
    """Return safe, deduplicated links for a blog draft."""
    selected: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for recommendation in recommendations or []:
        if not isinstance(recommendation, dict):
            continue
        url = str(recommendation.get("target_url") or "").strip()
        if not url or url in seen_urls:
            continue
        explicit_anchor = str(recommendation.get("anchor") or "").strip()
        anchors = [
            str(anchor).strip()
            for anchor in (recommendation.get("anchors") or [])
            if str(anchor).strip()
        ]
        title = str(recommendation.get("target_title") or "").strip()
        label = explicit_anchor or (anchors[0] if anchors else title)
        if not label:
            continue
        selected.append(
            {
                "target_url": url,
                "anchor": label,
                "target_title": title or label,
                "reason": str(recommendation.get("reason") or ""),
            }
        )
        seen_urls.add(url)
        if len(selected) >= max(0, max_links):
            break
    return selected


def suggest_links_for_article(
    *,
    keywords: list[str],
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    other_drafts: list[dict[str, Any]],
    exclude_urls: set[str] | None = None,
    max_links: int = _MAX_BLOG_LINKS,
) -> list[dict[str, str]]:
    """Return ranked link suggestions matching ``keywords`` from the article.

    Matches against products (via primary keyword), collections (via title), and
    other blog drafts (via title). Uses Jaccard similarity on normalized tokens.
    Lower threshold than the market analysis engine (0.3 vs 0.5) to stay useful
    even for short article keyword lists.
    """
    from app.market_analysis.keyword_normalization import (
        jaccard_similarity,
        tokenize_normalized,
    )

    exclude = exclude_urls or set()
    article_tokens = tokenize_normalized(" ".join(keywords))
    if not article_tokens:
        return []

    candidates: list[tuple[float, dict[str, str]]] = []

    for product in products:
        primary_kw = next(
            (kw for kw in (product.get("seo_keywords") or []) if isinstance(kw, dict) and kw.get("target_role") == "primary"),
            None,
        )
        if not primary_kw:
            continue
        query = str(primary_kw.get("query") or "").strip()
        if not query:
            continue
        sim = jaccard_similarity(article_tokens, tokenize_normalized(query))
        if sim < _DYNAMIC_SIM_THRESHOLD:
            continue
        url = str(product.get("product_url") or "").strip()
        if not url:
            handle = str(product.get("product_handle") or "").strip()
            url = f"/products/{handle}" if handle else ""
        if not url or url in exclude:
            continue
        candidates.append((sim, {
            "target_url": url,
            "anchor": query,
            "target_title": str(product.get("product_title") or ""),
            "reason": "sibling_product",
        }))

    for col in collections:
        handle = str(col.get("handle") or "").strip()
        title = str(col.get("title") or "").strip()
        if not handle or not title:
            continue
        url = f"/collections/{handle}"
        if url in exclude:
            continue
        sim = jaccard_similarity(article_tokens, tokenize_normalized(title))
        if sim < _DYNAMIC_SIM_THRESHOLD:
            continue
        candidates.append((sim, {
            "target_url": url,
            "anchor": title,
            "target_title": title,
            "reason": "collection_parent",
        }))

    for draft in other_drafts:
        title = str(draft.get("blog_title") or "").strip()
        handle = str(draft.get("shopify_article_handle") or "").strip()
        if not title:
            continue
        url = f"/blogs/blog/{handle}" if handle else f"#draft-{draft.get('id', '')}"
        if url in exclude:
            continue
        sim = jaccard_similarity(article_tokens, tokenize_normalized(title))
        if sim < _DYNAMIC_SIM_THRESHOLD:
            continue
        candidates.append((sim, {
            "target_url": url,
            "anchor": title,
            "target_title": title,
            "reason": "related_article",
        }))

    candidates.sort(key=lambda c: c[0], reverse=True)
    seen_urls: set[str] = set()
    result: list[dict[str, str]] = []
    for _, link in candidates:
        if link["target_url"] in seen_urls:
            continue
        seen_urls.add(link["target_url"])
        result.append(link)
        if len(result) >= max_links:
            break
    return result


def suggest_cluster_links(
    *,
    current_keyword: str,
    current_outline: list[str],
    other_drafts: list[dict[str, Any]],
    exclude_urls: set[str] | None = None,
    threshold: float = _CLUSTER_SIM_THRESHOLD,
) -> list[dict[str, str]]:
    """Suggest hub-and-spoke links inside a topic cluster of blog drafts.

    Groups the current article with ``other_drafts`` whose ``target_keyword``
    is similar (Jaccard on normalized tokens — same mechanism as
    `keyword_normalization.build_clusters`). The member with the richest
    outline is the cluster's pillar. Siblings get a single suggested link up
    to the pillar (``cluster_pillar``); the pillar gets one suggested link
    down to each sibling (``cluster_sibling``) — the standard hub-and-spoke
    pattern that spreads link equity without the merchant picking anchors.
    """
    from app.market_analysis.keyword_normalization import build_clusters

    keyword = (current_keyword or "").strip()
    if not keyword:
        return []
    exclude = exclude_urls or set()

    candidates: list[dict[str, Any]] = [
        {"query": keyword, "_self": True, "_outline_len": len(current_outline or [])}
    ]
    for draft in other_drafts:
        query = str(draft.get("target_keyword") or "").strip()
        if not query:
            continue
        candidates.append(
            {
                "query": query,
                "_self": False,
                "_draft": draft,
                "_outline_len": len(draft.get("outline") or []),
            }
        )

    cluster = next(
        (
            c
            for c in build_clusters(candidates, threshold=threshold)
            if len(c["members"]) >= 2 and any(m.get("_self") for m in c["members"])
        ),
        None,
    )
    if not cluster:
        return []

    members = cluster["members"]
    pillar = max(members, key=lambda m: m["_outline_len"])
    is_self_pillar = bool(pillar.get("_self"))

    def _link_to(member: dict[str, Any], reason: str) -> dict[str, str] | None:
        draft = member.get("_draft")
        title = str((draft or {}).get("blog_title") or "").strip()
        if not draft or not title:
            return None
        handle = str(draft.get("shopify_article_handle") or "").strip()
        url = f"/blogs/blog/{handle}" if handle else f"#draft-{draft.get('id', '')}"
        if url in exclude:
            return None
        return {"target_url": url, "anchor": title, "target_title": title, "reason": reason}

    if is_self_pillar:
        links = [_link_to(m, "cluster_sibling") for m in members if not m.get("_self")]
    else:
        links = [_link_to(pillar, "cluster_pillar")]
    return [link for link in links if link]


def render_internal_links_html(
    links: list[dict[str, Any]] | None,
    *,
    heading: str = "À lire aussi",
) -> str:
    """Render internal links as a Shopify-safe HTML block."""
    cleaned = select_blog_internal_links(links)
    if not cleaned:
        return ""
    items: list[str] = []
    for link in cleaned:
        url = escape(link["target_url"], quote=True)
        anchor = escape(link["anchor"])
        title = escape(link.get("target_title") or link["anchor"], quote=True)
        items.append(f'<li><a href="{url}" title="{title}">{anchor}</a></li>')
    return (
        '<aside class="leonie-internal-links">'
        f"<h2>{escape(heading)}</h2>"
        "<ul>" + "".join(items) + "</ul>"
        "</aside>"
    )
