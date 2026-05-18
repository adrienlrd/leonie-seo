"""Control group builder for GEO impact validation."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.geo.readiness import score_product_readiness

MEASURABLE_STATUSES = {"applied", "measured", "rolled_back"}


def _edge_nodes(container: Any) -> list[dict[str, Any]]:
    if isinstance(container, dict) and isinstance(container.get("edges"), list):
        return [edge.get("node", {}) for edge in container["edges"] if isinstance(edge, dict)]
    if isinstance(container, list):
        return [item for item in container if isinstance(item, dict)]
    return []


def _first_variant(resource: dict[str, Any]) -> dict[str, Any]:
    nodes = _edge_nodes(resource.get("variants"))
    return nodes[0] if nodes else {}


def _path(value: str) -> str:
    parsed = urlparse(value)
    return (parsed.path if parsed.scheme else value).rstrip("/") or "/"


def _resource_path(resource_type: str, handle: str) -> str:
    if resource_type == "collection":
        return f"/collections/{handle}"
    return f"/products/{handle}"


def _gsc_for_path(path: str, gsc_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target = _path(path)
    for url, row in gsc_rows.items():
        if _path(url) == target:
            return row
    return {}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _price(resource: dict[str, Any]) -> float | None:
    variant = _first_variant(resource)
    price = _float(variant.get("price"), -1.0)
    return price if price >= 0 else None


def _inventory(resource: dict[str, Any]) -> int | None:
    variant = _first_variant(resource)
    value = variant.get("inventoryQuantity", variant.get("inventory_quantity"))
    if value is None:
        return None
    return _int(value)


def _category(resource: dict[str, Any]) -> str:
    return str(
        resource.get("productType")
        or resource.get("product_type")
        or resource.get("category")
        or resource.get("type")
        or ""
    ).strip().lower()


def _tags(resource: dict[str, Any]) -> set[str]:
    raw = resource.get("tags") or []
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def _readiness(resource_type: str, resource: dict[str, Any]) -> int:
    if resource_type != "product":
        return 0
    return int(score_product_readiness(resource)["readiness_score"])


def _resource_features(
    *,
    resource_type: str,
    resource: dict[str, Any],
    gsc_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    handle = str(resource.get("handle") or "")
    path = _resource_path(resource_type, handle)
    gsc = _gsc_for_path(path, gsc_rows)
    return {
        "resource_type": resource_type,
        "resource_id": str(resource.get("id") or ""),
        "resource_title": str(resource.get("title") or ""),
        "handle": handle,
        "path": path,
        "category": _category(resource),
        "tags": sorted(_tags(resource)),
        "price": _price(resource),
        "inventory_quantity": _inventory(resource),
        "status": str(resource.get("status") or ""),
        "readiness_score": _readiness(resource_type, resource),
        "gsc": {
            "clicks": _int(gsc.get("clicks")),
            "impressions": _int(gsc.get("impressions")),
            "ctr": _float(gsc.get("ctr")),
            "position": _float(gsc.get("position")),
        },
    }


def _target_features(event: dict[str, Any]) -> dict[str, Any]:
    before = event.get("before_snapshot") or {}
    metrics = event.get("metrics_before") or {}
    content = before.get("content") or {}
    scores = before.get("scores") or {}
    commerce = before.get("commerce") or {}
    gsc = metrics.get("gsc") or {}
    price = _float(commerce.get("price"), -1.0) if commerce.get("price") is not None else -1.0
    return {
        "resource_type": event["resource_type"],
        "resource_id": event["resource_id"],
        "resource_title": event["resource_title"],
        "handle": content.get("handle", ""),
        "path": before.get("path", ""),
        "category": "",
        "tags": [],
        "price": price if price >= 0 else None,
        "inventory_quantity": commerce.get("inventory_quantity"),
        "status": commerce.get("status", ""),
        "readiness_score": int(event.get("score_before") or scores.get("readiness_score") or 0),
        "gsc": {
            "clicks": _int(gsc.get("clicks")),
            "impressions": _int(gsc.get("impressions")),
            "ctr": _float(gsc.get("ctr")),
            "position": _float(gsc.get("position")),
        },
    }


def _closeness(target: float, candidate: float, scale: float) -> int:
    if target <= 0 and candidate <= 0:
        return 100
    delta = abs(target - candidate)
    return max(0, round(100 - min(100, (delta / scale) * 100)))


def _price_closeness(target: float | None, candidate: float | None) -> int:
    if target is None or candidate is None:
        return 50
    scale = max(target, candidate, 1.0)
    return _closeness(target, candidate, scale)


def _similarity(target: dict[str, Any], candidate: dict[str, Any]) -> tuple[int, list[str]]:
    target_gsc = target["gsc"]
    candidate_gsc = candidate["gsc"]
    category_match = bool(target["category"]) and target["category"] == candidate["category"]
    tag_overlap = len(set(target["tags"]) & set(candidate["tags"]))
    impressions = _closeness(target_gsc["impressions"], candidate_gsc["impressions"], 1000)
    position = _closeness(target_gsc["position"], candidate_gsc["position"], 20)
    price = _price_closeness(target["price"], candidate["price"])
    readiness = _closeness(target["readiness_score"], candidate["readiness_score"], 100)
    score = round(
        (25 if category_match else 0)
        + min(15, tag_overlap * 5)
        + impressions * 0.2
        + position * 0.15
        + price * 0.15
        + readiness * 0.25
    )
    reasons = []
    if category_match:
        reasons.append("same_category")
    if tag_overlap:
        reasons.append("shared_tags")
    if impressions >= 70:
        reasons.append("similar_impressions")
    if position >= 70:
        reasons.append("similar_position")
    if price >= 70:
        reasons.append("similar_price")
    if readiness >= 70:
        reasons.append("similar_readiness")
    return min(100, score), reasons


def _quality(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "usable"
    return "weak"


def _resource_pool(snapshot: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    key = "collections" if resource_type == "collection" else "products"
    return [item for item in snapshot.get(key, []) if isinstance(item, dict)]


def _find_resource(snapshot: dict[str, Any], resource_type: str, resource_id: str) -> dict[str, Any] | None:
    for resource in _resource_pool(snapshot, resource_type):
        if str(resource.get("id")) == str(resource_id):
            return resource
    return None


def _optimized_ids(events: list[dict[str, Any]]) -> set[str]:
    return {
        str(event.get("resource_id"))
        for event in events
        if str(event.get("status")) in MEASURABLE_STATUSES and event.get("resource_id")
    }


def build_control_groups(
    *,
    snapshot: dict[str, Any],
    events: list[dict[str, Any]],
    gsc_rows: dict[str, dict[str, Any]] | None = None,
    event_id: int | None = None,
    top_events: int = 10,
    controls_per_event: int = 3,
) -> dict[str, Any]:
    """Build comparable control pages for traceable optimization events."""
    gsc = gsc_rows or {}
    optimized_ids = _optimized_ids(events)
    eligible_events = [
        event
        for event in events
        if event.get("status") in MEASURABLE_STATUSES and (event_id is None or int(event.get("id", 0)) == event_id)
    ][:top_events]

    groups = []
    for event in eligible_events:
        target = _target_features(event)
        target_resource = _find_resource(snapshot, event["resource_type"], event["resource_id"])
        if target_resource is not None:
            target_from_catalog = _resource_features(
                resource_type=event["resource_type"],
                resource=target_resource,
                gsc_rows=gsc,
            )
            target["category"] = target_from_catalog["category"]
            target["tags"] = target_from_catalog["tags"]
            if target["price"] is None:
                target["price"] = target_from_catalog["price"]
            if target["inventory_quantity"] is None:
                target["inventory_quantity"] = target_from_catalog["inventory_quantity"]
        candidates = []
        for resource in _resource_pool(snapshot, event["resource_type"]):
            resource_id = str(resource.get("id") or "")
            if not resource_id or resource_id == event["resource_id"] or resource_id in optimized_ids:
                continue
            features = _resource_features(resource_type=event["resource_type"], resource=resource, gsc_rows=gsc)
            score, reasons = _similarity(target, features)
            candidates.append(
                {
                    "resource_type": features["resource_type"],
                    "resource_id": features["resource_id"],
                    "resource_title": features["resource_title"],
                    "path": features["path"],
                    "similarity_score": score,
                    "quality": _quality(score),
                    "match_reasons": reasons,
                    "baseline": {
                        "readiness_score": features["readiness_score"],
                        "impressions": features["gsc"]["impressions"],
                        "position": features["gsc"]["position"],
                        "price": features["price"],
                        "inventory_quantity": features["inventory_quantity"],
                    },
                }
            )
        candidates.sort(key=lambda item: item["similarity_score"], reverse=True)
        controls = candidates[:controls_per_event]
        groups.append(
            {
                "event_id": event["id"],
                "snapshot_id": event.get("snapshot_id"),
                "action_type": event["action_type"],
                "status": event["status"],
                "target": {
                    "resource_type": target["resource_type"],
                    "resource_id": target["resource_id"],
                    "resource_title": target["resource_title"],
                    "path": target["path"],
                    "baseline": {
                        "readiness_score": target["readiness_score"],
                        "impressions": target["gsc"]["impressions"],
                        "position": target["gsc"]["position"],
                        "price": target["price"],
                        "inventory_quantity": target["inventory_quantity"],
                    },
                },
                "controls": controls,
                "quality": _quality(controls[0]["similarity_score"]) if controls else "missing",
                "warnings": []
                if controls and controls[0]["similarity_score"] >= 55
                else ["No sufficiently similar unmodified control page found."],
            }
        )

    return {
        "summary": {
            "events_considered": len(eligible_events),
            "groups_built": len(groups),
            "groups_with_controls": sum(1 for group in groups if group["controls"]),
            "causality_note": "Control groups are comparison aids, not causal proof. Treat weak matches as directional only.",
        },
        "groups": groups,
    }
