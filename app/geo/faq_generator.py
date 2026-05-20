"""GEO FAQ & Buying Guide generator (task 126).

Generates product FAQ, collection FAQ, answer blocks, buying guides and
JSON-LD FAQPage from confirmed Shopify facts and real GSC queries.
All output is draft / needs_review — no Shopify write without explicit
merchant confirmation. No facts are invented: missing sensitive data is
surfaced as merchant verification prompts, never filled with assumptions.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.geo.facts import analyze_product_facts
from app.snapshot.scope import filter_products_by_scope, summarize_product_scopes

# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

_QUALITY_THRESHOLDS = [
    (80, "excellent"),
    (60, "bon"),
    (40, "à_compléter"),
    (0, "incomplet"),
]


def _quality_label(score: int) -> str:
    for threshold, label in _QUALITY_THRESHOLDS:
        if score >= threshold:
            return label
    return "incomplet"


def _quality_score(confirmed_count: int, missing_count: int, faq_count: int, has_queries: bool) -> int:
    score = 0
    # Fact completeness (max 40)
    total = confirmed_count + missing_count
    if total > 0:
        score += round(40 * confirmed_count / total)
    # FAQ richness (max 30): 3+ items = full credit
    score += min(30, faq_count * 10)
    # GSC signal (max 20)
    if has_queries:
        score += 20
    # Description present (max 10)
    if confirmed_count >= 2:
        score += 10
    return min(100, score)


# ---------------------------------------------------------------------------
# FAQ Q/A generation from confirmed facts
# ---------------------------------------------------------------------------

_FACT_QA_FR: dict[str, tuple[str, str]] = {
    "product_type": (
        "À quelle catégorie appartient ce produit ?",
        "Ce produit appartient à la catégorie : {value}.",
    ),
    "materials": (
        "De quelle matière est-il fabriqué ?",
        "Ce produit est fabriqué à partir de : {value}.",
    ),
    "certifications": (
        "Ce produit est-il certifié ?",
        "Ce produit possède les certifications suivantes : {value}.",
    ),
    "origins": (
        "Où ce produit est-il fabriqué ?",
        "Origine du produit : {value}.",
    ),
    "targets": (
        "À qui ce produit est-il destiné ?",
        "Ce produit est recommandé pour : {value}.",
    ),
    "properties": (
        "Quelles sont les caractéristiques principales ?",
        "Caractéristiques : {value}.",
    ),
    "warranty": (
        "Ce produit est-il garanti ?",
        "Des informations relatives à la garantie sont mentionnées dans la fiche produit. Consultez la description pour les détails.",
    ),
    "care": (
        "Comment entretenir ce produit ?",
        "Des conseils d'entretien sont disponibles dans la description produit.",
    ),
    "dimensions": (
        "Quelles sont les dimensions de ce produit ?",
        "Des informations de dimensions sont mentionnées dans la fiche produit.",
    ),
    "compatibility": (
        "Avec quoi ce produit est-il compatible ?",
        "Des informations de compatibilité sont disponibles dans la description.",
    ),
    "price": (
        "Quel est le prix de ce produit ?",
        "Ce produit est proposé à {value} €.",
    ),
    "delivery": (
        "Quelles sont les options de livraison ?",
        "Des informations de livraison sont disponibles sur la page produit.",
    ),
    "returns": (
        "Quelle est la politique de retour ?",
        "Des informations de retour sont disponibles sur la page produit.",
    ),
}

_BUYING_GUIDE_KEYS = {
    "targets": "Choisir ce produit si…",
    "compatibility": "Compatible avec…",
    "care": "Entretien et durabilité",
    "warranty": "Garantie et retours",
    "dimensions": "Dimensions à connaître",
    "certifications": "Certifications",
}


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value or "").strip()


def _stable_id(prefix: str, resource_id: str, content_type: str) -> str:
    raw = f"{prefix}:{resource_id}:{content_type}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]  # noqa: S324


def _match_queries(title: str, gsc_queries: list[str], max_matches: int = 5) -> list[str]:
    """Return GSC queries that share at least one significant word with the product title."""
    title_words = {w.lower() for w in title.split() if len(w) > 3}
    matched: list[str] = []
    for query in gsc_queries:
        query_words = {w.lower() for w in query.split() if len(w) > 3}
        if title_words & query_words:
            matched.append(query)
        if len(matched) >= max_matches:
            break
    return matched


def _faq_from_queries(matched_queries: list[str], title: str) -> list[dict[str, str]]:
    """Generate simple intent-based Q/A from real GSC queries."""
    items: list[dict[str, str]] = []
    for query in matched_queries:
        q = query.capitalize() + ("?" if not query.endswith("?") else "")
        a = (
            f"Pour \"{title}\", consultez la description produit et les informations "
            f"ci-dessous pour répondre à cette question. Si vous avez besoin d'aide, "
            f"contactez-nous directement."
        )
        items.append({"question": q, "answer": a, "source": "gsc_query"})
    return items


def _faq_from_facts(confirmed_facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Generate Q/A pairs from each confirmed product fact."""
    items: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for fact in confirmed_facts:
        key = fact.get("key") or ""
        if key in seen_keys or key not in _FACT_QA_FR:
            continue
        seen_keys.add(key)
        question, answer_template = _FACT_QA_FR[key]
        value = _format_value(fact.get("value") or "")
        answer = answer_template.format(value=value) if "{value}" in answer_template else answer_template
        items.append({"question": question, "answer": answer, "source": f"fact:{key}"})
    return items


