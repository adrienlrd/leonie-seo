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
        nodes = container.get("nodes")
        if isinstance(nodes, list):
            return [item for item in nodes if isinstance(item, dict)]
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


def _confirmed_fact(
    key: str, label: str, value: Any, source: str = _CONFIRMED_SOURCE
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "source": source,
        "confidence": "confirmed",
    }


def _fact_value_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_fact_value_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_fact_value_text(item) for item in value)
    return str(value or "").strip()


def _append_fact_once(
    facts: list[dict[str, Any]],
    key: str,
    label: str,
    value: Any,
    source: str,
) -> None:
    value_text = _fact_value_text(value)
    if not value_text:
        return
    if any(fact.get("key") == key for fact in facts):
        return
    facts.append(_confirmed_fact(key, label, value, source))


_METAFIELD_KEY_MAP: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("material", "materials", "matiere", "matière", "composition"), "materials", "Materials"),
    (
        ("dimension", "dimensions", "width", "height", "length", "diameter"),
        "dimensions",
        "Dimensions",
    ),
    (("capacity", "contenance", "volume"), "capacity", "Capacity"),
    (("battery", "batterie", "autonomy", "autonomie"), "battery_autonomy", "Battery or autonomy"),
    (
        ("compatibility", "compatible", "compatibilite", "compatibilité"),
        "compatibility",
        "Compatibility",
    ),
    (("care", "entretien", "lavage", "wash"), "care_instructions", "Care instructions"),
    (("origin", "origine", "made_in", "fabrication"), "origins", "Manufacturing origin"),
    (("warranty", "garantie"), "warranty", "Warranty"),
    (("color", "colour", "couleur"), "color", "Color"),
    (("size", "taille"), "size", "Size"),
)

_MATERIAL_TERMS = frozenset(
    {
        "cachemire",
        "laine",
        "coton",
        "nylon",
        "cuir",
        "acier",
        "inox",
        "bois",
        "silicone",
        "bambou",
        "polyester",
        "corde",
    }
)


def _normalized_key_text(value: str) -> str:
    return (
        value.lower()
        .replace("è", "e")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ç", "c")
    )


def _mapped_attribute(name: str) -> tuple[str, str] | None:
    normalized = _normalized_key_text(name)
    for needles, key, label in _METAFIELD_KEY_MAP:
        if any(needle in normalized for needle in needles):
            return key, label
    return None


def _metafield_items(product: dict[str, Any]) -> list[dict[str, Any]]:
    return _edge_nodes(product.get("metafields"))


def _option_items(product: dict[str, Any]) -> list[dict[str, Any]]:
    return _edge_nodes(product.get("options"))


def _material_terms(text: str) -> set[str]:
    words = set(re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower()))
    return {word for word in words if word in _MATERIAL_TERMS}


def _description_attribute_facts(description: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    dimensions = re.findall(r"\b\d+(?:[.,]\d+)?\s?(?:cm|mm|kg|g)\b", description, flags=re.I)
    capacity = re.findall(r"\b\d+(?:[.,]\d+)?\s?(?:l|litres?|ml)\b", description, flags=re.I)
    if dimensions:
        _append_fact_once(
            facts, "dimensions", "Dimensions", sorted(set(dimensions)), _ENTITY_SOURCE
        )
    if capacity:
        _append_fact_once(facts, "capacity", "Capacity", sorted(set(capacity)), _ENTITY_SOURCE)
    return facts


def _structured_attribute_facts(product: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    facts: list[dict[str, Any]] = []
    structured_material_text: list[str] = []
    if product.get("status"):
        _append_fact_once(
            facts, "product_status", "Product status", product["status"], _CONFIRMED_SOURCE
        )

    for option in _option_items(product):
        name = str(option.get("name") or "").strip()
        mapped = _mapped_attribute(name)
        if not mapped:
            continue
        values = option.get("values") or option.get("value")
        key, label = mapped
        _append_fact_once(facts, key, label, values, "shopify_options")
        if key == "materials":
            structured_material_text.append(_fact_value_text(values))

    for variant in _edge_nodes(product.get("variants")):
        selected_options = _edge_nodes(variant.get("selectedOptions"))
        for option in selected_options:
            name = str(option.get("name") or "").strip()
            mapped = _mapped_attribute(name)
            if not mapped:
                continue
            key, label = mapped
            value = option.get("value") or option.get("values")
            _append_fact_once(facts, key, label, value, "shopify_variants")
            if key == "materials":
                structured_material_text.append(_fact_value_text(value))

    for metafield in _metafield_items(product):
        name = " ".join(
            str(metafield.get(field) or "")
            for field in ("namespace", "key", "name", "type")
            if metafield.get(field)
        )
        mapped = _mapped_attribute(name)
        if not mapped:
            continue
        key, label = mapped
        value = metafield.get("value") or metafield.get("jsonValue")
        _append_fact_once(facts, key, label, value, "shopify_metafields")
        if key == "materials":
            structured_material_text.append(_fact_value_text(value))

    return facts, " ".join(structured_material_text)


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
    structured_facts, structured_material_text = _structured_attribute_facts(product)

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

    for fact in structured_facts:
        _append_fact_once(
            confirmed,
            str(fact.get("key", "")),
            str(fact.get("label", "")),
            fact.get("value"),
            str(fact.get("source", _CONFIRMED_SOURCE)),
        )

    for fact in _entity_facts(entities):
        _append_fact_once(
            confirmed,
            str(fact.get("key", "")),
            str(fact.get("label", "")),
            fact.get("value"),
            str(fact.get("source", _ENTITY_SOURCE)),
        )

    for fact in _description_attribute_facts(description):
        _append_fact_once(
            confirmed,
            str(fact.get("key", "")),
            str(fact.get("label", "")),
            fact.get("value"),
            str(fact.get("source", _ENTITY_SOURCE)),
        )

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
            confirmed.append(
                _confirmed_fact(key, label, "Mentioned in product content", _ENTITY_SOURCE)
            )

    confirmed_keys = {fact["key"] for fact in confirmed}
    missing = [
        {"key": key, "label": label} for key, label in _SENSITIVE_FACTS if key not in confirmed_keys
    ]
    extracted_attributes = {
        key: fact.get("value")
        for key in (
            "materials",
            "dimensions",
            "capacity",
            "battery_autonomy",
            "compatibility",
            "care_instructions",
            "origins",
            "warranty",
            "color",
            "size",
            "price",
            "product_status",
        )
        for fact in confirmed
        if fact.get("key") == key
    }
    if "origins" in extracted_attributes:
        extracted_attributes["origin"] = extracted_attributes["origins"]
    description_materials = _material_terms(description)
    structured_materials = _material_terms(structured_material_text)
    fact_conflicts: list[dict[str, Any]] = []
    if (
        description_materials
        and structured_materials
        and description_materials.isdisjoint(structured_materials)
    ):
        fact_conflicts.append(
            {
                "field_key": "materials",
                "description_values": sorted(description_materials),
                "extracted_values": sorted(structured_materials),
                "message": "Material values conflict between product description and structured Shopify data.",
                "requires_merchant_validation": True,
            }
        )

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
        "extracted_attributes": extracted_attributes,
        "fact_conflict": bool(fact_conflicts),
        "fact_conflicts": fact_conflicts,
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
    avg_score = (
        round(
            sum(item["completeness_score"] for item in rows) / total,
            2,
        )
        if total
        else 0.0
    )
    critical_missing = sum(
        1
        for item in rows
        if any(fact["key"] in {"materials", "origins"} for fact in item["missing_facts"])
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
