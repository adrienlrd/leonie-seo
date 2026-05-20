"""Revenue-aware GEO prioritization for Shopify products."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.geo.readiness import score_product_readiness
from app.impact.calculator import estimate_ctr
from app.snapshot.scope import filter_products_by_scope, summarize_product_scopes


def _edge_nodes(container: Any) -> list[dict[str, Any]]:
    if isinstance(container, dict) and isinstance(container.get("edges"), list):
        return [edge.get("node", {}) for edge in container["edges"] if isinstance(edge, dict)]
    if isinstance(container, list):
        return [item for item in container if isinstance(item, dict)]
    return []


def _first_variant(product: dict[str, Any]) -> dict[str, Any]:
    nodes = _edge_nodes(product.get("variants"))
    return nodes[0] if nodes else {}


def _price(product: dict[str, Any]) -> float | None:
    variant = _first_variant(product)
    try:
        return float(variant.get("price"))
    except (TypeError, ValueError):
        return None


def _inventory_signal(product: dict[str, Any]) -> tuple[str, float]:
    variant = _first_variant(product)
    quantity = variant.get("inventoryQuantity", variant.get("inventory_quantity"))
    status = str(product.get("status") or "").upper()
    if status and status != "ACTIVE":
        return "not_active", 0.2
    if quantity is None:
        return "unknown", 0.8
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return "unknown", 0.8
    if qty <= 0:
        return "out_of_stock", 0.1
    if qty <= 3:
        return "low_stock", 0.45
    return "in_stock", 1.0


def _product_url(shop_domain: str, handle: str) -> str:
    return f"https://{shop_domain}/products/{handle}".rstrip("/")


def _path(value: str) -> str:
    parsed = urlparse(value)
    return (parsed.path if parsed.scheme else value).rstrip("/") or "/"


def _gsc_for_product(
    product: dict[str, Any],
    shop_domain: str,
    gsc_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    handle = str(product.get("handle") or "")
    url = _product_url(shop_domain, handle)
    if url in gsc_rows:
        return gsc_rows[url]
    target_path = _path(url)
    for row_url, row in gsc_rows.items():
        if _path(row_url) == target_path:
            return row
    return {}


def _click_gain_estimate(impressions: int, position: float, improvement: float) -> float:
    if impressions <= 0:
        return 0.0
    current = position if position > 0 else 20.0
    improved = max(1.0, current - improvement)
    return round(max(0.0, impressions * (estimate_ctr(improved) - estimate_ctr(current))), 1)


def _primary_action(readiness: dict[str, Any]) -> tuple[str, str, str, int]:
    components = readiness["components"]
    ordered = sorted(
        components.items(),
        key=lambda item: item[1]["score"] if isinstance(item[1], dict) else item[1],
    )
    weakest, value = ordered[0]
    score_val = value["score"] if isinstance(value, dict) else int(value)
    action_map = {
        "facts": ("enrich_product_facts", "Enrichir les faits produit", "high"),
        "schema": ("improve_schema", "Améliorer les données structurées", "medium"),
        "answerability": ("add_answer_blocks", "Ajouter FAQ et réponses IA", "medium"),
        "trust": ("add_trust_proofs", "Ajouter preuves de confiance vérifiées", "medium"),
        "seo": ("improve_seo_copy", "Améliorer title, meta et description", "low"),
        "commerce": ("review_commerce_data", "Compléter prix, stock ou statut", "medium"),
    }
    action_type, label, effort = action_map.get(weakest, ("review_product", "Revoir la page produit", "medium"))
    effort_cost = {"low": 1, "medium": 2, "high": 3}[effort]
    return action_type, label, effort, max(0, 100 - score_val) // effort_cost


def prioritize_product(
    product: dict[str, Any],
    shop_domain: str,
    gsc_rows: dict[str, dict[str, Any]],
    *,
    conversion_rate: float = 0.02,
    average_order_value: float = 50.0,
    position_improvement: float = 2.0,
) -> dict[str, Any]:
    """Build one revenue-aware GEO priority row."""
    readiness = score_product_readiness(product)
    gsc = _gsc_for_product(product, shop_domain, gsc_rows)
    impressions = int(gsc.get("impressions", 0) or 0)
    clicks = int(gsc.get("clicks", 0) or 0)
    position = float(gsc.get("position", 0.0) or 0.0)
    click_gain = _click_gain_estimate(impressions, position, position_improvement)
    price = _price(product)
    order_value = price if price and price > 0 else average_order_value
    revenue_estimate = round(click_gain * conversion_rate * order_value, 2)
    inventory_status, stock_multiplier = _inventory_signal(product)

    action_type, action_label, effort, gap_score = _primary_action(readiness)
    readiness_gap = max(0, 100 - readiness["readiness_score"])
    traffic_score = min(100, impressions / 10)
    revenue_score = min(100, revenue_estimate * 2)
    priority_score = round(
        (0.35 * readiness_gap + 0.25 * traffic_score + 0.25 * revenue_score + 0.15 * gap_score)
        * stock_multiplier
    )

    if gsc and price:
        confidence = "high"
    elif gsc:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "product_id": product.get("id", ""),
        "handle": product.get("handle", ""),
        "title": product.get("title", ""),
        "action_type": action_type,
        "action_label": action_label,
        "priority_score": priority_score,
        "readiness_score": readiness["readiness_score"],
        "readiness_gap": readiness_gap,
        "effort": effort,
        "risk": "medium" if readiness["readiness_score"] >= 75 else "low",
        "confidence": confidence,
        "inventory_status": inventory_status,
        "price": price,
        "impressions": impressions,
        "clicks": clicks,
        "position": round(position, 2),
        "clicks_gain_estimate": click_gain,
        "revenue_estimate": revenue_estimate,
        "reason": (
            f"{action_label} because readiness is {readiness['readiness_score']}/100 "
            f"with {impressions} GSC impressions and estimated revenue upside of {revenue_estimate:.2f}."
        ),
        "recommendations": readiness["recommendations"][:3],
        "estimated": True,
    }


def prioritize_catalog(
    products: list[dict[str, Any]],
    shop_domain: str,
    gsc_rows: dict[str, dict[str, Any]],
    *,
    top: int = 20,
    conversion_rate: float = 0.02,
    average_order_value: float = 50.0,
    position_improvement: float = 2.0,
    scope: str = "active",
) -> dict[str, Any]:
    """Prioritize products by GEO gap and estimated business upside."""
    scoped_products = filter_products_by_scope(products, scope)
    rows = [
        prioritize_product(
            product,
            shop_domain,
            gsc_rows,
            conversion_rate=conversion_rate,
            average_order_value=average_order_value,
            position_improvement=position_improvement,
        )
        for product in scoped_products
        if product.get("title")
    ]
    rows.sort(key=lambda item: (-item["priority_score"], -item["revenue_estimate"], item["title"]))
    limited = rows[:top]
    return {
        "total": len(rows),
        "scope": summarize_product_scopes(products, scope),
        "summary": {
            "avg_priority_score": round(sum(row["priority_score"] for row in rows) / len(rows)) if rows else 0,
            "total_revenue_estimate": round(sum(row["revenue_estimate"] for row in rows), 2),
            "high_confidence_actions": sum(1 for row in rows if row["confidence"] == "high"),
            "gsc_connected": bool(gsc_rows),
            "estimated": True,
            "note": "Revenue estimates use GSC impressions, CTR curve assumptions and conversion/AOV fallbacks; they are not promises.",
        },
        "rows": limited,
    }
