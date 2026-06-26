"""AI Search readiness scoring for Shopify products."""

from __future__ import annotations

from typing import Any

from app.geo.facts import analyze_product_facts
from app.snapshot.scope import filter_products_by_scope, summarize_product_scopes

_SEO_TITLE_MIN = 30
_SEO_TITLE_MAX = 70
_SEO_DESC_MIN = 70
_SEO_DESC_MAX = 160

_ACTION_METADATA: dict[str, dict[str, str]] = {
    "facts": {"impact_estimate": "high", "effort_estimate": "low"},
    "schema": {"impact_estimate": "medium", "effort_estimate": "medium"},
    "answerability": {"impact_estimate": "high", "effort_estimate": "medium"},
    "trust": {"impact_estimate": "medium", "effort_estimate": "medium"},
    "seo": {"impact_estimate": "high", "effort_estimate": "low"},
    "commerce": {"impact_estimate": "medium", "effort_estimate": "low"},
    "niche": {"impact_estimate": "high", "effort_estimate": "low"},
    "crawl": {"impact_estimate": "high", "effort_estimate": "medium"},
}


def _level(score: int) -> str:
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "bon"
    if score >= 45:
        return "partiel"
    return "faible"


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


def _niche_trust_adjustment(
    product: dict[str, Any],
    niche_hypothesis: dict[str, Any] | None,
) -> tuple[float, list[dict]]:
    """Return (score_delta ≤0, niche_alerts) from forbidden promises and brand voice checks."""
    if not niche_hypothesis or niche_hypothesis.get("status") != "validated_by_merchant":
        return 0.0, []
    body = _description(product).lower()
    alerts: list[dict] = []
    malus = 0.0
    for item in niche_hypothesis.get("forbidden_promises", []):
        promise = str(item.get("promise") or "").lower()
        if promise and promise in body:
            malus = min(malus + 0.10, 0.30)
            alerts.append({"type": "forbidden_promise", "detail": str(item.get("promise", ""))})
    for phrase in niche_hypothesis.get("brand_voice", {}).get("do_not_say", []):
        if phrase and phrase.lower() in body:
            alerts.append({"type": "brand_voice_violation", "detail": str(phrase)})
    return -malus, alerts


def _niche_answerability_adjustment(
    fact_keys: set[str],
    desc: str,
    niche_hypothesis: dict[str, Any] | None,
) -> float:
    """Return score delta (capped ±0.05) from niche conversational intents coverage."""
    if not niche_hypothesis or niche_hypothesis.get("status") != "validated_by_merchant":
        return 0.0
    intents = niche_hypothesis.get("conversational_intents", [])
    if not intents:
        return 0.0
    desc_lower = desc.lower()
    covered = sum(
        1
        for intent_item in intents
        if any(
            kw.lower() in fact_keys or kw.lower() in desc_lower
            for kw in (
                [str(intent_item.get("intent") or "")]
                + [str(q) for q in intent_item.get("example_queries", [])]
            )
            if kw
        )
    )
    ratio = covered / len(intents)
    return round((ratio - 0.5) * 0.10, 3)


def _crawl_seo_adjustment(
    product: dict[str, Any],
    crawl_findings: list[dict[str, Any]] | None,
) -> float:
    """Return SEO score delta (≤0) from crawl L3 findings matching this product's URL handle."""
    if not crawl_findings:
        return 0.0
    handle = str(product.get("handle") or "").lower()
    if not handle:
        return 0.0
    product_findings = [f for f in crawl_findings if handle in str(f.get("url") or "").lower()]
    delta = 0.0
    for finding in product_findings:
        issue_type = str(finding.get("issue_type") or "")
        if issue_type in ("page_404", "server_error"):
            delta -= 0.20
        elif issue_type == "redirect_chain":
            delta -= 0.10
        elif issue_type == "missing_canonical":
            delta -= 0.05
    return max(delta, -0.30)