def _buying_guide_sections(confirmed_facts: list[dict[str, Any]], title: str) -> list[dict[str, str]]:
    """Build buying guide sections from relevant confirmed facts."""
    fact_by_key = {f["key"]: f for f in confirmed_facts}
    sections: list[dict[str, str]] = []

    # "Choose this product if" from targets / properties
    for key in ("targets", "properties"):
        if key in fact_by_key:
            value = _format_value(fact_by_key[key].get("value") or "")
            if value:
                sections.append({
                    "heading": "Choisir ce produit si…",
                    "content": f"Ce produit convient particulièrement à : {value}.",
                    "source": f"fact:{key}",
                })
                break

    # "Know before buying" from care / dimensions / warranty
    know_lines: list[str] = []
    for key in ("care", "dimensions", "warranty"):
        if key in fact_by_key:
            _, tmpl = _FACT_QA_FR.get(key, ("", "{value}"))
            know_lines.append(tmpl.format(value=""))
    if know_lines:
        sections.append({
            "heading": "À savoir avant l'achat",
            "content": " ".join(know_lines).strip(),
            "source": "fact:care+dimensions+warranty",
        })

    # Compatibility
    if "compatibility" in fact_by_key:
        sections.append({
            "heading": "Compatibilité",
            "content": "Des informations de compatibilité sont disponibles dans la description.",
            "source": "fact:compatibility",
        })

    # Certifications
    if "certifications" in fact_by_key:
        value = _format_value(fact_by_key["certifications"].get("value") or "")
        sections.append({
            "heading": "Certifications",
            "content": f"Ce produit est certifié : {value}." if value else "Certifications mentionnées dans la description.",
            "source": "fact:certifications",
        })

    return sections


def _answer_block(title: str, confirmed_facts: list[dict[str, Any]], matched_queries: list[str]) -> str:
    """Generate a short 1-2 sentence answer block for AI search consumption."""
    product_type = next(
        (_format_value(f.get("value")) for f in confirmed_facts if f.get("key") == "product_type"),
        "",
    )
    materials = next(
        (_format_value(f.get("value")) for f in confirmed_facts if f.get("key") == "materials"),
        "",
    )
    targets = next(
        (_format_value(f.get("value")) for f in confirmed_facts if f.get("key") == "targets"),
        "",
    )

    parts: list[str] = [f"{title}"]
    if product_type:
        parts.append(f"est un(e) {product_type.lower()}")
    if materials:
        parts.append(f"fabriqué(e) en {materials.lower()}")
    if targets:
        parts.append(f"conçu(e) pour {targets.lower()}")
    sentence = " ".join(parts) + "."

    context = ""
    if matched_queries:
        context = f" Ce produit répond notamment aux recherches : « {matched_queries[0]} »."

    return sentence + context


