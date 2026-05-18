"""AI Search readiness scoring for Shopify products."""

from __future__ import annotations

from typing import Any

from app.geo.facts import analyze_product_facts

_SEO_TITLE_MIN = 30
_SEO_TITLE_MAX = 70
_SEO_DESC_MIN = 70
_SEO_DESC_MAX = 160


def _edge_count(container: Any) -> int:
    if isinstance(container, dict) and isinstance(container.get("edges"), list):
        return len(container["edges"])
    if isinstance(container, list):
        return len(container)
    return 0


def _first_variant(product: dict[str, Any]) -> dict[str, Any]:
    variants = product.get("variants")
    if isinstance(variants, dict) and isinstance(variants.get("edges"), list):
        edges = variants["edges"]
        if edges and isinstance(edges[0], dict):
            return edges[0].get("node", {}) or {}
    if isinstance(variants, list) and variants:
        return variants[0]
    return {}


def _description(product: dict[str, Any]) -> str:
    return str(
        product.get("descriptionHtml")
        or product.get("body_html")
        or product.get("description")
        or ""
    ).strip()


def _seo_score(product: dict[str, Any]) -> tuple[float, list[str]]:
    seo = product.get("seo") or {}
    title = str(seo.get("title") or "").strip()
    description = str(seo.get("description") or "").strip()
    checks = []
    recommendations: list[str] = []

    title_ok = _SEO_TITLE_MIN <= len(title) <= _SEO_TITLE_MAX
    desc_ok = _SEO_DESC_MIN <= len(description) <= _SEO_DESC_MAX
    handle_ok = bool(product.get("handle"))
    body_ok = len(_description(product).split()) >= 40

    checks.extend([title_ok, desc_ok, handle_ok, body_ok])

    if not title_ok:
        recommendations.append("Write a clear SEO title between 30 and 70 characters.")
    if not desc_ok:
        recommendations.append("Write a helpful meta description between 70 and 160 characters.")
    if not body_ok:
        recommendations.append("Add a richer product description with concrete usage details.")

    return round(sum(checks) / len(checks), 2), recommendations


def _schema_score(product: dict[str, Any], fact_keys: set[str]) -> tuple[float, list[str]]:
    variant = _first_variant(product)
    checks = {
        "name": bool(product.get("title")),
        "description": bool(_description(product)),
        "image": _edge_count(product.get("images")) > 0,
        "offer": bool(variant.get("price")),
        "sku_or_material": bool(variant.get("sku")) or "materials" in fact_keys,
    }
    recommendations: list[str] = []
    if not checks["image"]:
        recommendations.append("Add at least one product image for richer structured data.")
    if not checks["offer"]:
        recommendations.append("Expose price data in the Shopify snapshot for Product offers.")
    if not checks["sku_or_material"]:
        recommendations.append("Add SKU or material details to strengthen product structured data.")
    return round(sum(1 for ok in checks.values() if ok) / len(checks), 2), recommendations


def _answer_score(product: dict[str, Any], fact_keys: set[str]) -> tuple[float, list[str]]:
    description_words = len(_description(product).split())
    answer_keys = {
        "materials",
        "care",
        "dimensions",
        "compatibility",
        "size_recommendation",
        "targets",
        "properties",
    }
    present_answer_facts = len(answer_keys & fact_keys)
    score = round(min((present_answer_facts / 5) * 0.75 + min(description_words / 120, 1) * 0.25, 1), 2)
    recommendations: list[str] = []
    if present_answer_facts < 3:
        recommendations.append("Add factual answers about material, sizing, care, compatibility or use cases.")
    if description_words < 80:
        recommendations.append("Expand the product copy so AI answers have enough verified context.")
    return score, recommendations


def _trust_score(fact_keys: set[str]) -> tuple[float, list[str]]:
    trust_keys = {"certifications", "origins", "warranty", "delivery", "returns"}
    present = trust_keys & fact_keys
    score = round(len(present) / len(trust_keys), 2)
    recommendations: list[str] = []
    if "certifications" not in fact_keys:
        recommendations.append("Confirm certifications or state that none apply before generating claims.")
    if "origins" not in fact_keys:
        recommendations.append("Confirm manufacturing origin before using it in GEO content.")
    if "warranty" not in fact_keys:
        recommendations.append("Add warranty or guarantee information if it is actually offered.")
    return score, recommendations


