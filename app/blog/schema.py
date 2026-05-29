"""JSON-LD generators (Article + FAQPage) for the blog editor.

Article schema unlocks Google sitelinks/author/dates display. FAQPage is no longer
shown as a Google rich result (dropped May 2026) but remains a strong GEO signal:
ChatGPT, Perplexity, Gemini and Google AI Overviews still parse it to extract
quotable Q/A pairs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_article_jsonld(
    *,
    headline: str,
    description: str,
    url: str,
    published_at: str | None = None,
    modified_at: str | None = None,
    author_type: str = "Organization",
    author_name: str = "",
    author_url: str | None = None,
    publisher_name: str = "",
    publisher_logo_url: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    """Build the Article JSON-LD payload.

    ``author_type`` is ``Organization`` (brand-credited, default) or ``Person`` when
    the merchant credits a real human — Person strengthens E-E-A-T.
    """
    if author_type not in ("Organization", "Person"):
        author_type = "Organization"
    published = published_at or _now_iso()
    modified = modified_at or published

    article: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": description,
        "datePublished": published,
        "dateModified": modified,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "author": {"@type": author_type, "name": author_name or publisher_name or "Editorial team"},
        "publisher": {"@type": "Organization", "name": publisher_name or author_name or ""},
    }
    if author_url:
        article["author"]["url"] = author_url
    if publisher_logo_url:
        article["publisher"]["logo"] = {"@type": "ImageObject", "url": publisher_logo_url}
    if image_url:
        article["image"] = image_url
    return article


def build_faqpage_jsonld(qa_pairs: list[dict[str, str]]) -> dict[str, Any] | None:
    """Build the FAQPage JSON-LD from question/answer pairs (kept as a GEO signal)."""
    cleaned: list[dict[str, Any]] = []
    for pair in qa_pairs or []:
        if not isinstance(pair, dict):
            continue
        question = str(pair.get("question") or pair.get("q") or "").strip()
        answer = str(pair.get("answer") or pair.get("a") or "").strip()
        if not question or not answer:
            continue
        cleaned.append(
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )
    if not cleaned:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": cleaned,
    }


def render_jsonld_blocks(*blocks: dict[str, Any] | None) -> str:
    """Render one or more JSON-LD dicts as ``<script>`` tags, in order."""
    parts: list[str] = []
    for block in blocks:
        if not block:
            continue
        # ``ensure_ascii=False`` keeps French text readable in page source.
        encoded = json.dumps(block, ensure_ascii=False, separators=(",", ":"))
        parts.append(f'<script type="application/ld+json">{encoded}</script>')
    return "\n".join(parts)
