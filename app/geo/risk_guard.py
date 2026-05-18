"""GEO risk guard for high-value Shopify product pages."""

from __future__ import annotations

from typing import Any

from app.geo.prioritization import prioritize_product


def assess_product_risk(
    product: dict[str, Any],
    shop_domain: str,
    gsc_rows: dict[str, dict[str, Any]],
    *,
    conversion_rate: float = 0.02,
    average_order_value: float = 50.0,
    high_impressions: int = 500,
    top_position: float = 5.0,
) -> dict[str, Any]:
    """Assess whether a product should be protected from risky GEO changes."""
    priority = prioritize_product(
        product,
        shop_domain,
        gsc_rows,
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
    )

    reasons: list[str] = []
    risk_points = 0

    if priority["impressions"] >= high_impressions:
        risk_points += 2
        reasons.append("High GSC impressions: avoid changing a page with meaningful search visibility.")
    if 0 < priority["position"] <= top_position:
        risk_points += 3
        reasons.append("Already ranking near the top: changes may reduce existing visibility.")
    if priority["readiness_score"] >= 75:
        risk_points += 2
        reasons.append("AI Search readiness is already strong: avoid over-optimizing.")
    if priority["revenue_estimate"] >= 25:
        risk_points += 1
        reasons.append("Estimated business upside is meaningful: review changes carefully.")
    if priority["inventory_status"] in {"out_of_stock", "not_active"}:
        risk_points += 2
        reasons.append("Product is not safely sellable right now: avoid content pushes before commerce review.")
    elif priority["inventory_status"] == "low_stock":
        risk_points += 1
        reasons.append("Low stock: avoid driving demand before replenishment decision.")

    if risk_points >= 5:
        guard_status = "protected"
        confirmation_required = True
        recommendation = "Do not apply automatic GEO changes. Require manual review and strong confirmation."
    elif risk_points >= 2:
        guard_status = "review_required"
        confirmation_required = True
        recommendation = "Review before applying. Prefer reversible, low-impact changes."
    else:
        guard_status = "safe"
        confirmation_required = False
        recommendation = "No major risk signal detected. Standard review is still recommended."

    return {
        "product_id": priority["product_id"],
        "handle": priority["handle"],
        "title": priority["title"],
        "guard_status": guard_status,
        "risk_score": min(100, risk_points * 15),
        "confirmation_required": confirmation_required,
        "recommended_policy": recommendation,
        "reasons": reasons or ["No strong risk signal detected."],
        "signals": {
            "readiness_score": priority["readiness_score"],
            "impressions": priority["impressions"],
            "position": priority["position"],
            "revenue_estimate": priority["revenue_estimate"],
            "inventory_status": priority["inventory_status"],
            "confidence": priority["confidence"],
        },
    }


def assess_catalog_risk(
    products: list[dict[str, Any]],
    shop_domain: str,
    gsc_rows: dict[str, dict[str, Any]],
    *,
    top: int = 50,
    conversion_rate: float = 0.02,
    average_order_value: float = 50.0,
) -> dict[str, Any]:
    """Assess GEO change risk across a product catalog."""
    rows = [
        assess_product_risk(
            product,
            shop_domain,
            gsc_rows,
            conversion_rate=conversion_rate,
            average_order_value=average_order_value,
        )
        for product in products
        if product.get("title")
    ]
    rows.sort(key=lambda row: (-row["risk_score"], row["title"]))
    protected = sum(1 for row in rows if row["guard_status"] == "protected")
    review_required = sum(1 for row in rows if row["guard_status"] == "review_required")
    safe = sum(1 for row in rows if row["guard_status"] == "safe")
    return {
        "total": len(rows),
        "summary": {
            "protected": protected,
            "review_required": review_required,
            "safe": safe,
            "confirmation_required": protected + review_required,
            "policy_note": "Protected pages should not receive automatic GEO writes without manual review and strong confirmation.",
        },
        "rows": rows[:top],
    }
