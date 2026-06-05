"""Synthetic control group selection for learning observations."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn
from app.learning.features import keyword_source_from_product, product_category
from app.learning.outcomes import event_applied_at

_MIN_CONTROL_SIZE = 3
_MAX_CONTROL_SIZE = 10
_POLLUTION_LOOKBACK_DAYS = 7


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _metric(metrics: dict[str, Any], key: str) -> float:
    if key in metrics:
        return _num(metrics.get(key))
    gsc = metrics.get("gsc") if isinstance(metrics.get("gsc"), dict) else {}
    ga4 = metrics.get("ga4") if isinstance(metrics.get("ga4"), dict) else {}
    if key in gsc:
        return _num(gsc.get(key))
    if key in ga4:
        return _num(ga4.get(key))
    return 0.0


def _product_id(product: dict[str, Any]) -> str:
    return str(product.get("product_id") or product.get("id") or "")


def _is_active_product(product: dict[str, Any]) -> bool:
    status = str(product.get("status") or product.get("product_status") or "").strip().lower()
    if status and status not in {"active", "published"}:
        return False
    published = product.get("published")
    if published is False:
        return False
    return True


def _collections(product: dict[str, Any]) -> set[str]:
    raw = product.get("collections") or product.get("collection_titles") or []
    if isinstance(raw, str):
        return {item.strip().lower() for item in raw.split(",") if item.strip()}
    if not isinstance(raw, list):
        return set()
    values: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            text = str(item.get("title") or item.get("handle") or item.get("id") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            values.add(text.lower())
    return values


def _primary_keyword(product: dict[str, Any]) -> dict[str, Any]:
    keywords = [item for item in product.get("seo_keywords") or [] if isinstance(item, dict)]
    if not keywords:
        return {}
    for keyword in keywords:
        if str(keyword.get("target_role") or "").lower() == "primary":
            return keyword
    return keywords[0]


def _keyword_metrics(product: dict[str, Any]) -> dict[str, Any]:
    keyword = _primary_keyword(product)
    impressions = keyword.get("gsc_impressions")
    clicks = keyword.get("gsc_clicks")
    position = keyword.get("gsc_position")
    if impressions is None and clicks is None and position is None:
        return {}
    impressions_value = int(impressions or 0)
    clicks_value = int(clicks or 0)
    ctr = round(clicks_value / impressions_value, 4) if impressions_value else 0.0
    return {
        "gsc": {
            "impressions": impressions_value,
            "clicks": clicks_value,
            "ctr": ctr,
            "position": float(position or 0.0),
        }
    }


def _impression_bucket(product: dict[str, Any]) -> int:
    impressions = _metric(_keyword_metrics(product), "impressions")
    if impressions <= 0:
        return 0
    return int(math.log10(max(impressions, 1)))


def _position(product: dict[str, Any]) -> float:
    return _metric(_keyword_metrics(product), "position")


def _similarity_score(target: dict[str, Any], candidate: dict[str, Any]) -> float:
    score = 0.0
    if product_category(target) == product_category(candidate):
        score += 30.0

    target_collections = _collections(target)
    candidate_collections = _collections(candidate)
    if target_collections and candidate_collections:
        overlap = len(target_collections & candidate_collections)
        score += min(20.0, overlap * 10.0)

    if _impression_bucket(target) == _impression_bucket(candidate):
        score += 15.0

    target_position = _position(target)
    candidate_position = _position(candidate)
    if target_position and candidate_position:
        score += max(0.0, 15.0 - abs(target_position - candidate_position) * 1.5)

    if keyword_source_from_product(target) == keyword_source_from_product(candidate):
        score += 10.0

    target_score = float(target.get("opportunity_score") or 0)
    candidate_score = float(candidate.get("opportunity_score") or 0)
    if target_score or candidate_score:
        score += max(0.0, 10.0 - abs(target_score - candidate_score) / 10.0)
    return round(score, 2)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_event_in_window(
    event: dict[str, Any],
    *,
    resource_id: str,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    if str(event.get("resource_id") or "") != resource_id:
        return False
    if str(event.get("status") or "") not in {"applied", "measured", "rolled_back"}:
        return False
    applied_at = event_applied_at(event)
    return applied_at is not None and window_start <= applied_at <= window_end


def _has_seo_change(
    shop: str,
    *,
    resource_id: str,
    window_start: datetime,
    window_end: datetime,
    db_path: Path | None,
) -> bool:
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT applied_at FROM seo_changes
            WHERE shop = ? AND resource_type = 'product' AND resource_id = ?
            """,
            (shop, resource_id),
        ).fetchall()
    for row in rows:
        applied_at = _parse_dt(str(row.get("applied_at") or ""))
        if applied_at and window_start <= applied_at <= window_end:
            return True
    return False


def _window_payload(product: dict[str, Any], window_label: str) -> dict[str, Any]:
    for key in ("learning_metrics", "control_metrics"):
        container = product.get(key)
        if not isinstance(container, dict):
            continue
        payload = container.get(window_label) or container.get(window_label.lower())
        if isinstance(payload, dict):
            return payload
    return {}