def _build_reasons(
    components_flat: dict[str, int],
    niche_alerts: list[dict],
) -> list[dict]:
    """Build at most 6 diagnostic reasons from component scores and niche alerts."""
    label_map = [
        ("facts", "Insufficient product facts"),
        ("answerability", "Low answerability for AI responses"),
        ("trust", "Missing trust signals"),
        ("seo", "SEO metadata gaps"),
        ("schema", "Incomplete structured data"),
        ("commerce", "Commerce data incomplete"),
    ]
    reasons: list[dict] = []
    for key, label in label_map:
        s = components_flat.get(key, 100)
        if s < 30:
            severity = "critical"
        elif s < 60:
            severity = "warning"
        else:
            continue
        reasons.append({"category": key, "label": label, "severity": severity})

    for alert in niche_alerts[:2]:
        reasons.append({
            "category": "niche",
            "label": str(alert.get("detail", "Niche guideline violation")),
            "severity": "warning",
        })

    return reasons[:6]


def _build_recommended_actions(
    recs_by_category: list[tuple[str, list[str]]],
) -> list[dict]:
    """Build at most 3 recommended actions with impact/effort estimates."""
    actions: list[dict] = []
    for category, recs in recs_by_category:
        meta = _ACTION_METADATA.get(category, {"impact_estimate": "medium", "effort_estimate": "medium"})
        for rec in recs:
            actions.append({"action": rec, "category": category, **meta})
            if len(actions) >= 3:
                return actions
    return actions


