"""Product facts extraction for GEO and AI search readiness."""

from __future__ import annotations

import re
from typing import Any

from app.niche.ner import ProductEntities, extract_entities

_CONFIRMED_SOURCE = "shopify_snapshot"
_ENTITY_SOURCE = "description_entities"

_SENSITIVE_FACTS: tuple[tuple[str, str], ...] = (
    ("materials", "Material or composition"),
    ("origins", "Manufacturing origin"),
    ("certifications", "Certification or proof"),
    ("warranty", "Warranty"),
    ("care", "Care instructions"),
    ("dimensions", "Dimensions"),
    ("compatibility", "Compatibility"),
    ("size_recommendation", "Size recommendation"),
)

_TRUST_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("warranty", ("garantie", "guarantee", "warranty", "satisfait", "rembours")),
    ("delivery", ("livraison", "delivery", "expédition", "shipping")),
    ("returns", ("retour", "returns", "refund", "remboursement")),
    ("care", ("entretien", "lavage", "nettoyage", "wash", "clean")),
    ("dimensions", ("dimension", "taille", "cm", "centim", "size")),
    ("compatibility", ("compatible", "adapté", "convient", "suitable")),
)


def _strip_html(value: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").strip()


def _edge_nodes(container: Any) -> list[dict[str, Any]]:
    if isinstance(container, dict):
        edges = container.get("edges")
        if isinstance(edges, list):
            return [edge.get("node", {}) for edge in edges if isinstance(edge, dict)]
    if isinstance(container, list):
        return [item for item in container if isinstance(item, dict)]
    return []


def _tags_text(product: dict[str, Any]) -> str:
    tags = product.get("tags")
    if isinstance(tags, list):
        return " ".join(str(tag) for tag in tags)
    if isinstance(tags, str):
        return tags
    return ""


def _product_type(product: dict[str, Any]) -> str:
    return str(product.get("product_type") or product.get("productType") or "").strip()


def _description(product: dict[str, Any]) -> str:
    return _strip_html(
        product.get("descriptionHtml")
        or product.get("body_html")
        or product.get("description")
        or ""
    )


def _text_for_entities(product: dict[str, Any]) -> str:
    return " ".join(
        value
        for value in [
            str(product.get("title") or ""),
            _description(product),
            _product_type(product),
            _tags_text(product),
        ]
        if value
    )


def _first_variant(product: dict[str, Any]) -> dict[str, Any]:
    variants = product.get("variants")
    nodes = _edge_nodes(variants)
    return nodes[0] if nodes else {}


def _confirmed_fact(key: str, label: str, value: Any, source: str = _CONFIRMED_SOURCE) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "source": source,
        "confidence": "confirmed",
    }


def _entity_facts(entities: ProductEntities) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for key, label, values in [
        ("materials", "Materials", entities.materials),
        ("certifications", "Certifications", entities.certifications),
        ("origins", "Origins", entities.origins),
        ("targets", "Recommended target", entities.targets),
        ("properties", "Product properties", entities.properties),
    ]:
        if values:
            facts.append(_confirmed_fact(key, label, values, _ENTITY_SOURCE))
    return facts


def _matched_signal_keys(text: str) -> set[str]:
    normalized = text.lower()
    found: set[str] = set()
    for key, patterns in _TRUST_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            found.add(key)
    return found


def analyze_product_facts(product: dict[str, Any]) -> dict[str, Any]:
    """Extract confirmed and missing product facts from one Shopify product.

    The extractor only records facts already present in Shopify snapshot data.
    Missing sensitive facts are returned as merchant suggestions to verify.
    """
    title = str(product.get("title") or "").strip()
    handle = str(product.get("handle") or "").strip()
    description = _description(product)
    product_type = _product_type(product)
    text = _text_for_entities(product)
    entities = extract_entities(text)
    variant = _first_variant(product)

    confirmed: list[dict[str, Any]] = []
    if title:
        confirmed.append(_confirmed_fact("title", "Product title", title))
    if handle:
        confirmed.append(_confirmed_fact("handle", "Product handle", handle))
    if product_type:
        confirmed.append(_confirmed_fact("product_type", "Product type", product_type))
    if description:
        confirmed.append(_confirmed_fact("description", "Description", description[:240]))
    if product.get("status"):
        confirmed.append(_confirmed_fact("status", "Shopify status", product["status"]))
    if variant.get("price"):
        confirmed.append(_confirmed_fact("price", "Price", variant["price"]))

    confirmed.extend(_entity_facts(entities))

    signal_keys = _matched_signal_keys(text)
    for key, label in [
        ("warranty", "Warranty signal"),
        ("delivery", "Delivery signal"),
        ("returns", "Returns signal"),
        ("care", "Care signal"),
        ("dimensions", "Dimensions signal"),
        ("compatibility", "Compatibility signal"),
    ]:
        if key in signal_keys:
            confirmed.append(_confirmed_fact(key, label, "Mentioned in product content", _ENTITY_SOURCE))

    confirmed_keys = {fact["key"] for fact in confirmed}
    missing = [
        {"key": key, "label": label}
        for key, label in _SENSITIVE_FACTS
        if key not in confirmed_keys
    ]

    suggestions = [
        {
            "key": item["key"],
            "label": item["label"],
            "instruction": f"Ask the merchant to confirm {item['label'].lower()} before using it in GEO content.",
        }
        for item in missing
    ]

    required_count = len(_SENSITIVE_FACTS)
    present_count = required_count - len(missing)
    completeness_score = round(present_count / required_count, 2)

    return {
        "id": product.get("id", ""),
        "handle": handle,
        "title": title,
        "confirmed_facts": confirmed,
        "missing_facts": missing,
        "suggestions_to_verify": suggestions,
        "completeness_score": completeness_score,
        "confirmed_count": len(confirmed),
        "missing_count": len(missing),
        "safety_note": (
            "Only confirmed Shopify snapshot facts are used. Missing sensitive facts must be "
            "verified by the merchant before generation or publication."
        ),
    }


def analyze_catalog_facts(products: list[dict[str, Any]], top: int = 50) -> dict[str, Any]:
    """Analyze product facts for a catalog snapshot."""
    rows = [analyze_product_facts(product) for product in products if product.get("title")]
    rows.sort(key=lambda item: (item["completeness_score"], -item["missing_count"], item["title"]))
    limited = rows[:top]

    total = len(rows)
    avg_score = round(
        sum(item["completeness_score"] for item in rows) / total,
        2,
    ) if total else 0.0
    critical_missing = sum(
        1 for item in rows if any(fact["key"] in {"materials", "origins"} for fact in item["missing_facts"])
    )

    return {
        "total": total,
        "summary": {
            "avg_completeness_score": avg_score,
            "products_missing_sensitive_facts": critical_missing,
            "products_ready_for_geo": sum(1 for item in rows if item["completeness_score"] >= 0.75),
            "safety_note": "Facts are extracted from existing Shopify data only; suggestions are merchant validation prompts.",
        },
        "products": limited,
    }

