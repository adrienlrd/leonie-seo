"""Prompt formatting for competitor crawl insights."""

from __future__ import annotations

from typing import Any


def format_competitor_crawl_for_prompt(insights: dict) -> str:
    """Return a structural benchmark block for Pass 2.

    Beyond aggregate rates, surface the actionable detail crawled from the top
    competitor pages — real titles, meta descriptions, H2 subtopics, target
    length and featured snippet — so content generation (meta, FAQ, blog,
    description) can take inspiration without copying competitor wording.
    """
    if not isinstance(insights, dict) or not insights.get("sample_size"):
        return ""
    sample_size = int(insights.get("sample_size", 0) or 0)
    patterns = (
        insights.get("dominant_patterns")
        if isinstance(insights.get("dominant_patterns"), dict)
        else {}
    )
    gaps = insights.get("merchant_gaps") if isinstance(insights.get("merchant_gaps"), list) else []
    top_urls = insights.get("top_urls") if isinstance(insights.get("top_urls"), list) else []

    lines = ["COMPETITOR CRAWL INSIGHTS:"]
    _append_rate_line(
        lines,
        patterns,
        "has_faq_block_rate",
        sample_size,
        "top competitor pages have visible FAQ blocks",
    )
    if patterns.get("median_word_count"):
        lines.append(
            f"- Median word count: {int(patterns['median_word_count'])} "
            "— vise cette longueur pour proposed_product_description."
        )
    if patterns.get("median_internal_links"):
        lines.append(f"- Median internal links: {int(patterns['median_internal_links'])}.")
    _append_rate_line(
        lines, patterns, "has_product_schema_rate", sample_size, "pages expose Product schema"
    )
    _append_rate_line(
        lines, patterns, "has_breadcrumb_schema_rate", sample_size, "pages expose Breadcrumb schema"
    )
    for gap in gaps[:4]:
        if not isinstance(gap, dict):
            continue
        lines.append(
            f"- Merchant gap: {gap.get('gap', '')} -> prioritize {gap.get('action_type', '')}."
        )

    titles = _collect(top_urls, lambda u: _get(u, "seo", "title") or u.get("title"), limit=3)
    if titles:
        lines.append(
            "\nTITRES SEO CONCURRENTS (inspire proposed_meta_title — différencie, ne copie pas):"
        )
        lines.extend(f'- "{t}"' for t in titles)

    metas = _collect(top_urls, lambda u: _get(u, "seo", "meta_description"), limit=3)
    if metas:
        lines.append("\nMETA DESCRIPTIONS CONCURRENTES (inspire proposed_meta_description):")
        lines.extend(f'- "{m}"' for m in metas)

    h2s = _collect_many(top_urls, lambda u: _get(u, "structure", "h2_texts") or [], limit=8)
    if h2s:
        lines.append(
            "\nSOUS-THÈMES / H2 CONCURRENTS (inspire proposed_blog_outline + structure description):"
        )
        lines.extend(f"- {h}" for h in h2s)

    snippet = _first(top_urls, lambda u: _get(u, "serp", "featured_snippet"))
    if snippet:
        lines.append(
            "\nEXTRAIT REPRIS PAR GOOGLE (featured snippet — inspire proposed_geo_answer_block):"
        )
        lines.append(f'- "{snippet}"')

    lines.append(
        "\nUse these patterns as structural inspiration only. Do not copy competitor text."
    )
    lines.append("Do not infer unverified product facts from competitors.")
    return "\n".join(line for line in lines if line.strip() or line == "")


def _get(url: dict, section: str, key: str) -> str:
    block = url.get(section) if isinstance(url, dict) else None
    if isinstance(block, dict):
        value = block.get(key)
        if isinstance(value, str):
            return value.strip()
        return value
    return ""


def _collect(top_urls: list, getter, *, limit: int) -> list[str]:
    """Deduplicated, non-empty single values across top_urls, capped at `limit`."""
    out: list[str] = []
    for url in top_urls:
        value = getter(url)
        text = str(value).strip() if value else ""
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _collect_many(top_urls: list, getter, *, limit: int) -> list[str]:
    """Deduplicated, non-empty values from list-valued fields across top_urls."""
    out: list[str] = []
    for url in top_urls:
        for value in getter(url) or []:
            text = str(value).strip()
            if text and text not in out:
                out.append(text)
            if len(out) >= limit:
                return out
    return out


def _first(top_urls: list, getter) -> str:
    for url in top_urls:
        value = getter(url)
        text = str(value).strip() if value else ""
        if text:
            return text
    return ""


def _append_rate_line(
    lines: list[str],
    patterns: dict[str, Any],
    key: str,
    sample_size: int,
    label: str,
) -> None:
    rate = float(patterns.get(key, 0) or 0)
    if rate <= 0 or sample_size <= 0:
        return
    count = round(rate * sample_size)
    lines.append(f"- {count}/{sample_size} {label}.")
