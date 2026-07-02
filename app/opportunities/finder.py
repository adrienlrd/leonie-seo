"""Opportunity Finder — deterministic 7-signal aggregation for product pages."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.geo.competitors import build_competitor_monitor
from app.geo.readiness import score_product_readiness
from app.niche.clustering import cluster_products
from app.niche.gaps import analyze_keyword_gaps
from app.niche.intent import cluster_gsc_queries
from app.shop_identity import brand_terms
from app.snapshot.scope import filter_products_by_scope, summarize_product_scopes
from scripts.audit.detect_gsc_opportunities import classify_url
from scripts.audit.detect_issues import detect_duplicate_content

_WEIGHTS: dict[str, float] = {
    "gsc_signal": 0.30,
    "keyword_gap": 0.20,
    "audit_pressure": 0.15,
    "intent_match": 0.10,
    "cannibalization": 0.10,
    "link_opportunity": 0.10,  # V1: always 0 — no link graph yet
    "competitor_pressure": 0.05,
}


def _normalize_text(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", _normalize_text(text)))


def _product_url(shop_domain: str, handle: str) -> str:
    return f"https://{shop_domain}/products/{handle}".rstrip("/")


def _path(value: str) -> str:
    parsed = urlparse(value)
    return (parsed.path if parsed.scheme else value).rstrip("/") or "/"


def _gsc_row_for_product(
    product: dict[str, Any],
    shop_domain: str,
    gsc_page_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    handle = str(product.get("handle") or "")
    url = _product_url(shop_domain, handle)
    if url in gsc_page_rows:
        return gsc_page_rows[url]
    target_path = _path(url)
    for row_url, row in gsc_page_rows.items():
        if _path(row_url) == target_path:
            return row
    return {}


def _gsc_signal_for_product(
    product: dict[str, Any],
    shop_domain: str,
    gsc_page_rows: dict[str, dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    gsc = _gsc_row_for_product(product, shop_domain, gsc_page_rows)
    if not gsc:
        return 0.0, {}

    handle = str(product.get("handle") or "")
    url = _product_url(shop_domain, handle)
    impressions = int(gsc.get("impressions", 0) or 0)
    position = float(gsc.get("position", 0.0) or 0.0)
    ctr = float(gsc.get("ctr", 0.0) or 0.0)

    zone = classify_url(url, position, impressions, ctr)
    zone_scores: dict[str, float] = {"quick_win": 1.0, "low_ctr": 0.7, "long_term": 0.5}
    value = zone_scores.get(zone or "", 0.0)

    return value, {
        "zone": zone,
        "impressions": impressions,
        "position": round(position, 2),
        "clicks": int(gsc.get("clicks", 0) or 0),
        "ctr": round(ctr, 4),
    }


def _keyword_gap_for_product(
    product: dict[str, Any],
    gaps: list[Any],
    clusters: list[Any],
) -> tuple[float, dict[str, Any]]:
    product_id = str(product.get("id") or "")
    product_cluster_names = {c.name for c in clusters if product_id in c.product_ids}

    if not product_cluster_names:
        return 0.0, {}

    best_gap = None
    max_score = 0.0
    for gap in gaps:
        if gap.cluster_name in product_cluster_names and gap.opportunity_score > max_score:
            max_score = gap.opportunity_score
            best_gap = gap

    if best_gap is None:
        return 0.0, {"cluster_names": list(product_cluster_names)}

    return max_score, {
        "query": best_gap.query,
        "impressions": best_gap.impressions,
        "opportunity_score": best_gap.opportunity_score,
        "cluster_name": best_gap.cluster_name,
    }


def _audit_pressure(readiness_score: int) -> float:
    return (100 - readiness_score) / 100


def _intent_match_boost(
    product: dict[str, Any],
    intent_clusters: list[Any],
    niche_hypothesis: dict[str, Any] | None,
) -> tuple[float, dict[str, Any]]:
    title_tokens = _tokens(product.get("title") or "")

    for cluster in intent_clusters:
        kw_tokens: set[str] = set()
        for kw in cluster.top_keywords:
            kw_tokens.update(_tokens(kw))
        for q in cluster.queries[:5]:
            kw_tokens.update(_tokens(q))

        if not (title_tokens & kw_tokens):
            continue

        matched_info = {
            "cluster_name": cluster.name,
            "intent": str(cluster.intent),
            "top_keywords": cluster.top_keywords[:5],
        }

        if niche_hypothesis and niche_hypothesis.get("status") == "validated_by_merchant":
            for ci in niche_hypothesis.get("conversational_intents", []):
                if ci.get("confidence") not in {"high", "medium"}:
                    continue
                ci_tokens: set[str] = set()
                for eq in ci.get("example_queries", []):
                    ci_tokens.update(_tokens(eq))
                if kw_tokens & ci_tokens:
                    return 1.0, {**matched_info, "niche_validated": True}
            return 0.5, {**matched_info, "niche_validated": False}

        return 0.5, {**matched_info, "niche_validated": False}

    return 0.0, {}


def _cannibalization_for_product(
    product: dict[str, Any],
    duplicate_issues: list[Any],
) -> tuple[float, dict[str, Any]]:
    product_id = str(product.get("id") or "")
    count = sum(1 for issue in duplicate_issues if issue.resource_id == product_id)
    return min(count / 3, 1.0), {"duplicate_issue_count": count}


def _competitor_pressure(
    product: dict[str, Any],
    competitor_report: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    domains = competitor_report.get("competitor_domains", [])
    domain_count = len(domains)
    if domain_count == 0:
        return 0.0, {}

    handle = str(product.get("handle") or "")
    matched_queries = 0
    for query in competitor_report.get("queries", []):
        for match in query.get("matching_products", []):
            if match.get("handle") == handle:
                matched_queries += 1
                break

    if matched_queries == 0:
        return 0.0, {}

    return min(domain_count / 5, 1.0), {
        "competitor_domains": domain_count,
        "matched_queries": matched_queries,
    }


def _apply_niche_adjustments(
    score: float,
    product: dict[str, Any],
    niche_hypothesis: dict[str, Any] | None,
) -> tuple[float, list[dict[str, Any]]]:
    if not niche_hypothesis or niche_hypothesis.get("status") != "validated_by_merchant":
        return score, []

    alerts: list[dict[str, Any]] = []
    adjusted = score
    product_id = str(product.get("id") or "")

    # forbidden_promises → alert only (score malus already applied by readiness Trust component)
    desc = (
        product.get("descriptionHtml") or product.get("body_html") or product.get("description") or ""
    ).lower()
    for fp in niche_hypothesis.get("forbidden_promises", []):
        promise_text = str(fp.get("promise") or "").lower()
        if promise_text and promise_text[:20] in desc:
            alerts.append({"type": "forbidden_promise", "detail": fp.get("promise", "")})

    # priority_products → +10 pts bonus (cap 100)
    for pp in niche_hypothesis.get("priority_products", []):
        if str(pp.get("product_id") or "") == product_id:
            adjusted = min(adjusted + 10, 100.0)
            break

    return adjusted, alerts


def _confidence(signals: list[dict[str, Any]]) -> str:
    non_zero = sum(1 for s in signals if s["value"] > 0)
    if non_zero >= 3:
        return "high"
    if non_zero >= 1:
        return "medium"
    return "low"


def _tier(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _primary_reason(signals: list[dict[str, Any]], product_title: str) -> str:
    weighted = [(s["weight"] * s["value"], s) for s in signals]
    if not weighted or all(v == 0 for v, _ in weighted):
        return f"Aucun signal fort détecté pour {product_title}."

    _, best_sig = max(weighted, key=lambda x: x[0])
    ev = best_sig.get("evidence", {})
    sig_type = best_sig["type"]

    if sig_type == "gsc_signal":
        zone = ev.get("zone", "")
        pos = ev.get("position", 0)
        imp = ev.get("impressions", 0)
        if zone == "quick_win":
            return f"Page positionnée {pos} avec {imp} impressions — quick win potentiel."
        if zone == "low_ctr":
            return f"CTR faible à la position {pos} avec {imp} impressions."
        if zone == "long_term":
            return f"Opportunité longue traîne : {imp} impressions à la position {pos}."
    if sig_type == "keyword_gap":
        q = ev.get("query", "")
        return f'Keyword gap identifié : "{q}" non couvert par ce produit.'
    if sig_type == "audit_pressure":
        r_score = 100 - int(best_sig["value"] * 100)
        return f"Score AI Search Readiness faible ({r_score}/100) — fort potentiel d'amélioration."
    if sig_type == "cannibalization":
        return f"Cannibalisation détectée : {ev.get('duplicate_issue_count', 0)} conflit(s) de contenu."
    if sig_type == "intent_match":
        return f"Correspond à un intent conversationnel : {ev.get('cluster_name', '')}."
    if sig_type == "competitor_pressure":
        return f"Pression concurrentielle : {ev.get('competitor_domains', 0)} domaines suivis."

    return f"Opportunité détectée pour {product_title}."


def find_opportunities_for_catalog(
    products: list[dict[str, Any]],
    shop_domain: str,
    gsc_page_rows: dict[str, dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    *,
    niche_hypothesis: dict[str, Any] | None = None,
    crawl_findings: list[dict[str, Any]] | None = None,
    scope: str = "active",
    top: int = 20,
) -> dict[str, Any]:
    """Rank product pages by deterministic 7-signal opportunity score.

    Args:
        products: Shopify product list from snapshot.
        shop_domain: Shopify shop domain (e.g. mystore.myshopify.com).
        gsc_page_rows: Page-level GSC data keyed by URL (from _parse_gsc_csv).
        gsc_query_rows: Query-level GSC rows [{query, impressions, clicks, position}].
        niche_hypothesis: Validated niche hypothesis or None.
        crawl_findings: Crawl L3 findings (passed to readiness scoring).
        scope: Product scope filter (default "active").
        top: Maximum number of opportunities to return.

    Returns:
        Opportunity catalogue dict with shop, opportunities, and summary.
    """
    scoped = filter_products_by_scope(products, scope)
    titled = [p for p in scoped if p.get("title")]

    clusters = cluster_products(titled)
    gaps = analyze_keyword_gaps(gsc_query_rows, clusters) if gsc_query_rows else []
    intent_clusters = (
        cluster_gsc_queries(gsc_query_rows, brand_terms=brand_terms(shop_domain))
        if gsc_query_rows
        else []
    )
    competitor_report = build_competitor_monitor(titled, gsc_query_rows or None)
    duplicate_issues = detect_duplicate_content(titled)

    rows: list[dict[str, Any]] = []
    for product in titled:
        readiness = score_product_readiness(
            product,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings,
        )
        r_score = int(readiness["readiness_score"])

        gsc_val, gsc_ev = _gsc_signal_for_product(product, shop_domain, gsc_page_rows)
        gap_val, gap_ev = _keyword_gap_for_product(product, gaps, clusters)
        pressure_val = _audit_pressure(r_score)
        intent_val, intent_ev = _intent_match_boost(product, intent_clusters, niche_hypothesis)
        canni_val, canni_ev = _cannibalization_for_product(product, duplicate_issues)
        comp_val, comp_ev = _competitor_pressure(product, competitor_report)

        signals: list[dict[str, Any]] = [
            {"type": "gsc_signal", "weight": _WEIGHTS["gsc_signal"], "value": round(gsc_val, 4), "evidence": gsc_ev},
            {"type": "keyword_gap", "weight": _WEIGHTS["keyword_gap"], "value": round(gap_val, 4), "evidence": gap_ev},
            {"type": "audit_pressure", "weight": _WEIGHTS["audit_pressure"], "value": round(pressure_val, 4), "evidence": {"readiness_score": r_score}},
            {"type": "intent_match", "weight": _WEIGHTS["intent_match"], "value": round(intent_val, 4), "evidence": intent_ev},
            {"type": "cannibalization", "weight": _WEIGHTS["cannibalization"], "value": round(canni_val, 4), "evidence": canni_ev},
            {"type": "link_opportunity", "weight": _WEIGHTS["link_opportunity"], "value": 0.0, "evidence": {}},
            {"type": "competitor_pressure", "weight": _WEIGHTS["competitor_pressure"], "value": round(comp_val, 4), "evidence": comp_ev},
        ]

        raw_score = 100.0 * sum(s["weight"] * s["value"] for s in signals)
        adjusted_score, niche_alerts = _apply_niche_adjustments(raw_score, product, niche_hypothesis)
        final_score = round(min(max(adjusted_score, 0.0), 100.0))

        matched_queries: list[str] = []
        matched_intents: list[str] = []
        if intent_val > 0 and intent_ev:
            cluster_name = intent_ev.get("cluster_name", "")
            for ic in intent_clusters:
                if ic.name == cluster_name:
                    matched_queries = ic.queries[:5]
                    matched_intents = [str(ic.intent)]
                    break

        rows.append({
            "product_id": str(product.get("id") or ""),
            "handle": str(product.get("handle") or ""),
            "title": str(product.get("title") or ""),
            "opportunity_score": final_score,
            "tier": _tier(final_score),
            "primary_reason": _primary_reason(signals, str(product.get("title") or "")),
            "signals": signals,
            "matched_queries": matched_queries,
            "matched_intents": matched_intents,
            "recommended_actions": readiness.get("recommended_actions", [])[:3],
            "niche_alerts": niche_alerts,
            "confidence": _confidence(signals),
        })

    rows.sort(key=lambda r: (-r["opportunity_score"], r["title"]))
    limited = rows[:top]

    by_tier: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    by_intent: dict[str, int] = {}
    for r in rows:
        tier = r["tier"]
        by_tier[tier] = by_tier.get(tier, 0) + 1
        for intent in r["matched_intents"]:
            by_intent[intent] = by_intent.get(intent, 0) + 1

    avg_score = round(sum(r["opportunity_score"] for r in rows) / len(rows)) if rows else 0

    return {
        "shop": shop_domain,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_products_scanned": len(rows),
        "scope": summarize_product_scopes(products, scope),
        "opportunities": limited,
        "summary": {
            "by_tier": by_tier,
            "by_intent": by_intent,
            "average_score": avg_score,
        },
    }
