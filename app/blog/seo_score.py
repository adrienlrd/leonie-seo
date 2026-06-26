"""Blog article GEO/SEO readiness score.

Mirrors ``app.geo.readiness.score_product_readiness`` in shape (``readiness_score``
plus weighted ``components``) so the blog editor can render the exact same badge +
breakdown popover the product page uses. The score is an internal editorial
checklist, not a ranking guarantee.
"""

from __future__ import annotations

import re
from typing import Any

# Sweet spot for informative pet-care guides: ~1500 words. Below ~600 Google
# treats the page as thin content, so the length pillar saturates at the target.
_TARGET_WORDS = 1500
_META_MIN = 70
_META_MAX = 155
_MIN_SECTIONS = 3
_MIN_FAQ = 2


def _strip_html(value: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")


def _word_count(draft: dict[str, Any]) -> int:
    parts = [str(draft.get("intro") or "")]
    for section in draft.get("sections") or []:
        if isinstance(section, dict):
            parts.append(str(section.get("direct_answer") or ""))
            parts.append(str(section.get("body") or ""))
    text = _strip_html(" ".join(parts))
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _keyword_score(draft: dict[str, Any]) -> float:
    keyword = str(draft.get("target_keyword") or "").strip().lower()
    if not keyword:
        return 0.0
    title = str(draft.get("blog_title") or "").lower()
    intro = str(draft.get("intro") or "").lower()
    h2_text = " ".join(
        str(s.get("h2") or "").lower()
        for s in (draft.get("sections") or [])
        if isinstance(s, dict)
    )
    checks = [keyword in title, keyword in intro, keyword in h2_text]
    return sum(checks) / len(checks)


def _structure_score(draft: dict[str, Any]) -> float:
    sections = [s for s in (draft.get("sections") or []) if isinstance(s, dict)]
    has_intro = bool(str(draft.get("intro") or "").strip())
    enough_sections = len(sections) >= _MIN_SECTIONS
    answered = sum(1 for s in sections if str(s.get("direct_answer") or "").strip())
    has_answers = answered >= max(1, len(sections) // 2) if sections else False
    checks = [has_intro, enough_sections, has_answers]
    return sum(1 for c in checks if c) / len(checks)


def _meta_score(draft: dict[str, Any]) -> float:
    meta = str(draft.get("meta_description") or "").strip()
    if not meta:
        return 0.0
    return 1.0 if _META_MIN <= len(meta) <= _META_MAX else 0.5


def score_blog_readiness(draft: dict[str, Any]) -> dict[str, Any]:
    """Score one blog draft for editorial / SEO readiness.

    Returns ``readiness_score`` (0-100) and ``components`` keyed by pillar, each
    with a 0-100 ``score`` and its ``weight`` — identical structure to the product
    readiness scorer so the frontend can reuse the same breakdown component.
    """
    words = _word_count(draft)
    length_score = min(words / _TARGET_WORDS, 1.0)
    keyword_score = _keyword_score(draft)
    structure_score = _structure_score(draft)
    meta_score = _meta_score(draft)
    faq = [f for f in (draft.get("faq") or []) if isinstance(f, dict)]
    faq_score = 1.0 if len(faq) >= _MIN_FAQ else (0.5 if faq else 0.0)
    links = [link for link in (draft.get("internal_links") or []) if link]
    links_score = min(len(links) / 2, 1.0)
    image_score = 1.0 if str(draft.get("image_url") or "").strip() else 0.0

    components = {
        "content_length": {"score": round(length_score * 100), "weight": 0.20},
        "keyword": {"score": round(keyword_score * 100), "weight": 0.20},
        "structure": {"score": round(structure_score * 100), "weight": 0.15},
        "meta_description": {"score": round(meta_score * 100), "weight": 0.15},
        "faq": {"score": round(faq_score * 100), "weight": 0.10},
        "internal_links": {"score": round(links_score * 100), "weight": 0.10},
        "image": {"score": round(image_score * 100), "weight": 0.10},
    }
    weighted = sum(c["score"] * c["weight"] for c in components.values())

    return {
        "readiness_score": round(weighted),
        "word_count": words,
        "target_words": _TARGET_WORDS,
        "components": components,
        "note": "Internal editorial readiness score only; it does not guarantee ranking.",
    }