def _product_window_metrics(
    product: dict[str, Any],
    *,
    window_days: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    window_label = f"J+{window_days}"
    payload = _window_payload(product, window_label) or _window_payload(product, str(window_days))
    before = payload.get("before") if isinstance(payload.get("before"), dict) else None
    after = payload.get("after") if isinstance(payload.get("after"), dict) else None
    if before and after:
        return before, after
    before = (
        product.get("metrics_before") if isinstance(product.get("metrics_before"), dict) else None
    )
    after = product.get("metrics_after") if isinstance(product.get("metrics_after"), dict) else None
    if before and after:
        return before, after
    return None


def _snapshot_metrics(
    shop: str,
    *,
    resource_id: str,
    applied_at: datetime,
    window_days: int,
    db_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    path = db_path if db_path is not None else DB_PATH
    window_end = applied_at + timedelta(days=window_days)
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT created_at, metrics_json
            FROM geo_optimization_snapshots
            WHERE shop = ? AND resource_type = 'product' AND resource_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (shop, resource_id),
        ).fetchall()
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    for row in rows:
        created_at = _parse_dt(str(row.get("created_at") or ""))
        if created_at is None:
            continue
        try:
            metrics = json.loads(row.get("metrics_json") or "{}")
        except json.JSONDecodeError:
            metrics = {}
        if not isinstance(metrics, dict):
            continue
        if created_at <= applied_at:
            before = metrics
        if created_at >= window_end and after is None:
            after = metrics
            break
    if before and after:
        return before, after
    return None


def _candidate_metrics(
    shop: str,
    product: dict[str, Any],
    *,
    applied_at: datetime,
    window_days: int,
    db_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    direct = _product_window_metrics(product, window_days=window_days)
    if direct:
        return direct
    return _snapshot_metrics(
        shop,
        resource_id=_product_id(product),
        applied_at=applied_at,
        window_days=window_days,
        db_path=db_path,
    )


def _weighted_average(rows: list[tuple[float, dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    total_weight = sum(weight for weight, _before, _after in rows)
    if total_weight <= 0:
        return {}

    def avg(key: str, side: str) -> float:
        total = 0.0
        for weight, before, after in rows:
            metrics = before if side == "before" else after
            total += weight * _metric(metrics, key)
        return total / total_weight

    impressions_before = avg("impressions", "before")
    impressions_after = avg("impressions", "after")
    clicks_before = avg("clicks", "before")
    clicks_after = avg("clicks", "after")
    return {
        "impressions_before": round(impressions_before),
        "impressions_after": round(impressions_after),
        "clicks_before": round(clicks_before),
        "clicks_after": round(clicks_after),
        "ctr_before": round(clicks_before / impressions_before, 4) if impressions_before else 0.0,
        "ctr_after": round(clicks_after / impressions_after, 4) if impressions_after else 0.0,
        "position_before": round(avg("position", "before"), 2),
        "position_after": round(avg("position", "after"), 2),
        "conversions_before": round(avg("conversions", "before"), 2),
        "conversions_after": round(avg("conversions", "after"), 2),
        "revenue_before": round(avg("revenue", "before"), 2),
        "revenue_after": round(avg("revenue", "after"), 2),
    }


def build_control_metrics_for_event(
    *,
    shop: str,
    event: dict[str, Any],
    products: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    window_days: int,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return weighted metrics for similar unmodified products when available."""
    applied_at = event_applied_at(event)
    target_id = str(event.get("resource_id") or "")
    target = products.get(target_id)
    if applied_at is None or target is None:
        return {}

    window_start = applied_at - timedelta(days=_POLLUTION_LOOKBACK_DAYS)
    window_end = applied_at + timedelta(days=window_days)
    scored: list[tuple[float, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    excluded_modified = 0
    missing_metrics = 0
    for product_id, product in products.items():
        if product_id == target_id or not _is_active_product(product):
            continue
        if any(
            _is_event_in_window(
                other,
                resource_id=product_id,
                window_start=window_start,
                window_end=window_end,
            )
            for other in events
        ) or _has_seo_change(
            shop,
            resource_id=product_id,
            window_start=window_start,
            window_end=window_end,
            db_path=db_path,
        ):
            excluded_modified += 1
            continue
        similarity = _similarity_score(target, product)
        if similarity <= 0:
            continue
        metrics = _candidate_metrics(
            shop,
            product,
            applied_at=applied_at,
            window_days=window_days,
            db_path=db_path,
        )
        if metrics is None:
            missing_metrics += 1
            continue
        before, after = metrics
        scored.append((similarity, product, before, after))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = scored[:_MAX_CONTROL_SIZE]
    if len(selected) < _MIN_CONTROL_SIZE:
        return {}

    rows: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    selected_ids: list[str] = []
    for similarity, product, before, after in selected:
        rows.append((similarity, before, after))
        selected_ids.append(_product_id(product))

    if len(rows) < _MIN_CONTROL_SIZE:
        return {}
    aggregated = _weighted_average(rows)
    quality = "strong" if len(rows) >= 5 else "fair"
    return {
        **aggregated,
        "control_size": len(rows),
        "control_quality": quality,
        "control_product_ids": selected_ids,
        "selection_method": "similar_unmodified_products_v1",
        "candidates_seen": max(0, len(products) - 1),
        "candidates_missing_metrics": missing_metrics,
        "candidates_excluded_modified": excluded_modified,
    }
