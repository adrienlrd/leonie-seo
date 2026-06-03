"""Continuous improvement agent for GEO corrections."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.apply.shopify_writer import ShopifyWriter
from app.content_actions.runner import run_content_action
from app.content_actions.schema import (
    ConfirmedFact,
    Constraints,
    ContentActionRequest,
    ContentStatus,
    ContentType,
    GscSignals,
    MissingFact,
    NicheContext,
    PreviousContent,
    ResourceInput,
)
from app.db_adapter import DB_PATH, get_conn
from app.geo.continuous_improvement import (
    enrich_market_analysis_result,
    merge_product_tags,
    upsert_product_tags,
)
from app.geo.ledger import create_geo_event, list_geo_events
from app.market_analysis.jobs import load_latest_result
from app.niche.understanding import get_validated_niche_hypothesis
from app.safe_apply.decisions import record_decision
from app.safe_apply.writer_adapters import is_live_supported, live_write
from app.safety import require_shopify_write_allowed

_WINDOWS_DAYS = (7, 30, 60)
_SENSITIVE_FACTS = {
    "materials",
    "origins",
    "certifications",
    "warranty",
    "dimensions",
    "compatibility",
}
_SAFE_ELEMENT_TO_CONTENT_TYPE: dict[str, ContentType] = {
    "meta_title": ContentType.META_TITLE,
    "meta_description": ContentType.META_DESCRIPTION,
    "product_description": ContentType.PRODUCT_DESCRIPTION,
}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_window(created_at: str | None, now: datetime) -> str | None:
    created = _parse_created_at(created_at)
    if created is None:
        return None
    elapsed = (now - created).days
    due = [day for day in _WINDOWS_DAYS if elapsed >= day]
    return f"J+{max(due)}" if due else None


def _observed_delta(event: dict[str, Any]) -> float:
    observed = event.get("observed_impact") or {}
    metrics_before = event.get("metrics_before") or {}
    metrics_after = event.get("metrics_after") or {}
    score_before = event.get("score_before")
    score_after = event.get("score_after")
    delta = 0.0
    if isinstance(score_before, int) and isinstance(score_after, int):
        delta += score_after - score_before
    for key in ("revenue", "clicks", "impressions", "conversions"):
        if key in observed:
            try:
                delta += float(observed.get(key) or 0)
            except (TypeError, ValueError):
                pass
    for key in ("clicks", "impressions", "conversions", "revenue"):
        if key in metrics_before or key in metrics_after:
            try:
                delta += float(metrics_after.get(key) or 0) - float(metrics_before.get(key) or 0)
            except (TypeError, ValueError):
                pass
    return delta


def _performance_status(delta: float) -> str:
    if delta > 0:
        return "positive"
    if delta < 0:
        return "negative"
    return "neutral"


def _record_tag_history(
    *,
    shop: str,
    product_id: str,
    tag: dict[str, Any],
    status_before: str,
    status_after: str,
    window: str,
    metrics: dict[str, Any],
    reason: str,
    db_path: Path | None = None,
) -> None:
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO tag_performance_history (
                shop, product_id, tag_id, label, status_before, status_after,
                window, metrics_json, reason, decided_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                product_id,
                str(tag.get("tag_id") or ""),
                str(tag.get("label") or ""),
                status_before,
                status_after,
                window,
                _json_dumps(metrics),
                reason,
                now,
            ),
        )


def _update_tags_from_feedback(
    shop: str,
    products: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    events_by_product: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("resource_type") != "product":
            continue
        window = _event_window(event.get("created_at"), now)
        if not window:
            continue
        events_by_product.setdefault(str(event.get("resource_id") or ""), []).append(event)

    decisions: list[dict[str, Any]] = []
    for product in products:
        product_id = str(product.get("product_id") or "")
        product_events = events_by_product.get(product_id, [])
        if not product_id or not product_events:
            continue
        tags = merge_product_tags(shop, product, persist=False, db_path=db_path)
        changed_tags: list[dict[str, Any]] = []
        for tag in tags:
            if tag.get("locked_by_merchant"):
                changed_tags.append(tag)
                continue
            relevant_events = product_events
            delta = sum(_observed_delta(event) for event in relevant_events)
            status_after = _performance_status(delta)
            if tag.get("tag_type") == "risk" and status_after == "positive":
                status_after = "negative"
            if status_after == "neutral":
                changed_tags.append(tag)
                continue
            status_before = str(tag.get("status") or "neutral")
            updated = {
                **tag,
                "status": status_after,
                "score": 100 if status_after == "positive" else 0,
                "reason": f"Updated from continuous improvement feedback ({delta:+.1f}).",
            }
            changed_tags.append(updated)
            window = _event_window(relevant_events[-1].get("created_at"), now) or "J+?"
            metrics = {
                "delta": delta,
                "event_ids": [event.get("id") for event in relevant_events],
                "windows": [
                    _event_window(event.get("created_at"), now) for event in relevant_events
                ],
            }
            _record_tag_history(
                shop=shop,
                product_id=product_id,
                tag=updated,
                status_before=status_before,
                status_after=status_after,
                window=window,
                metrics=metrics,
                reason=updated["reason"],
                db_path=db_path,
            )
            decisions.append(
                {
                    "product_id": product_id,
                    "tag": updated["label"],
                    "status_before": status_before,
                    "status_after": status_after,
                    "window": window,
                    "delta": delta,
                }
            )
        upsert_product_tags(shop, product_id, changed_tags, db_path=db_path)
    return decisions


def _confirmed_facts(pack: dict[str, Any]) -> list[ConfirmedFact]:
    facts: list[ConfirmedFact] = []
    for item in pack.get("confirmed_facts") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or item.get("label") or "")
        if not key:
            continue
        facts.append(
            ConfirmedFact(
                key=key,
                value=item.get("value", ""),
                source=str(item.get("source") or "market_analysis"),
            )
        )
    return facts


def _missing_facts(pack: dict[str, Any]) -> list[MissingFact]:
    facts: list[MissingFact] = []
    for key in pack.get("facts_missing") or []:
        clean = str(key)
        facts.append(
            MissingFact(
                key=clean, severity="sensitive" if clean in _SENSITIVE_FACTS else "standard"
            )
        )
    return facts


def _niche_context(product: dict[str, Any], tags: list[dict[str, Any]]) -> NicheContext:
    positive = [tag["label"] for tag in tags if tag.get("status") in {"positive", "forced"}]
    negative = [tag["label"] for tag in tags if tag.get("status") == "negative"]
    return NicheContext(
        primary_niche=str(product.get("target_customer") or ""),
        marketing_angles=positive[:8],
        forbidden_promises=negative[:8],
        conversational_intents=[
            {"intent": intent, "example_queries": []}
            for intent in product.get("buying_intents", [])[:5]
        ],
    )


def _request_for_product(
    product: dict[str, Any],
    content_type: ContentType,
    tags: list[dict[str, Any]],
) -> ContentActionRequest:
    pack = (
        product.get("content_test_pack")
        if isinstance(product.get("content_test_pack"), dict)
        else {}
    )
    keywords = [kw for kw in product.get("seo_keywords", []) if isinstance(kw, dict)]
    top_queries = [{"query": str(kw.get("query") or "")} for kw in keywords[:5]]
    positive = [tag["label"] for tag in tags if tag.get("status") in {"positive", "forced"}]
    negative = [tag["label"] for tag in tags if tag.get("status") == "negative"]
    feedback = (
        "Continuous improvement update. Prioritize positive tags: "
        f"{', '.join(positive[:8]) or 'none'}. Avoid negative tags: {', '.join(negative[:8]) or 'none'}."
    )
    return ContentActionRequest(
        content_type=content_type,
        resource=ResourceInput(
            type="product",
            id=str(product.get("product_id") or ""),
            handle=str(product.get("product_handle") or ""),
            title=str(product.get("product_title") or ""),
            current_seo={
                "title": str(pack.get("current_meta_title") or ""),
                "description": str(pack.get("current_meta_description") or ""),
            },
            current_description_html=str(pack.get("current_product_description_summary") or ""),
        ),
        confirmed_facts=_confirmed_facts(pack),
        missing_facts=_missing_facts(pack),
        gsc_signals=GscSignals(top_queries=top_queries),
        niche_context=_niche_context(product, tags),
        constraints=Constraints(locale="fr"),
        previous_content=PreviousContent(content="", feedback=feedback),
    )


def _candidate_actions(
    products: list[dict[str, Any]], *, max_actions: int
) -> list[tuple[dict[str, Any], str, ContentType]]:
    candidates: list[tuple[dict[str, Any], str, ContentType]] = []
    for product in products:
        elements = product.get("improvement_elements") or []
        tags = product.get("improvement_tags") or []
        has_negative = any(tag.get("status") == "negative" for tag in tags)
        for element in elements:
            key = str(element.get("key") or "")
            content_type = _SAFE_ELEMENT_TO_CONTENT_TYPE.get(key)
            if content_type is None:
                continue
            if element.get("improved") and not has_negative:
                continue
            candidates.append((product, key, content_type))
    candidates.sort(key=lambda item: int(item[0].get("opportunity_score") or 0), reverse=True)
    return candidates[:max_actions]


def _mark_action_approved(
    shop: str, action_id: str, *, db_path: Path | None = None
) -> dict[str, Any]:
    return record_decision(shop, action_id, "accept", db_path=db_path)


def _apply_safe_action(
    *,
    shop: str,
    access_token: str,
    action_id: str,
    content_type: ContentType,
    resource_id: str,
    text: str,
    confirm_live_write: bool,
    db_path: Path | None = None,
) -> dict[str, Any]:
    from app.content_actions.runner import _update_action_status  # noqa: PLC0415
    from app.safe_apply import writer_adapters  # noqa: PLC0415
    from app.safe_apply.writer_adapters import FIELD_FOR_CONTENT_TYPE  # noqa: PLC0415

    require_shopify_write_allowed(
        action="continuous_improvement_agent",
        dry_run=False,
        confirmed=confirm_live_write,
    )
    if not is_live_supported(content_type):
        return {"applied": False, "reason": "content_type_not_live_supported"}
    writer = ShopifyWriter(shop, access_token)
    write_result = live_write(content_type, resource_id, text, writer=writer)
    if not write_result.get("applied"):
        return {
            "applied": False,
            "reason": "; ".join(write_result.get("errors") or ["write_failed"]),
        }
    field = FIELD_FOR_CONTENT_TYPE.get(content_type)
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """INSERT INTO seo_changes
               (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status)
               VALUES (?, ?, 'product', ?, ?, ?, ?, 'applied')""",
            (shop, now, resource_id, field, write_result.get("old_value"), text),
        )
    _update_action_status(shop, action_id, ContentStatus.APPLIED, db_path=db_path)
    return {
        "applied": True,
        "field": writer_adapters.FIELD_FOR_CONTENT_TYPE.get(content_type),
        "applied_at": now,
    }


def _save_run(
    *,
    shop: str,
    mode: str,
    status: str,
    summary: dict[str, Any],
    proposals: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO continuous_improvement_agent_runs (
                shop, created_at, mode, status, summary_json, proposals_json, errors_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                now,
                mode,
                status,
                _json_dumps(summary),
                _json_dumps(proposals),
                _json_dumps(errors),
            ),
        )
        row = conn.execute(
            """
            SELECT id FROM continuous_improvement_agent_runs
            WHERE shop = ? AND created_at = ?
            ORDER BY id DESC LIMIT 1
            """,
            (shop, now),
        ).fetchone()
    return int((row or {}).get("id", 0))


def run_continuous_improvement_agent(
    shop: str,
    *,
    access_token: str | None = None,
    plan: str = "free",
    auto_apply: bool = False,
    confirm_live_write: bool = False,
    max_actions: int = 5,
    llm_router: Any | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run the continuous improvement agent.

    The agent measures J+7/J+30/J+60 feedback from the GEO ledger, updates tag
    status, generates content-action proposals, and live-applies only supported
    Shopify fields when auto_apply and confirm_live_write are both true.
    """
    latest = load_latest_result(shop)
    if latest is None:
        raise ValueError("No market analysis is available. Run Market analysis first.")

    enriched = enrich_market_analysis_result(shop, latest, persist_tags=True, db_path=db_path)
    products = [product for product in enriched.get("products", []) if isinstance(product, dict)]
    ledger = list_geo_events(shop, limit=500, db_path=db_path)
    tag_decisions = _update_tags_from_feedback(
        shop, products, ledger.get("events", []), db_path=db_path
    )

    refreshed = enrich_market_analysis_result(shop, latest, persist_tags=False, db_path=db_path)
    refreshed_products = [
        product for product in refreshed.get("products", []) if isinstance(product, dict)
    ]
    candidates = _candidate_actions(refreshed_products, max_actions=max_actions)
    niche_hypothesis = get_validated_niche_hypothesis(shop)
    proposals: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    applied = 0

    for product, element_key, content_type in candidates:
        tags = product.get("improvement_tags") or []
        try:
            request = _request_for_product(product, content_type, tags)
            result = run_content_action(
                request,
                shop,
                niche_hypothesis=niche_hypothesis,
                llm_router=llm_router,
                plan=plan,
                db_path=db_path,
            )
            proposal: dict[str, Any] = {
                "product_id": product.get("product_id"),
                "product_title": product.get("product_title"),
                "element": element_key,
                "content_type": content_type.value,
                "action_id": result.action_id,
                "quality_score": result.quality.score,
                "status": result.status.value,
                "auto_apply_attempted": False,
                "applied": False,
                "justification": (
                    f"Generated from continuous feedback and tags. Quality score {result.quality.score}/100."
                ),
            }
            score_before = int(product.get("opportunity_score") or 0)
            score_after = min(100, score_before + max(1, round(result.quality.score / 20)))
            event_id = create_geo_event(
                shop=shop,
                event_type="continuous_improvement_proposal",
                resource_type="product",
                resource_id=str(product.get("product_id") or ""),
                resource_title=str(product.get("product_title") or ""),
                action_type=content_type.value,
                status="planned",
                source="continuous_improvement_agent",
                hypothesis=proposal["justification"],
                score_before=score_before,
                score_after=score_after,
                before_snapshot={"tags": tags, "element": element_key},
                after_snapshot={
                    "action_id": result.action_id,
                    "quality_score": result.quality.score,
                },
                metrics_before={},
                estimated_impact={
                    "quality_score": result.quality.score,
                    "expected_score_delta": score_after - score_before,
                },
                notes=f"action_id={result.action_id}",
                db_path=db_path,
            )
            proposal["ledger_event_id"] = event_id

            if auto_apply:
                proposal["auto_apply_attempted"] = True
                if not access_token:
                    proposal["auto_apply_reason"] = "missing_access_token"
                elif plan not in {"pro", "agency"}:
                    proposal["auto_apply_reason"] = "plan_requires_pro_or_agency"
                elif result.status == ContentStatus.NEEDS_REVIEW:
                    proposal["auto_apply_reason"] = "needs_review"
                elif not is_live_supported(content_type):
                    proposal["auto_apply_reason"] = "content_type_not_live_supported"
                else:
                    _mark_action_approved(shop, result.action_id, db_path=db_path)
                    apply_result = _apply_safe_action(
                        shop=shop,
                        access_token=access_token,
                        action_id=result.action_id,
                        content_type=content_type,
                        resource_id=result.resource_id,
                        text=result.output.primary_text,
                        confirm_live_write=confirm_live_write,
                        db_path=db_path,
                    )
                    proposal.update(apply_result)
                    applied += 1 if apply_result.get("applied") else 0

            proposals.append(proposal)
        except Exception as exc:
            errors.append(
                {
                    "product_id": product.get("product_id"),
                    "product_title": product.get("product_title"),
                    "element": element_key,
                    "content_type": content_type.value,
                    "error": str(exc),
                }
            )

    summary = {
        "products_seen": len(products),
        "feedback_tag_decisions": len(tag_decisions),
        "candidate_actions": len(candidates),
        "proposals_created": len(proposals),
        "auto_apply": auto_apply,
        "applied": applied,
        "errors": len(errors),
    }
    run_id = _save_run(
        shop=shop,
        mode="auto_apply" if auto_apply else "proposal",
        status="completed" if not errors else "completed_with_errors",
        summary=summary,
        proposals=proposals,
        errors=errors,
        db_path=db_path,
    )
    return {
        "run_id": run_id,
        "summary": summary,
        "tag_decisions": tag_decisions,
        "proposals": proposals,
        "errors": errors,
    }
