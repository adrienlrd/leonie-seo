"""Prompt formatting for competitor crawl insights."""

from __future__ import annotations

from typing import Any


def format_competitor_crawl_for_prompt(insights: dict) -> str:
    """Return a short structural benchmark block for Pass 2."""
    if not isinstance(insights, dict) or not insights.get("sample_size"):
        return ""
    sample_size = int(insights.get("sample_size", 0) or 0)
    patterns = (
        insights.get("dominant_patterns")
        if isinstance(insights.get("dominant_patterns"), dict)
        else {}
    )
    gaps = insights.get("merchant_gaps") if isinstance(insights.get("merchant_gaps"), list) else []
    lines = ["COMPETITOR CRAWL INSIGHTS:"]
    _append_rate_line(
        lines,
        patterns,
        "has_faq_block_rate",
        sample_size,
        "top competitor pages have visible FAQ blocks",
    )
    if patterns.get("median_word_count"):
        lines.append(f"- Median word count: {int(patterns['median_word_count'])}.")
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
    lines.append("Use these patterns as structural inspiration only. Do not copy competitor text.")
    lines.append("Do not infer unverified product facts from competitors.")
    return "\n".join(line for line in lines if line.strip())


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
