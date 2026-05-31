"""Internal links for generated blog articles.

Market analysis already computes deterministic link recommendations per product.
This module adapts those recommendations to blog drafts and renders a compact
HTML block that Shopify can store in the draft article body.
"""

from __future__ import annotations

from html import escape
from typing import Any

_MAX_BLOG_LINKS = 5


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
