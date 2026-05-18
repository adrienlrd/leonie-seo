"""Weekly GEO action assistant."""

from __future__ import annotations

from typing import Any

from app.geo.prioritization import prioritize_catalog


def _weekly_message(row: dict[str, Any]) -> str:
    revenue = row.get("revenue_estimate", 0.0)
    impressions = row.get("impressions", 0)
    score = row.get("readiness_score", 0)
    return (
        f"Focus this week: {row['action_label']} for {row['title']}. "
        f"The page has readiness {score}/100, {impressions} GSC impressions, "
        f"and an estimated upside of {revenue:.2f}."
    )


def _next_steps(row: dict[str, Any]) -> list[str]:
    action = row.get("action_type")
    if action == "enrich_product_facts":
        return [
            "Confirm missing material, origin, size, warranty or care facts with the merchant.",
            "Add only verified facts to product content, FAQ or structured data.",
            "Recompute AI Search Readiness after enrichment.",
        ]
    if action == "add_answer_blocks":
        return [
            "Draft short FAQ or answer blocks from confirmed product facts.",
            "Review answers manually before publishing.",
            "Link the answers from relevant product or collection pages.",
        ]
    if action == "add_trust_proofs":
        return [
            "Collect verified proof: origin, warranty, returns, reviews or certifications.",
            "Avoid claims that are not explicitly confirmed.",
            "Add the strongest proof to product copy and schema where appropriate.",
        ]
    if action == "improve_schema":
        return [
            "Check product name, description, image, offer and SKU/material coverage.",
            "Preview JSON-LD before any theme or app extension change.",
            "Validate structured data after publishing.",
        ]
    if action == "improve_seo_copy":
        return [
            "Rewrite the SEO title and meta description around the main product intent.",
            "Keep copy specific and consistent with confirmed facts.",
            "Preview the change in dry-run before applying.",
        ]
    return [
        "Review the product data and confirm the missing business signals.",
        "Prioritize safe, reversible changes first.",
        "Measure the page again after the next crawl and GSC import.",
    ]


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "weekly_message": _weekly_message(row),
        "next_steps": _next_steps(row),
    }


def build_weekly_actions(
    products: list[dict[str, Any]],
    shop_domain: str,
    gsc_rows: dict[str, dict[str, Any]],
    *,
    limit: int = 3,
    conversion_rate: float = 0.02,
    average_order_value: float = 50.0,
    position_improvement: float = 2.0,
) -> dict[str, Any]:
    """Select the top weekly GEO actions from revenue-aware priorities."""
    priorities = prioritize_catalog(
        products,
        shop_domain,
        gsc_rows,
        top=max(limit * 4, 12),
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
        position_improvement=position_improvement,
    )

    selected: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for row in priorities["rows"]:
        if len(selected) >= limit:
            break
        if row["action_type"] in seen_actions and len(selected) < min(limit, 2):
            continue
        seen_actions.add(row["action_type"])
        selected.append(_decorate(row))

    if len(selected) < limit:
        existing = {row["product_id"] for row in selected}
        for row in priorities["rows"]:
            if len(selected) >= limit:
                break
            if row["product_id"] in existing:
                continue
            selected.append(_decorate(row))

    return {
        "total_candidates": priorities["total"],
        "summary": {
            "weekly_actions": len(selected),
            "estimated_revenue": round(sum(row["revenue_estimate"] for row in selected), 2),
            "estimated_clicks": round(sum(row["clicks_gain_estimate"] for row in selected), 1),
            "high_confidence_actions": sum(1 for row in selected if row["confidence"] == "high"),
            "note": "Weekly actions are selected from estimated priorities; review before applying any change.",
        },
        "actions": selected,
    }
