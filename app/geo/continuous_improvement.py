"""Continuous improvement tags and GEO agent change summaries."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn
from app.product_optimization.context import build_product_optimization_context

_TAG_TYPES = frozenset({"keyword", "analysis_axis", "content_axis", "risk", "merchant"})
_TAG_STATUSES = frozenset({"positive", "neutral", "negative", "forced"})
_ELEMENT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("meta_title", "Meta title", "proposed_meta_title"),
    ("meta_description", "Meta description", "proposed_meta_description"),
    ("product_description", "Description produit", "proposed_product_description"),
    ("faq", "FAQ", "proposed_faq"),
    ("geo_answer_block", "Bloc court GEO", "proposed_geo_answer_block"),
    ("blog", "Blog", "proposed_blog_title"),
    ("image_alts", "Alt images", "proposed_image_alts"),
    ("jsonld", "JSON-LD", "schema_jsonld"),
    ("internal_links", "Maillage interne", "recommended_internal_links"),
)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _coerce_status(status: str) -> str:
    return status if status in _TAG_STATUSES else "neutral"


def _coerce_type(tag_type: str) -> str:
    return tag_type if tag_type in _TAG_TYPES else "content_axis"


def _stable_tag_id(product_id: str, tag_type: str, label: str) -> str:
    safe = "|".join((product_id, tag_type, label)).lower()
    return hashlib.sha256(safe.encode("utf-8")).hexdigest()[:16]


def _element_value(product: dict[str, Any], pack: dict[str, Any], key: str) -> Any:
    if key == "schema_jsonld":
        return product.get("schema_jsonld") or pack.get("proposed_schema_jsonld")
    if key == "recommended_internal_links":
        return product.get("recommended_internal_links") or pack.get("recommended_internal_links")
    return pack.get(key)


def _has_improvement(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return bool(value)


def build_improvement_elements(product: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact per-product element status for the market-analysis UI."""
    pack = (
        product.get("content_test_pack")
        if isinstance(product.get("content_test_pack"), dict)
        else {}
    )
    elements: list[dict[str, Any]] = []
    for key, label, source_key in _ELEMENT_FIELDS:
        value = _element_value(product, pack, source_key)
        improved = _has_improvement(value)
        elements.append(
            {
                "key": key,
                "label": label,
                "improved": improved,
                "status": "improved" if improved else "not_improved",
            }
        )
    return elements


def _keyword_tags(product: dict[str, Any]) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = []
    for kw in (product.get("seo_keywords") or [])[:5]:
        if not isinstance(kw, dict):
            continue
        query = str(kw.get("query") or "").strip()
        if not query:
            continue
        fit = int(kw.get("product_fit_score") or 0)
        status = "positive" if fit >= 70 else "negative" if fit < 35 else "neutral"
        tags.append(
            {
                "tag_id": _stable_tag_id(str(product.get("product_id", "")), "keyword", query),
                "label": query,
                "tag_type": "keyword",
                "status": status,
                "score": fit,
                "source": str(kw.get("data_source") or "market_analysis"),
                "locked_by_merchant": False,
                "reason": str(kw.get("reason") or ""),
            }
        )
    return tags


# Intent-type labels the LLM sometimes returns verbatim in buying_intents.
# They describe how someone searches, not what they want — never show them.
_INTENT_TYPE_LABELS = frozenset({"transactional", "commercial", "informational", "navigational"})