def score_product_readiness(
    product: dict[str, Any],
    *,
    niche_hypothesis: dict[str, Any] | None = None,
    crawl_findings: list[dict[str, Any]] | None = None,
    extra_fact_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Score one product for AI Search readiness.

    The score is an internal readiness indicator, not a ranking guarantee.
    extra_fact_keys: merchant-confirmed fact keys not yet in the Shopify snapshot
    (e.g. answered via the enrichment form). They are merged into fact_keys so the
    score reflects what the merchant has confirmed, not only what is already in Shopify.
    """
    from app.geo.facts import _SENSITIVE_FACTS  # noqa: PLC0415

    facts = analyze_product_facts(product)
    fact_keys = {fact["key"] for fact in facts["confirmed_facts"]}
    if extra_fact_keys:
        fact_keys |= extra_fact_keys
        _sensitive_set = frozenset(k for k, _ in _SENSITIVE_FACTS)
        facts_score = round(len(_sensitive_set & fact_keys) / len(_sensitive_set), 2)
    else:
        facts_score = facts["completeness_score"]

    seo_score, seo_recs = _seo_score(product)
    schema_score, schema_recs = _schema_score(product, fact_keys)
    answer_score, answer_recs = _answer_score(product, fact_keys)
    trust_score, trust_recs = _trust_score(fact_keys)
    commerce_score, commerce_recs = _commerce_score(product)

    niche_trust_delta, niche_alerts = _niche_trust_adjustment(product, niche_hypothesis)
    niche_answer_delta = _niche_answerability_adjustment(fact_keys, _description(product), niche_hypothesis)
    crawl_seo_delta = _crawl_seo_adjustment(product, crawl_findings)

    adj_trust = max(0.0, min(1.0, trust_score + niche_trust_delta))
    adj_answer = max(0.0, min(1.0, answer_score + niche_answer_delta))
    adj_seo = max(0.0, min(1.0, seo_score + crawl_seo_delta))

    weighted = (
        0.25 * facts_score
        + 0.20 * schema_score
        + 0.20 * adj_answer
        + 0.15 * adj_trust
        + 0.10 * adj_seo
        + 0.10 * commerce_score
    )
    score = round(weighted * 100)
    level = _level(score)

    components = {
        "facts": {"score": round(facts_score * 100), "weight": 0.25},
        "schema": {"score": round(schema_score * 100), "weight": 0.20},
        "answerability": {"score": round(adj_answer * 100), "weight": 0.20},
        "trust": {"score": round(adj_trust * 100), "weight": 0.15},
        "seo": {"score": round(adj_seo * 100), "weight": 0.10},
        "commerce": {"score": round(commerce_score * 100), "weight": 0.10},
    }
    components_flat = {k: v["score"] for k, v in components.items()}

    recommendations = (
        facts["suggestions_to_verify"][:2]
        + [{"key": "answerability", "label": "Answerability", "instruction": rec} for rec in answer_recs]
        + [{"key": "schema", "label": "Structured data", "instruction": rec} for rec in schema_recs]
        + [{"key": "trust", "label": "Trust", "instruction": rec} for rec in trust_recs]
        + [{"key": "seo", "label": "SEO", "instruction": rec} for rec in seo_recs]
        + [{"key": "commerce", "label": "Commerce", "instruction": rec} for rec in commerce_recs]
    )

    recs_by_category: list[tuple[str, list[str]]] = []
    if niche_alerts:
        recs_by_category.append(("niche", [a["detail"] for a in niche_alerts if "detail" in a]))
    recs_by_category += [
        ("facts", [r["instruction"] for r in facts["suggestions_to_verify"][:2] if isinstance(r, dict) and "instruction" in r]),
        ("answerability", answer_recs),
        ("seo", seo_recs),
        ("trust", trust_recs),
        ("schema", schema_recs),
        ("commerce", commerce_recs),
    ]

    reasons = _build_reasons(components_flat, niche_alerts)
    recommended_actions = _build_recommended_actions(recs_by_category)

    return {
        "id": product.get("id", ""),
        "handle": product.get("handle", ""),
        "title": product.get("title", ""),
        "readiness_score": score,
        "level": level,
        "components": components,
        "confirmed_fact_count": facts["confirmed_count"],
        "missing_fact_count": facts["missing_count"],
        "recommendations": recommendations[:5],
        "reasons": reasons,
        "recommended_actions": recommended_actions,
        "niche_alerts": niche_alerts,
        "note": "Internal readiness score only; it does not guarantee ranking or citation in AI search.",
    }


def score_catalog_readiness(
    products: list[dict[str, Any]],
    top: int = 50,
    *,
    scope: str = "active",
    niche_hypothesis: dict[str, Any] | None = None,
    crawl_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score a product catalog for AI Search readiness."""
    scoped_products = filter_products_by_scope(products, scope)
    rows = [
        score_product_readiness(
            product,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings,
        )
        for product in scoped_products
        if product.get("title")
    ]
    rows.sort(key=lambda item: (item["readiness_score"], item["title"]))
    limited = rows[:top]
    total = len(rows)
    avg_score = round(sum(row["readiness_score"] for row in rows) / total) if total else 0
    global_level = _level(avg_score)

    all_niche_alerts = [alert for row in rows for alert in row.get("niche_alerts", [])]

    if crawl_findings is not None:
        by_sev: dict[str, int] = {}
        for f in crawl_findings:
            s = str(f.get("severity") or "info")
            by_sev[s] = by_sev.get(s, 0) + 1
        crawl_health: dict[str, Any] = {
            "available": True,
            "critical": by_sev.get("critical", 0),
            "high": by_sev.get("high", 0),
            "medium": by_sev.get("medium", 0),
            "low": by_sev.get("low", 0),
            "info": by_sev.get("info", 0),
        }
    else:
        crawl_health = {"available": False}

    return {
        "total": total,
        "global_score": avg_score,
        "global_level": global_level,
        "scope": summarize_product_scopes(products, scope),
        "summary": {
            "avg_readiness_score": avg_score,
            "excellent_products": sum(1 for row in rows if row["level"] == "excellent"),
            "bon_products": sum(1 for row in rows if row["level"] == "bon"),
            "partiel_products": sum(1 for row in rows if row["level"] == "partiel"),
            "faible_products": sum(1 for row in rows if row["level"] == "faible"),
            "score_note": "AI Search Readiness is an internal diagnostic score, not a visibility promise.",
        },
        "niche_alerts": all_niche_alerts[:10],
        "crawl_health": crawl_health,
        "products": limited,
    }
