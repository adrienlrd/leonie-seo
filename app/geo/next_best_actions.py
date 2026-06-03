"""Next Best Action Loop for GEO optimization (task 125).

Transforms validated impact reports into concrete, prioritised action
recommendations. Every suggested action is dry-run by default; no Shopify
write is triggered without explicit merchant confirmation.
"""

from __future__ import annotations

from typing import Any

from app.learning.policy import learning_boost_for_action
from app.snapshot.scope import filter_products_by_scope, summarize_product_scopes

_ACTION_PRIORITY: dict[str, str] = {
    "répliquer": "high",
    "rollback": "high",
    "ajuster": "medium",
    "attendre": "low",
}

_RATIONALES: dict[str, str] = {
    "répliquer": (
        "L'optimisation a produit un impact positif probable. "
        "Appliquer la même action sur des pages similaires pour amplifier le gain."
    ),
    "ajuster": (
        "L'impact est neutre. Affiner les facts produits, la FAQ ou le schéma "
        "pour renforcer la pertinence GEO avant de mesurer à nouveau."
    ),
    "rollback": (
        "Le score GEO a diminué après l'optimisation. "
        "Examiner le changement et envisager un rollback pour limiter la perte."
    ),
    "attendre": (
        "Données insuffisantes pour conclure. "
        "Attendre la prochaine fenêtre de validation (J+14 ou J+28) avant d'agir."
    ),
}


def _similar_products(
    source_resource_id: str,
    source_resource_type: str,
    snapshot: dict[str, Any] | None,
    already_optimized_ids: set[str],
    scope: str,
    max_suggestions: int = 3,
) -> list[dict[str, Any]]:
    """Return similar unoptimized products from the snapshot catalog."""
    if not snapshot or source_resource_type != "product":
        return []

    products = filter_products_by_scope(snapshot.get("products") or [], scope)
    # Find source product to extract category signal
    source = next(
        (p for p in products if str(p.get("id") or "") == source_resource_id),
        None,
    )
    source_type = (source or {}).get("product_type") or ""
    source_vendor = (source or {}).get("vendor") or ""

    suggestions: list[dict[str, Any]] = []
    for product in products:
        pid = str(product.get("id") or "")
        if pid == source_resource_id or pid in already_optimized_ids:
            continue
        # Match by product_type or vendor for similarity
        p_type = product.get("product_type") or ""
        p_vendor = product.get("vendor") or ""
        if (source_type and p_type == source_type) or (source_vendor and p_vendor == source_vendor):
            suggestions.append(
                {
                    "resource_id": pid,
                    "resource_title": product.get("title") or pid,
                    "resource_type": "product",
                    "similarity_reason": (
                        f"Même type : {p_type}"
                        if p_type == source_type
                        else f"Même marque : {p_vendor}"
                    ),
                }
            )
        if len(suggestions) >= max_suggestions:
            break

    return suggestions


def build_next_best_actions(
    reports: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
    *,
    scope: str = "active",
    shop: str | None = None,
) -> dict[str, Any]:
    """Build a prioritised next-best-action list from validated event reports.

    Args:
        reports: Output of ``build_catalog_report``'s ``reports`` list.
        snapshot: Optional catalog snapshot for similar-product suggestions.

    Returns:
        Dict with ``actions`` list, ``summary`` and ``dry_run`` flag.
    """
    already_optimized_ids: set[str] = {str(r.get("resource_id") or "") for r in reports}

    all_products = (snapshot or {}).get("products") or []
    scoped_products = filter_products_by_scope(all_products, scope) if snapshot else []
    scoped_product_ids = {str(product.get("id") or "") for product in scoped_products}

    actions: list[dict[str, Any]] = []
    by_action: dict[str, int] = {
        "répliquer": 0,
        "ajuster": 0,
        "rollback": 0,
        "attendre": 0,
    }

    for report in reports:
        if snapshot and str(report.get("resource_type") or "product") == "product":
            resource_id = str(report.get("resource_id") or "")
            if resource_id and resource_id not in scoped_product_ids:
                continue

        action_type = report.get("next_recommendation") or "attendre"
        verdict = report.get("verdict") or "inconclusif"
        priority = _ACTION_PRIORITY.get(action_type, "low")
        rationale = _RATIONALES.get(action_type, "")
        learning_signal = (
            learning_boost_for_action(
                shop=shop,
                action_type=str(report.get("action_type") or "review_product"),
            )
            if shop
            else {"learning_boost": 0, "reason": "Learning not scoped."}
        )

        suggestions: list[dict[str, Any]] = []
        if action_type == "répliquer":
            suggestions = _similar_products(
                source_resource_id=str(report.get("resource_id") or ""),
                source_resource_type=str(report.get("resource_type") or "product"),
                snapshot=snapshot,
                already_optimized_ids=already_optimized_ids,
                scope=scope,
            )

        actions.append(
            {
                "source_event_id": report.get("event_id"),
                "source_resource_id": report.get("resource_id"),
                "source_resource_title": report.get("resource_title") or report.get("resource_id"),
                "source_action_type": report.get("action_type"),
                "verdict": verdict,
                "action_type": action_type,
                "priority": priority,
                "rationale": rationale,
                "learning": learning_signal,
                "suggested_resources": suggestions,
                "dry_run": True,
            }
        )
        by_action[action_type] = by_action.get(action_type, 0) + 1

    # Sort: high priority first, then rollback before replicate
    _priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: (_priority_order.get(a["priority"], 3), a["action_type"]))

    high_count = sum(1 for a in actions if a["priority"] == "high")

    return {
        "actions": actions,
        "summary": {
            "total_actions": len(actions),
            "high_priority": high_count,
            "by_action": by_action,
        },
        "scope": summarize_product_scopes(all_products, scope) if snapshot else None,
        "dry_run": True,
    }