# facts_missing mixes known fact keys with free-form LLM diagnostics ("pas de
# PAA pour ce mot-clé"). Only known keys become merchant-facing tags, with a
# label that says what to do; diagnostics stay in the analysis payload.
_MISSING_FACT_LABELS_FR = {
    "materials": "Matière à confirmer",
    "origins": "Origine de fabrication à confirmer",
    "origin": "Origine de fabrication à confirmer",
    "certifications": "Certifications à confirmer",
    "warranty": "Garantie à confirmer",
    "care": "Conseils d'entretien à confirmer",
    "care_instructions": "Conseils d'entretien à confirmer",
    "dimensions": "Dimensions à confirmer",
    "capacity": "Capacité à confirmer",
    "compatibility": "Compatibilité à confirmer",
    "size_recommendation": "Guide des tailles à confirmer",
    "delivery": "Informations de livraison à confirmer",
    "returns": "Politique de retour à confirmer",
    "battery_autonomy": "Autonomie à confirmer",
}


def _truncate_label(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return f"{cut}…"


def _missing_fact_label(fact: str) -> str | None:
    key = fact.split(":", 1)[0].strip().lower().replace(" ", "_")
    return _MISSING_FACT_LABELS_FR.get(key)


def _axis_tags(product: dict[str, Any]) -> list[dict[str, Any]]:
    labels: list[tuple[str, str, int]] = []
    if product.get("target_customer"):
        labels.append(("analysis_axis", str(product["target_customer"]), 60))
    for intent in (product.get("buying_intents") or [])[:3]:
        if not intent:
            continue
        words = {w for w in str(intent).lower().split() if w}
        if words and words <= _INTENT_TYPE_LABELS:
            continue
        labels.append(("content_axis", str(intent), 65))
    pack = (
        product.get("content_test_pack")
        if isinstance(product.get("content_test_pack"), dict)
        else {}
    )
    seen_risks: set[str] = set()
    for fact in pack.get("facts_missing") or []:
        label = _missing_fact_label(str(fact)) if fact else None
        if label and label not in seen_risks:
            seen_risks.add(label)
            labels.append(("risk", label, 30))
        if len(seen_risks) >= 3:
            break

    tags = []
    product_id = str(product.get("product_id", ""))
    for tag_type, label, score in labels:
        clean = label.strip()
        if not clean:
            continue
        tags.append(
            {
                "tag_id": _stable_tag_id(product_id, tag_type, clean),
                "label": _truncate_label(clean),
                "tag_type": tag_type,
                "status": "negative" if tag_type == "risk" else "neutral",
                "score": score,
                "source": "market_analysis",
                "locked_by_merchant": False,
                "reason": "Derived from the latest market analysis.",
            }
        )
    return tags


def _load_persisted_tags(
    shop: str, product_id: str, db_path: Path | None = None
) -> list[dict[str, Any]]:
    path = db_path if db_path is not None else DB_PATH
    try:
        with get_conn(path) as conn:
            rows = conn.execute(
                """
                SELECT tag_id, label, tag_type, status, score, source, locked_by_merchant,
                       reason, last_seen_at, updated_at
                FROM product_improvement_tags
                WHERE shop = ? AND product_id = ?
                ORDER BY locked_by_merchant DESC, status, label
                """,
                (shop, product_id),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    return [
        {
            "tag_id": row["tag_id"],
            "label": row["label"],
            "tag_type": row["tag_type"],
            "status": row["status"],
            "score": row["score"],
            "source": row["source"],
            "locked_by_merchant": bool(row["locked_by_merchant"]),
            "reason": row["reason"] or "",
            "last_seen_at": row["last_seen_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def merge_product_tags(
    shop: str,
    product: dict[str, Any],
    *,
    persist: bool = False,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Merge derived tags with merchant-managed persisted tags."""
    product_id = str(product.get("product_id") or product.get("id") or "")
    derived = _keyword_tags(product) + _axis_tags(product)
    persisted = _load_persisted_tags(shop, product_id, db_path=db_path)

    # Key by label only — one entry per label. Locked merchant tags always win over
    # derived tags with the same label so that retire/add actions survive re-analysis.
    by_label: dict[str, dict[str, Any]] = {}
    for tag in derived:
        by_label[str(tag["label"]).lower()] = tag
    for tag in persisted:
        label_key = str(tag["label"]).lower()
        existing = by_label.get(label_key)
        if existing is None:
            by_label[label_key] = tag
        elif tag.get("locked_by_merchant"):
            # Locked tag wins: preserve its status but merge in derived metadata
            by_label[label_key] = {**existing, **tag}
        else:
            by_label[label_key] = {
                **existing,
                **{k: v for k, v in tag.items() if k in ("tag_id", "locked_by_merchant")},
            }

    merged = _dedupe_axis_variants(list(by_label.values()))
    if persist and product_id:
        upsert_product_tags(shop, product_id, merged, db_path=db_path)
    return sorted(
        merged, key=lambda item: (item["status"] == "negative", item["tag_type"], item["label"])
    )


def _dedupe_axis_variants(tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse near-identical persona labels accumulated across re-analyses.

    Successive analyses rephrase the same target_customer ("Propriétaires
    d'animaux soucieux de la qualité et de l'élégance / et du style / …");
    keyed-by-label merging keeps every variant. Group analysis_axis tags by
    their first words and keep one — locked first, then the most complete.
    """
    kept: list[dict[str, Any]] = []
    best_by_prefix: dict[str, dict[str, Any]] = {}
    for tag in tags:
        if tag.get("tag_type") != "analysis_axis":
            kept.append(tag)
            continue
        prefix = " ".join(str(tag.get("label") or "").casefold().split()[:5])
        current = best_by_prefix.get(prefix)
        if current is None:
            best_by_prefix[prefix] = tag
            continue
        challenger_wins = bool(tag.get("locked_by_merchant")) and not current.get(
            "locked_by_merchant"
        )
        same_lock = bool(tag.get("locked_by_merchant")) == bool(current.get("locked_by_merchant"))
        if challenger_wins or (same_lock and len(str(tag["label"])) > len(str(current["label"]))):
            best_by_prefix[prefix] = tag
    return kept + list(best_by_prefix.values())


def upsert_product_tags(
    shop: str,
    product_id: str,
    tags: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> None:
    """Persist tags without deleting user-managed tags absent from the latest analysis."""
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    try:
        with get_conn(path) as conn:
            for tag in tags:
                label = str(tag.get("label") or "").strip()[:120]
                if not label:
                    continue
                tag_type = _coerce_type(str(tag.get("tag_type") or "content_axis"))
                tag_id = str(tag.get("tag_id") or _stable_tag_id(product_id, tag_type, label))
                conn.execute(
                    """
                    INSERT INTO product_improvement_tags (
                        shop, product_id, tag_id, label, tag_type, status, score, source,
                        locked_by_merchant, reason, first_seen_at, last_seen_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(shop, product_id, tag_id) DO UPDATE SET
                        label = excluded.label,
                        tag_type = excluded.tag_type,
                        status = CASE
                            WHEN product_improvement_tags.locked_by_merchant = 1 THEN product_improvement_tags.status
                            ELSE excluded.status
                        END,
                        score = excluded.score,
                        source = excluded.source,
                        reason = excluded.reason,
                        last_seen_at = excluded.last_seen_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        shop,
                        product_id,
                        tag_id,
                        label,
                        tag_type,
                        _coerce_status(str(tag.get("status") or "neutral")),
                        int(tag.get("score") or 0),
                        str(tag.get("source") or "market_analysis"),
                        1 if tag.get("locked_by_merchant") else 0,
                        str(tag.get("reason") or ""),
                        now,
                        now,
                        now,
                    ),
                )
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return
        raise


def set_product_tag(
    shop: str,
    product_id: str,
    *,
    label: str,
    tag_type: str = "merchant",
    status: str = "forced",
    locked_by_merchant: bool = True,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Create or update one merchant-controlled product tag."""
    clean_label = label.strip()[:120]
    if not clean_label:
        raise ValueError("Tag label is required")
    clean_type = _coerce_type(tag_type)
    tag = {
        "tag_id": _stable_tag_id(product_id, clean_type, clean_label),
        "label": clean_label,
        "tag_type": clean_type,
        "status": _coerce_status(status),
        "score": 100 if status in ("positive", "forced") else 0,
        "source": "merchant",
        "locked_by_merchant": locked_by_merchant,
        "reason": "Merchant-managed tag.",
    }
    upsert_product_tags(shop, product_id, [tag], db_path=db_path)
    return tag


def get_product_locked_tags(
    shop: str, product_id: str, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Return all merchant-locked tags for one product (any status)."""
    return _load_persisted_tags(shop, product_id, db_path=db_path)


def get_shop_retired_tags(shop: str, db_path: Path | None = None) -> list[str]:
    """Return labels of all merchant-retired tags for a shop (status=negative + locked)."""
    path = db_path if db_path is not None else DB_PATH
    try:
        with get_conn(path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT label
                FROM product_improvement_tags
                WHERE shop = ? AND status = 'negative' AND locked_by_merchant = 1
                """,
                (shop,),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    return [row["label"] for row in rows]


def reset_all_shop_tags(shop: str, db_path: Path | None = None) -> int:
    """Delete all improvement tags for a shop. Returns the number of deleted rows."""
    path = db_path if db_path is not None else DB_PATH
    try:
        with get_conn(path) as conn:
            cur = conn.execute(
                "DELETE FROM product_improvement_tags WHERE shop = ?",
                (shop,),
            )
            return cur.rowcount
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return 0
        raise


def _published_linked_handles(shop: str) -> set[str]:
    """Return product handles linked from any published blog article."""
    try:
        from app.blog.store import list_drafts  # noqa: PLC0415

        linked: set[str] = set()
        for draft in list_drafts(shop):
            if draft.get("status") != "published_to_shopify":
                continue
            for link in draft.get("internal_links") or []:
                url = str(link.get("target_url") or "").strip().rstrip("/")
                parts = url.split("/")
                if "products" in parts:
                    idx = parts.index("products") + 1
                    if idx < len(parts) and parts[idx]:
                        linked.add(parts[idx])
        return linked
    except Exception:
        return set()


def enrich_market_analysis_result(
    shop: str,
    result: dict[str, Any],
    *,
    persist_tags: bool = False,
    business_profile: dict[str, Any] | None = None,
    niche_hypothesis: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Attach tags and per-element improvement statuses to a market analysis result."""
    enriched = dict(result)
    linked_handles = _published_linked_handles(shop)
    products = []
    for product in result.get("products", []) if isinstance(result.get("products"), list) else []:
        if not isinstance(product, dict):
            continue
        product_copy = dict(product)
        product_copy["improvement_tags"] = merge_product_tags(
            shop,
            product_copy,
            persist=persist_tags,
            db_path=db_path,
        )
        product_copy["improvement_elements"] = build_improvement_elements(product_copy)
        # Override maillage element immediately when a published blog links to this product
        handle = str(product_copy.get("product_handle") or "").strip()
        if handle and handle in linked_handles:
            for el in product_copy["improvement_elements"]:
                if el.get("key") == "internal_links":
                    el["improved"] = True
                    el["status"] = "improved"
        product_copy["optimization_context"] = build_product_optimization_context(
            shop,
            product_copy,
            business_profile=business_profile,
            niche_hypothesis=niche_hypothesis,
        )
        products.append(product_copy)
    enriched["products"] = products
    return enriched


def list_continuous_improvement(
    shop: str,
    *,
    limit: int = 100,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return agent changes, tags and compact metrics for the continuous page."""
    from app.geo.ledger import list_geo_events, summarize_geo_events  # noqa: PLC0415
    from app.market_analysis.jobs import load_latest_result  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    latest = load_latest_result(shop) or {}
    enriched = (
        enrich_market_analysis_result(shop, latest, db_path=path) if latest else {"products": []}
    )
    products = enriched.get("products", [])
    all_tags = [tag for product in products for tag in product.get("improvement_tags", [])]
    elements = [
        element for product in products for element in product.get("improvement_elements", [])
    ]
    improved_count = sum(1 for element in elements if element.get("improved"))
    negative_tags = [tag for tag in all_tags if tag.get("status") == "negative"]
    positive_tags = [tag for tag in all_tags if tag.get("status") == "positive"]
    ledger = list_geo_events(shop, limit=limit, db_path=path)
    summary = summarize_geo_events(shop, db_path=path)

    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT tag_type, status, COUNT(*) AS count
            FROM product_improvement_tags
            WHERE shop = ?
            GROUP BY tag_type, status
            ORDER BY tag_type, status
            """,
            (shop,),
        ).fetchall()
        run_rows = conn.execute(
            """
            SELECT id, created_at, mode, status, summary_json, proposals_json, errors_json
            FROM continuous_improvement_agent_runs
            WHERE shop = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 20
            """,
            (shop,),
        ).fetchall()
        tag_history_rows = conn.execute(
            """
            SELECT product_id, tag_id, label, status_before, status_after,
                   measurement_window, metrics_json, reason, decided_at
            FROM tag_performance_history
            WHERE shop = ?
            ORDER BY decided_at DESC, id DESC
            LIMIT 100
            """,
            (shop,),
        ).fetchall()

    return {
        "summary": {
            **summary,
            "products_tracked": len(products),
            "tags_total": len(all_tags),
            "positive_tags": len(positive_tags),
            "negative_tags": len(negative_tags),
            "improved_elements": improved_count,
            "total_elements": len(elements),
        },
        "tag_breakdown": [dict(row) for row in rows],
        "products": [
            {
                "product_id": product.get("product_id"),
                "product_title": product.get("product_title"),
                "product_handle": product.get("product_handle"),
                "opportunity_score": product.get("opportunity_score"),
                "tags": product.get("improvement_tags", []),
                "elements": product.get("improvement_elements", []),
            }
            for product in products
        ],
        "events": ledger.get("events", []),
        "agent_runs": [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "mode": row["mode"],
                "status": row["status"],
                "summary": _json_loads(row["summary_json"], {}),
                "proposals": _json_loads(row["proposals_json"], []),
                "errors": _json_loads(row["errors_json"], []),
            }
            for row in run_rows
        ],
        "tag_history": [
            {
                "product_id": row["product_id"],
                "tag_id": row["tag_id"],
                "label": row["label"],
                "status_before": row["status_before"],
                "status_after": row["status_after"],
                "window": row["measurement_window"],
                "metrics": _json_loads(row["metrics_json"], {}),
                "reason": row["reason"],
                "decided_at": row["decided_at"],
            }
            for row in tag_history_rows
        ],
    }


def record_agent_change_from_product(
    shop: str,
    product: dict[str, Any],
    *,
    action_type: str,
    notes: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Record a planned GEO agent change in the existing impact ledger."""
    from app.geo.ledger import create_geo_event  # noqa: PLC0415

    score = int(product.get("opportunity_score") or 0)
    tags = product.get("improvement_tags") or []
    return create_geo_event(
        shop=shop,
        event_type="continuous_improvement",
        resource_type="product",
        resource_id=str(product.get("product_id") or ""),
        resource_title=str(product.get("product_title") or ""),
        action_type=action_type,
        status="planned",
        source="geo_correction_agent",
        hypothesis="Correction generated from market analysis tags and product opportunities.",
        score_before=score,
        before_snapshot={
            "opportunity_score": score,
            "tags": tags,
            "elements": product.get("improvement_elements") or [],
        },
        metrics_before={},
        estimated_impact={
            "tag_count": len(tags),
            "negative_tags": sum(1 for t in tags if t.get("status") == "negative"),
        },
        notes=notes,
        db_path=db_path,
    )