def _faq_jsonld(title: str, faq_items: list[dict[str, str]]) -> dict[str, Any]:
    """Generate a JSON-LD FAQPage schema from FAQ items."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "name": f"FAQ — {title}",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["answer"],
                },
            }
            for item in faq_items
            if item.get("question") and item.get("answer")
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_product_content(
    product: dict[str, Any],
    gsc_queries: list[str] | None = None,
) -> dict[str, Any]:
    """Generate FAQ, buying guide, answer block and JSON-LD for one product.

    Args:
        product: Shopify product dict from catalog snapshot.
        gsc_queries: List of GSC query strings (flat, not per-product dicts).

    Returns:
        Content dict with faq_items, buying_guide, answer_block, faq_jsonld,
        quality_score, status and provenance metadata.
    """
    facts = analyze_product_facts(product)
    confirmed = facts["confirmed_facts"]
    missing = facts["missing_facts"]
    title = facts["title"] or str(product.get("id") or "")
    resource_id = str(product.get("id") or "")

    matched = _match_queries(title, gsc_queries or [])

    faq_from_facts = _faq_from_facts(confirmed)
    faq_from_queries = _faq_from_queries(matched, title)
    # Deduplicate by question text
    seen_q: set[str] = set()
    all_faq: list[dict[str, str]] = []
    for item in faq_from_facts + faq_from_queries:
        q = item["question"]
        if q not in seen_q:
            seen_q.add(q)
            all_faq.append(item)

    guide_sections = _buying_guide_sections(confirmed, title)
    block = _answer_block(title, confirmed, matched)
    jsonld = _faq_jsonld(title, all_faq)

    score = _quality_score(
        confirmed_count=len(confirmed),
        missing_count=len(missing),
        faq_count=len(all_faq),
        has_queries=bool(matched),
    )

    # Mark needs_review when sensitive facts are absent or very few confirmed facts
    sensitive_missing = {m["key"] for m in missing} & {"materials", "origins", "certifications"}
    status = "needs_review" if (len(missing) > 4 or sensitive_missing) else "draft"

    return {
        "id": _stable_id("product", resource_id, "faq"),
        "content_type": "product_faq",
        "resource_type": "product",
        "resource_id": resource_id,
        "resource_title": title,
        "resource_handle": facts["handle"],
        "faq_items": all_faq,
        "buying_guide": {
            "title": f"Guide d'achat — {title}",
            "sections": guide_sections,
        },
        "answer_block": block,
        "faq_jsonld": jsonld,
        "faq_jsonld_str": json.dumps(jsonld, ensure_ascii=False, indent=2),
        "quality_score": score,
        "quality_label": _quality_label(score),
        "status": status,
        "facts_used": [f["key"] for f in confirmed],
        "facts_missing": [m["key"] for m in missing],
        "source_queries": matched,
        "completeness_score": facts["completeness_score"],
    }


def generate_collection_faq(
    collection: dict[str, Any],
    products: list[dict[str, Any]],
    gsc_queries: list[str] | None = None,
    max_products: int = 5,
) -> dict[str, Any]:
    """Generate a collection-level FAQ from catalog products.

    Args:
        collection: Shopify collection dict (id, title, handle, description).
        products: Products belonging to this collection.
        gsc_queries: Flat list of GSC query strings.
        max_products: Products sampled for FAQ richness.

    Returns:
        Collection FAQ content dict.
    """
    title = str(collection.get("title") or "Collection")
    resource_id = str(collection.get("id") or "collection-0")
    description = str(collection.get("body_html") or collection.get("description") or "").strip()

    sample = products[:max_products]
    product_titles = [str(p.get("title") or "") for p in sample if p.get("title")]
    matched = _match_queries(title, gsc_queries or [])

    faq_items: list[dict[str, str]] = []

    if product_titles:
        faq_items.append({
            "question": f"Quels produits trouve-t-on dans la collection « {title} » ?",
            "answer": f"Cette collection comprend notamment : {', '.join(product_titles[:3])}{'...' if len(product_titles) > 3 else ''}.",
            "source": "catalog",
        })

    if description:
        faq_items.append({
            "question": f"Qu'est-ce que la collection « {title} » ?",
            "answer": description[:300],
            "source": "collection_description",
        })

    faq_items.extend(_faq_from_queries(matched[:3], title))

    if len(sample) > 1:
        faq_items.append({
            "question": f"Comment choisir dans la collection « {title} » ?",
            "answer": (
                f"La collection « {title} » propose {len(products)} produit(s). "
                "Filtrez par usage, matière ou taille pour trouver le modèle adapté."
            ),
            "source": "catalog_count",
        })

    jsonld = _faq_jsonld(title, faq_items)
    score = _quality_score(
        confirmed_count=len(product_titles) + (1 if description else 0),
        missing_count=0,
        faq_count=len(faq_items),
        has_queries=bool(matched),
    )

    return {
        "id": _stable_id("collection", resource_id, "faq"),
        "content_type": "collection_faq",
        "resource_type": "collection",
        "resource_id": resource_id,
        "resource_title": title,
        "resource_handle": str(collection.get("handle") or ""),
        "faq_items": faq_items,
        "buying_guide": None,
        "answer_block": f"La collection « {title} » regroupe {len(products)} produit(s)." + (
            f" {description[:120]}..." if description else ""
        ),
        "faq_jsonld": jsonld,
        "faq_jsonld_str": json.dumps(jsonld, ensure_ascii=False, indent=2),
        "quality_score": score,
        "quality_label": _quality_label(score),
        "status": "draft",
        "facts_used": ["title", "description", "product_count"],
        "facts_missing": [],
        "source_queries": matched,
        "completeness_score": 1.0 if description else 0.5,
    }


def generate_catalog_content(
    products: list[dict[str, Any]],
    gsc_queries: list[str] | None = None,
    collections: list[dict[str, Any]] | None = None,
    top: int = 20,
    scope: str = "active",
) -> dict[str, Any]:
    """Generate GEO content for the top products and all collections.

    Args:
        products: Full Shopify product list from snapshot.
        gsc_queries: Flat list of GSC query strings.
        collections: Optional Shopify collections list.
        top: Maximum number of products to process.

    Returns:
        Dict with content items list and summary statistics.
    """
    queries = gsc_queries or []
    scoped_products = filter_products_by_scope(products, scope)
    content_items: list[dict[str, Any]] = []

    for product in scoped_products[:top]:
        item = generate_product_content(product, gsc_queries=queries)
        content_items.append(item)

    for collection in (collections or [])[:10]:
        # Associate products that match the collection handle or title
        coll_products = _products_for_collection(collection, scoped_products)
        item = generate_collection_faq(collection, coll_products, gsc_queries=queries)
        content_items.append(item)

    by_status: dict[str, int] = {"draft": 0, "needs_review": 0}
    by_quality: dict[str, int] = {"excellent": 0, "bon": 0, "à_compléter": 0, "incomplet": 0}
    for item in content_items:
        s = item.get("status") or "draft"
        by_status[s] = by_status.get(s, 0) + 1
        q = item.get("quality_label") or "incomplet"
        by_quality[q] = by_quality.get(q, 0) + 1

    avg_quality = (
        round(sum(item.get("quality_score", 0) for item in content_items) / len(content_items))
        if content_items
        else 0
    )

    return {
        "content_items": content_items,
        "scope": summarize_product_scopes(products, scope),
        "summary": {
            "total": len(content_items),
            "by_status": by_status,
            "by_quality": by_quality,
            "avg_quality_score": avg_quality,
        },
    }


def _products_for_collection(
    collection: dict[str, Any],
    products: list[dict[str, Any]],
    max_products: int = 10,
) -> list[dict[str, Any]]:
    """Return products whose product_type roughly matches the collection title."""
    coll_title = str(collection.get("title") or "").lower()
    coll_words = {w for w in coll_title.split() if len(w) > 3}
    matched: list[dict[str, Any]] = []
    for product in products:
        p_type = str(product.get("product_type") or product.get("productType") or "").lower()
        p_title = str(product.get("title") or "").lower()
        p_words = {w for w in (p_type + " " + p_title).split() if len(w) > 3}
        if coll_words & p_words:
            matched.append(product)
        if len(matched) >= max_products:
            break
    return matched or products[:max_products]
