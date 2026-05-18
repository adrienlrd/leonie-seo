"""Fact-grounded FAQ and answer blocks for GEO previews."""

from __future__ import annotations

from typing import Any

from app.geo.facts import analyze_product_facts

_PUBLISHABLE_FACT_KEYS = {
    "description",
    "product_type",
    "materials",
    "certifications",
    "origins",
    "targets",
    "properties",
    "price",
    "status",
}

_SIGNAL_ONLY_FACT_KEYS = {
    "warranty",
    "delivery",
    "returns",
    "care",
    "dimensions",
    "compatibility",
}


def _fact_map(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(fact.get("key")): fact for fact in facts}


def _string_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    return str(value or "").strip()


def _source(fact: dict[str, Any]) -> dict[str, str]:
    return {
        "key": str(fact.get("key") or ""),
        "label": str(fact.get("label") or ""),
        "source": str(fact.get("source") or ""),
    }


def _answer_block(
    *,
    question: str,
    answer: str,
    intent: str,
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "question": question,
        "answer": answer,
        "intent": intent,
        "confidence": "confirmed",
        "sources": [_source(fact) for fact in facts],
        "review_required": False,
    }


def _review_prompt(key: str, label: str, title: str, reason: str) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "question": f"Confirmer {label.lower()} pour {title}",
        "reason": reason,
    }


def _description_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Que faut-il savoir sur {title} ?",
        answer=value,
        intent="overview",
        facts=[fact],
    )


def _product_type_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Dans quelle catégorie se trouve {title} ?",
        answer=f"{title} est classé dans la catégorie {value}.",
        intent="classification",
        facts=[fact],
    )


def _materials_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Quelle est la matière de {title} ?",
        answer=f"Les matières confirmées pour {title} sont : {value}.",
        intent="material",
        facts=[fact],
    )


def _origins_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Où est fabriqué {title} ?",
        answer=f"L'origine confirmée dans les données produit est : {value}.",
        intent="origin",
        facts=[fact],
    )


def _certifications_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"{title} dispose-t-il d'une certification ?",
        answer=f"Les certifications confirmées pour {title} sont : {value}.",
        intent="trust",
        facts=[fact],
    )


def _targets_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Pour qui {title} est-il recommandé ?",
        answer=f"Les cibles confirmées pour {title} sont : {value}.",
        intent="fit",
        facts=[fact],
    )


def _properties_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Quels sont les points clés de {title} ?",
        answer=f"Les propriétés confirmées pour {title} sont : {value}.",
        intent="benefit",
        facts=[fact],
    )


def _price_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"Quel est le prix de {title} ?",
        answer=f"Le prix présent dans le snapshot Shopify est {value}.",
        intent="commerce",
        facts=[fact],
    )


def _status_block(title: str, fact: dict[str, Any]) -> dict[str, Any]:
    value = _string_value(fact.get("value"))
    return _answer_block(
        question=f"{title} est-il publié dans Shopify ?",
        answer=f"Le statut Shopify confirmé est : {value}.",
        intent="availability",
        facts=[fact],
    )


_BLOCK_BUILDERS = {
    "description": _description_block,
    "product_type": _product_type_block,
    "materials": _materials_block,
    "origins": _origins_block,
    "certifications": _certifications_block,
    "targets": _targets_block,
    "properties": _properties_block,
    "price": _price_block,
    "status": _status_block,
}


def _jsonld(answer_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": block["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": block["answer"],
                },
            }
            for block in answer_blocks
            if not block["review_required"]
        ],
    }


def build_product_answer_blocks(product: dict[str, Any], *, max_blocks: int = 6) -> dict[str, Any]:
    """Build fact-grounded answer blocks for one product."""
    facts = analyze_product_facts(product)
    title = str(facts.get("title") or product.get("title") or "").strip()
    mapped_facts = _fact_map(facts["confirmed_facts"])

    answer_blocks = []
    for key in (
        "description",
        "product_type",
        "materials",
        "origins",
        "certifications",
        "targets",
        "properties",
        "price",
        "status",
    ):
        fact = mapped_facts.get(key)
        if not fact or key not in _PUBLISHABLE_FACT_KEYS:
            continue
        value = _string_value(fact.get("value"))
        if not value:
            continue
        answer_blocks.append(_BLOCK_BUILDERS[key](title, fact))
        if len(answer_blocks) >= max_blocks:
            break

    review_prompts = [
        _review_prompt(
            str(item["key"]),
            str(item["label"]),
            title,
            "Sensitive fact is missing and must be confirmed before generating a public answer.",
        )
        for item in facts["missing_facts"]
    ]
    for key in sorted(_SIGNAL_ONLY_FACT_KEYS & mapped_facts.keys()):
        fact = mapped_facts[key]
        review_prompts.append(
            _review_prompt(
                key,
                str(fact.get("label") or key),
                title,
                "The product content mentions this topic, but the exact public answer still needs merchant validation.",
            )
        )

    return {
        "product_id": facts["id"],
        "handle": facts["handle"],
        "title": title,
        "answer_block_count": len(answer_blocks),
        "answer_blocks": answer_blocks,
        "review_prompt_count": len(review_prompts),
        "review_prompts": review_prompts,
        "jsonld": _jsonld(answer_blocks),
        "dry_run": True,
        "safety_note": "Only confirmed Shopify snapshot facts are used in answer blocks; uncertain facts remain review prompts.",
    }


def build_catalog_answer_blocks(
    products: list[dict[str, Any]],
    *,
    top: int = 30,
    max_blocks: int = 6,
) -> dict[str, Any]:
    """Build answer block previews across a product catalog."""
    rows = [
        build_product_answer_blocks(product, max_blocks=max_blocks)
        for product in products
        if product.get("title")
    ]
    rows.sort(key=lambda row: (-row["answer_block_count"], row["title"]))
    limited = rows[:top]
    return {
        "total": len(rows),
        "summary": {
            "products_with_answers": sum(1 for row in rows if row["answer_block_count"] > 0),
            "total_answer_blocks": sum(row["answer_block_count"] for row in rows),
            "total_review_prompts": sum(row["review_prompt_count"] for row in rows),
            "dry_run": True,
            "safety_note": "Answer blocks are previews grounded in confirmed facts only; Shopify is not modified.",
        },
        "products": limited,
    }