def _commerce_score(product: dict[str, Any]) -> tuple[float, list[str]]:
    variant = _first_variant(product)
    status = str(product.get("status") or "").upper()
    checks = [
        bool(variant.get("price")),
        status in ("", "ACTIVE"),
        bool(product.get("handle")),
    ]
    recommendations: list[str] = []
    if not variant.get("price"):
        recommendations.append("Ensure price is available for revenue-aware and offer-aware scoring.")
    if status and status != "ACTIVE":
        recommendations.append("Review product publication status before prioritizing GEO work.")
    return round(sum(checks) / len(checks), 2), recommendations


def score_product_readiness(product: dict[str, Any]) -> dict[str, Any]:
    """Score one product for AI Search readiness.

    The score is an internal readiness indicator, not a ranking guarantee.
    """
    facts = analyze_product_facts(product)
    fact_keys = {fact["key"] for fact in facts["confirmed_facts"]}

    seo_score, seo_recs = _seo_score(product)
    schema_score, schema_recs = _schema_score(product, fact_keys)
    answer_score, answer_recs = _answer_score(product, fact_keys)
    trust_score, trust_recs = _trust_score(fact_keys)
    commerce_score, commerce_recs = _commerce_score(product)
    facts_score = facts["completeness_score"]

    weighted = (
        0.25 * facts_score
        + 0.20 * schema_score
        + 0.20 * answer_score
        + 0.15 * trust_score
        + 0.10 * seo_score
        + 0.10 * commerce_score
    )
    score = round(weighted * 100)

    recommendations = (
        facts["suggestions_to_verify"][:2]
        + [{"key": "answerability", "label": "Answerability", "instruction": rec} for rec in answer_recs]
        + [{"key": "schema", "label": "Structured data", "instruction": rec} for rec in schema_recs]
        + [{"key": "trust", "label": "Trust", "instruction": rec} for rec in trust_recs]
        + [{"key": "seo", "label": "SEO", "instruction": rec} for rec in seo_recs]
        + [{"key": "commerce", "label": "Commerce", "instruction": rec} for rec in commerce_recs]
    )

    if score >= 75:
        level = "ready"
    elif score >= 50:
        level = "partial"
    else:
        level = "weak"

    return {
        "id": product.get("id", ""),
        "handle": product.get("handle", ""),
        "title": product.get("title", ""),
        "readiness_score": score,
        "level": level,
        "components": {
            "facts": round(facts_score * 100),
            "schema": round(schema_score * 100),
            "answerability": round(answer_score * 100),
            "trust": round(trust_score * 100),
            "seo": round(seo_score * 100),
            "commerce": round(commerce_score * 100),
        },
        "confirmed_fact_count": facts["confirmed_count"],
        "missing_fact_count": facts["missing_count"],
        "recommendations": recommendations[:5],
        "note": "Internal readiness score only; it does not guarantee ranking or citation in AI search.",
    }


def score_catalog_readiness(products: list[dict[str, Any]], top: int = 50) -> dict[str, Any]:
    """Score a product catalog for AI Search readiness."""
    rows = [score_product_readiness(product) for product in products if product.get("title")]
    rows.sort(key=lambda item: (item["readiness_score"], item["title"]))
    limited = rows[:top]
    total = len(rows)
    avg_score = round(sum(row["readiness_score"] for row in rows) / total) if total else 0

    return {
        "total": total,
        "summary": {
            "avg_readiness_score": avg_score,
            "ready_products": sum(1 for row in rows if row["level"] == "ready"),
            "partial_products": sum(1 for row in rows if row["level"] == "partial"),
            "weak_products": sum(1 for row in rows if row["level"] == "weak"),
            "score_note": "AI Search Readiness is an internal diagnostic score, not a visibility promise.",
        },
        "products": limited,
    }
