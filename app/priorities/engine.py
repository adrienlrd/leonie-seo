"""Priority Engine — select exactly 3 top actions from the opportunity catalog."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.geo.prioritization import prioritize_catalog
from app.geo.risk_guard import assess_product_risk
from app.observability.metrics import check_budget
from app.opportunities.finder import find_opportunities_for_catalog
from app.snapshot.scope import filter_products_by_scope

_PROMPT_NAME = "priority_arbitrage"
_CACHE_TTL_HOURS = 24
_CANDIDATES_TOP = 50
_PRESCORE_TOP = 10

_PLAN_BUDGETS_USD: dict[str, float] = {
    "free": 0.50,
    "pro": 15.00,
    "agency": 75.00,
}

_EFFORT_MAP: dict[str, str] = {
    "enrich_product_facts": "high",
    "fix_cannibalization": "high",
    "improve_schema": "medium",
    "add_answer_blocks": "medium",
    "add_trust_proofs": "medium",
    "review_commerce_data": "medium",
    "improve_seo_copy": "low",
    "add_internal_link": "low",
    "review_product": "medium",
}

_EFFORT_NORM: dict[str, float] = {"low": 1 / 3, "medium": 2 / 3, "high": 1.0}
_CONF_MAP: dict[str, float] = {"high": 1.0, "medium": 0.6, "low": 0.3}

_SUCCESS_METRIC_WINDOW: dict[str, int] = {
    "enrich_product_facts": 30,
    "improve_schema": 30,
    "add_answer_blocks": 60,
    "add_trust_proofs": 30,
    "improve_seo_copy": 60,
    "review_commerce_data": 30,
    "fix_cannibalization": 90,
    "add_internal_link": 60,
    "review_product": 30,
}

_OUTPUT_TYPE: dict[str, str] = {
    "enrich_product_facts": "text",
    "improve_schema": "jsonld",
    "add_answer_blocks": "faq",
    "add_trust_proofs": "text",
    "improve_seo_copy": "meta",
    "review_commerce_data": "text",
    "fix_cannibalization": "text",
    "add_internal_link": "internal_link",
    "review_product": "text",
}


def _stable_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _llm_cache_lookup(
    shop: str,
    prompt_version: str,
    content_hash: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        row = conn.execute(
            """SELECT response_json FROM llm_cache
               WHERE shop = ? AND task_name = ? AND prompt_version = ? AND content_hash = ? AND expires_at > ?""",
            (shop, _PROMPT_NAME, prompt_version, content_hash, now),
        ).fetchone()
    if not row:
        return None
    raw = row["response_json"] if isinstance(row, dict) else row[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _llm_cache_store(
    shop: str,
    prompt_version: str,
    content_hash: str,
    result: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> None:
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC)
    expires = (now + timedelta(hours=_CACHE_TTL_HOURS)).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO llm_cache
               (shop, task_name, prompt_version, content_hash, response_json,
                tokens_in, tokens_out, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                shop,
                _PROMPT_NAME,
                prompt_version,
                content_hash,
                json.dumps(result),
                0,
                0,
                now.isoformat(),
                expires,
            ),
        )


def _success_metric(action_type: str, readiness_score: int, impressions: int) -> dict[str, Any]:
    window = _SUCCESS_METRIC_WINDOW.get(action_type, 30)
    if action_type in {"improve_seo_copy", "fix_cannibalization", "add_internal_link"}:
        target = round(impressions * 1.3) if impressions > 0 else impressions + 50
        return {
            "name": "gsc_impressions",
            "current_value": impressions,
            "target_value": target,
            "measurement_window_days": window,
            "source": "gsc",
        }
    target = min(100, readiness_score + 15)
    return {
        "name": "readiness_score",
        "current_value": readiness_score,
        "target_value": target,
        "measurement_window_days": window,
        "source": "audit_readiness",
    }


def _why_now_deterministic(opp: dict[str, Any], prio: dict[str, Any]) -> str:
    impressions = int(prio.get("impressions") or 0)
    position = float(prio.get("position") or 0.0)
    r_score = int(prio.get("readiness_score") or 50)
    revenue = float(prio.get("revenue_estimate") or 0.0)
    title = str(opp.get("title") or "ce produit")

    gsc_ev = next(
        (s["evidence"] for s in opp.get("signals", []) if s["type"] == "gsc_signal" and s["value"] > 0),
        None,
    )
    if gsc_ev:
        zone = gsc_ev.get("zone", "")
        if zone == "quick_win":
            return (
                f"Cette page reçoit {impressions} impressions Google à la position {position:.0f}. "
                f"Elle est au seuil de la première page — une amélioration ciblée peut augmenter le trafic rapidement."
            )
        if zone == "low_ctr":
            return (
                f"{title} est bien positionnée ({position:.0f}) mais son CTR est faible. "
                f"Un meilleur titre et une meta description peuvent doubler les clics."
            )
        if zone == "long_term":
            return (
                f"Avec {impressions} impressions à la position {position:.0f}, "
                f"{title} a un potentiel estimé à {revenue:.0f} €."
            )

    if r_score < 50:
        return (
            f"Le score AI Search Readiness de {title} est de {r_score}/100. "
            f"Les manques de faits limitent sa visibilité dans les réponses IA."
        )

    return (
        f"{title} présente plusieurs signaux d'amélioration convergents. "
        f"Agir maintenant maximise l'impact avant le prochain cycle de crawl."
    )


def _preview_depends(action_type: str, niche_hypothesis: dict[str, Any] | None) -> list[str]:
    deps = ["product_facts_layer"]
    if action_type in {"add_answer_blocks", "enrich_product_facts"} and niche_hypothesis:
        deps.append("niche_hypothesis")
    if action_type == "improve_schema":
        deps.append("jsonld_current_state")
    return deps


def _build_evidence(opp: dict[str, Any], prio: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for sig in opp.get("signals", []):
        if sig["value"] <= 0:
            continue
        ev = sig.get("evidence", {})
        if sig["type"] == "gsc_signal":
            evidence.append({"source": "gsc", "metric": "impressions", "value": ev.get("impressions", 0)})
        elif sig["type"] == "keyword_gap":
            evidence.append({"source": "gsc", "metric": "keyword_gap_query", "value": ev.get("query", "")})
        elif sig["type"] == "audit_pressure":
            evidence.append({"source": "audit", "metric": "readiness_score", "value": ev.get("readiness_score", 0)})
        elif sig["type"] == "cannibalization":
            evidence.append({"source": "audit", "metric": "duplicate_issues", "value": ev.get("duplicate_issue_count", 0)})
    revenue = prio.get("revenue_estimate")
    if revenue and float(revenue) > 0:
        evidence.append({"source": "gsc", "metric": "revenue_estimate_eur", "value": float(revenue)})
    return evidence[:5]


def _build_action_dossier(
    rank: int,
    opp: dict[str, Any],
    prio: dict[str, Any],
    risk: dict[str, Any],
    niche_hypothesis: dict[str, Any] | None,
    priority_score: float,
    *,
    why_now: str | None = None,
) -> dict[str, Any]:
    action_type = str(prio.get("action_type") or "review_product")
    effort_str = _EFFORT_MAP.get(action_type, "medium")
    risk_status = str(risk.get("guard_status") or "safe")
    risk_level = "low" if risk_status == "safe" else "medium" if risk_status == "review_required" else "high"

    r_score = int(prio.get("readiness_score") or 50)
    impressions = int(prio.get("impressions") or 0)

    opp_score = int(opp.get("opportunity_score") or 0)
    impact = "high" if opp_score >= 70 else "medium" if opp_score >= 40 else "low"
    estimate_basis = "gsc_only" if impressions > 0 else "gsc+fallback"

    return {
        "rank": rank,
        "action_id": f"{opp['handle']}-{action_type}-{rank}",
        "product_id": str(opp.get("product_id") or ""),
        "product_handle": str(opp.get("handle") or ""),
        "product_title": str(opp.get("title") or ""),
        "action_type": action_type,
        "action_label": str(prio.get("action_label") or "Revoir le produit"),
        "priority_score": round(min(max(priority_score, 0.0), 100.0)),
        "why_now": why_now or _why_now_deterministic(opp, prio),
        "evidence": _build_evidence(opp, prio),
        "estimates": {
            "impact": impact,
            "confidence": str(opp.get("confidence") or "low"),
            "effort": effort_str,
            "risk": risk_level,
            "click_gain_estimate": prio.get("clicks_gain_estimate"),
            "revenue_estimate_eur": prio.get("revenue_estimate"),
            "estimate_basis": estimate_basis,
        },
        "success_metric": _success_metric(action_type, r_score, impressions),
        "preview": {
            "depends_on": _preview_depends(action_type, niche_hypothesis),
            "expected_output_type": _OUTPUT_TYPE.get(action_type, "text"),
            "human_review_required": True,
        },
        "risk_guard": {
            "status": "review_required" if risk_status == "protected" else risk_status,
            "reasons": list(risk.get("reasons") or []),
            "override_required": risk_status in {"review_required", "protected"},
        },
        "niche_alerts": [
            {"type": str(a.get("type") or ""), "message": str(a.get("detail") or "")}
            for a in opp.get("niche_alerts", [])
        ],
    }


def _pre_score(
    opp: dict[str, Any],
    prio: dict[str, Any],
    risk: dict[str, Any],
    niche_hypothesis: dict[str, Any] | None,
) -> float:
    opp_score = float(opp.get("opportunity_score") or 0) / 100.0
    revenue = float(prio.get("revenue_estimate") or 0.0)
    bv = min(revenue / 200.0, 1.0)
    confidence = _CONF_MAP.get(str(opp.get("confidence") or "low"), 0.3)

    niche_boost = 0.0
    if niche_hypothesis and niche_hypothesis.get("status") == "validated_by_merchant":
        pid = str(opp.get("product_id") or "")
        for pp in niche_hypothesis.get("priority_products", []):
            if str(pp.get("product_id") or "") == pid:
                niche_boost = 1.0
                break

    action_type = str(prio.get("action_type") or "review_product")
    effort_norm = _EFFORT_NORM.get(_EFFORT_MAP.get(action_type, "medium"), 2 / 3)
    risk_norm = float(risk.get("risk_score") or 0) / 100.0

    return (
        0.40 * opp_score
        + 0.25 * bv
        + 0.15 * confidence
        + 0.10 * niche_boost
        - 0.05 * effort_norm
        - 0.05 * risk_norm
    )


def _try_llm_arbitrage(
    shop: str,
    candidates: list[dict[str, Any]],
    niche_hypothesis: dict[str, Any] | None,
    llm_router: Any,
    *,
    db_path: Path | None = None,
) -> list[dict[str, str]] | None:
    """Attempt LLM arbitrage. Returns [{action_id, why_now}] or None."""
    from app.llm.prompts import load_prompt  # noqa: PLC0415
    from app.llm.provider import LLMError  # noqa: PLC0415

    try:
        prompt_template = load_prompt(_PROMPT_NAME)
    except Exception:
        return None

    compact = [
        {
            "action_id": c["action_id"],
            "product_title": c["product_title"],
            "action_type": c["action_type"],
            "action_label": c["action_label"],
            "priority_score": c["priority_score"],
            "confidence": c["estimates"]["confidence"],
            "evidence": c["evidence"][:2],
        }
        for c in candidates
    ]

    niche_ctx: dict[str, Any] = {}
    if niche_hypothesis and niche_hypothesis.get("status") == "validated_by_merchant":
        sh = niche_hypothesis.get("shop_summary", {})
        niche_ctx = {
            "primary_niche": str(sh.get("primary_niche") or ""),
            "conversational_intents": [
                str(ci.get("intent") or "")
                for ci in niche_hypothesis.get("conversational_intents", [])[:3]
            ],
        }

    content_hash = _stable_hash({"candidates": compact, "niche": niche_ctx})
    cached = _llm_cache_lookup(shop, prompt_template.version, content_hash, db_path=db_path)
    if cached is not None:
        return cached.get("selections")

    try:
        rendered = prompt_template.render_user(
            candidates_json=json.dumps(compact, ensure_ascii=False),
            niche_context_json=json.dumps(niche_ctx, ensure_ascii=False),
        )
        result = llm_router.complete(
            rendered,
            system=prompt_template.system,
            max_tokens=prompt_template.max_tokens,
            temperature=prompt_template.temperature,
        )
        raw = result.text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines and lines[-1].startswith("```") else lines[1:]).strip()

        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return None

        selections = [
            {"action_id": str(s.get("action_id") or ""), "why_now": str(s.get("why_now") or "")}
            for s in parsed[:3]
            if isinstance(s, dict) and s.get("action_id") and s.get("why_now")
        ]
        if selections:
            _llm_cache_store(shop, prompt_template.version, content_hash, {"selections": selections}, db_path=db_path)
            return selections
    except (LLMError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        pass

    return None


def build_priority_actions(
    products: list[dict[str, Any]],
    shop_domain: str,
    shop: str,
    gsc_page_rows: dict[str, dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    *,
    niche_hypothesis: dict[str, Any] | None = None,
    crawl_findings: list[dict[str, Any]] | None = None,
    scope: str = "active",
    llm_router: Any | None = None,
    plan: str = "free",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build exactly 3 priority action dossiers from the opportunity catalog.

    Runs a 4-step pipeline: pull opportunities → Risk Guard filter →
    deterministic pre-score → LLM arbitrage (or fallback).

    Args:
        products: Shopify product list from snapshot.
        shop_domain: Shop domain (e.g. mystore.myshopify.com).
        shop: Shop identifier for auth and budget lookups.
        gsc_page_rows: Page-level GSC data keyed by URL.
        gsc_query_rows: Query-level GSC rows.
        niche_hypothesis: Validated niche hypothesis or None.
        crawl_findings: Crawl L3 findings or None.
        scope: Product scope filter.
        llm_router: Injected LLM router (defaults to get_router if None).
        plan: Merchant plan tier (free/pro/agency).
        db_path: Override DB path (tests only).

    Returns:
        Dict with "actions" (≤3), metadata, llm_used flag, fallback_reason.
    """
    now = datetime.now(UTC)

    # Step 1: Pull opportunities (top 50)
    opps_result = find_opportunities_for_catalog(
        products,
        shop_domain,
        gsc_page_rows,
        gsc_query_rows,
        niche_hypothesis=niche_hypothesis,
        crawl_findings=crawl_findings,
        scope=scope,
        top=_CANDIDATES_TOP,
    )
    all_opps = opps_result.get("opportunities", [])

    if not all_opps:
        return {
            "shop": shop,
            "generated_at": now.isoformat(),
            "scope": scope,
            "actions": [],
            "candidates_evaluated": 0,
            "sparse_signal": True,
            "llm_used": False,
            "fallback_reason": "no_opportunities",
            "next_refresh_at": (now + timedelta(days=7)).isoformat(),
        }

    # Index prioritize_catalog by handle for revenue / action_type data
    prio_result = prioritize_catalog(
        products,
        shop_domain,
        gsc_page_rows,
        top=_CANDIDATES_TOP,
        scope=scope,
    )
    prio_by_handle: dict[str, dict[str, Any]] = {r["handle"]: r for r in prio_result.get("rows", [])}

    # Step 2: Risk Guard filter — exclude protected products
    scoped = filter_products_by_scope(products, scope)
    products_by_handle: dict[str, dict[str, Any]] = {
        str(p.get("handle") or ""): p for p in scoped if p.get("title")
    }

    candidates: list[dict[str, Any]] = []
    for opp in all_opps:
        handle = str(opp.get("handle") or "")
        product = products_by_handle.get(handle)
        if not product:
            continue
        risk = assess_product_risk(product, shop_domain, gsc_page_rows)
        if risk["guard_status"] == "protected":
            continue
        prio = prio_by_handle.get(handle, {
            "action_type": "review_product",
            "action_label": "Revoir le produit",
            "readiness_score": 50,
            "impressions": 0,
            "revenue_estimate": 0.0,
            "clicks_gain_estimate": 0.0,
            "position": 0.0,
            "confidence": "low",
        })
        score = _pre_score(opp, prio, risk, niche_hypothesis)
        candidates.append({"opp": opp, "prio": prio, "risk": risk, "pre_score": score})

    # Step 3: Sort by pre-score, keep top 10
    candidates.sort(key=lambda c: -c["pre_score"])
    top10 = candidates[:_PRESCORE_TOP]

    if not top10:
        return {
            "shop": shop,
            "generated_at": now.isoformat(),
            "scope": scope,
            "actions": [],
            "candidates_evaluated": len(all_opps),
            "sparse_signal": True,
            "llm_used": False,
            "fallback_reason": "all_protected",
            "next_refresh_at": (now + timedelta(days=7)).isoformat(),
        }

    top10_dossiers = [
        _build_action_dossier(
            idx + 1,
            c["opp"],
            c["prio"],
            c["risk"],
            niche_hypothesis,
            round(c["pre_score"] * 100, 1),
        )
        for idx, c in enumerate(top10)
    ]

    # Step 4: LLM arbitrage (pro/agency with budget) or deterministic fallback
    llm_used = False
    fallback_reason: str | None = None
    selected_dossiers: list[dict[str, Any]] = top10_dossiers[:3]

    use_llm = plan in {"pro", "agency"}
    if use_llm:
        try:
            budget_usd = _PLAN_BUDGETS_USD.get(plan, _PLAN_BUDGETS_USD["free"])
            budget_check = check_budget(shop, budget_usd, db_path=db_path)
            if budget_check["over_budget"]:
                use_llm = False
                fallback_reason = "budget_exceeded"
        except Exception:
            use_llm = False
            fallback_reason = "budget_check_failed"

    if use_llm and llm_router is None:
        try:
            from app.llm import get_router  # noqa: PLC0415

            llm_router = get_router(shop=shop)
        except Exception:
            use_llm = False
            fallback_reason = "llm_unavailable"

    if use_llm and llm_router is not None:
        selections = _try_llm_arbitrage(
            shop, top10_dossiers, niche_hypothesis, llm_router, db_path=db_path
        )
        if selections:
            dossier_by_id = {d["action_id"]: d for d in top10_dossiers}
            reordered: list[dict[str, Any]] = []
            for rank, sel in enumerate(selections[:3], start=1):
                aid = str(sel.get("action_id") or "")
                if aid in dossier_by_id:
                    dossier = dict(dossier_by_id[aid])
                    dossier["rank"] = rank
                    why = str(sel.get("why_now") or "").strip()
                    if why:
                        dossier["why_now"] = why
                    reordered.append(dossier)
            if reordered:
                selected_dossiers = reordered
                llm_used = True
                fallback_reason = None
            else:
                fallback_reason = "llm_selection_empty"
        else:
            fallback_reason = fallback_reason or "llm_no_output"
    elif not llm_used:
        fallback_reason = fallback_reason or "plan_free"

    for i, dossier in enumerate(selected_dossiers, start=1):
        dossier["rank"] = i

    return {
        "shop": shop,
        "generated_at": now.isoformat(),
        "scope": scope,
        "actions": selected_dossiers,
        "candidates_evaluated": len(all_opps),
        "sparse_signal": len(selected_dossiers) < 3,
        "llm_used": llm_used,
        "fallback_reason": fallback_reason,
        "next_refresh_at": (now + timedelta(days=7)).isoformat(),
    }
