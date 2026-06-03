"""Optimization snapshots for GEO impact validation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.db_adapter import DB_PATH, get_conn
from app.geo.facts import analyze_product_facts
from app.geo.readiness import score_product_readiness


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _strip_html(value: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").strip()


def _description(resource: dict[str, Any]) -> str:
    return _strip_html(
        resource.get("descriptionHtml")
        or resource.get("body_html")
        or resource.get("description")
        or ""
    )


def _edge_nodes(container: Any) -> list[dict[str, Any]]:
    if isinstance(container, dict) and isinstance(container.get("edges"), list):
        return [edge.get("node", {}) for edge in container["edges"] if isinstance(edge, dict)]
    if isinstance(container, list):
        return [item for item in container if isinstance(item, dict)]
    return []


def _first_variant(product: dict[str, Any]) -> dict[str, Any]:
    nodes = _edge_nodes(product.get("variants"))
    return nodes[0] if nodes else {}


def _content_hash(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()
    return digest[:16]


def _path(value: str) -> str:
    parsed = urlparse(value)
    return (parsed.path if parsed.scheme else value).rstrip("/") or "/"


def _gsc_for_path(path: str, gsc_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target = _path(path)
    for url, row in gsc_rows.items():
        if _path(url) == target:
            return row
    return {}


def _seo_score(resource: dict[str, Any]) -> int:
    seo = resource.get("seo") or {}
    title = str(seo.get("title") or resource.get("title") or "").strip()
    description = str(seo.get("description") or _description(resource)).strip()
    checks = [
        30 <= len(title) <= 70,
        70 <= len(description) <= 160,
        bool(resource.get("handle")),
        len(_description(resource).split()) >= 20,
    ]
    return round(sum(1 for check in checks if check) / len(checks) * 100)


def _resource_path(resource_type: str, handle: str) -> str:
    if resource_type == "collection":
        return f"/collections/{handle}"
    return f"/products/{handle}"


def _find_resource(
    snapshot: dict[str, Any], resource_type: str, resource_id: str
) -> dict[str, Any] | None:
    key = "collections" if resource_type == "collection" else "products"
    for resource in snapshot.get(key, []):
        if str(resource.get("id")) == str(resource_id):
            return resource
    return None


def build_optimization_snapshot(
    *,
    shop: str,
    snapshot: dict[str, Any],
    resource_type: str,
    resource_id: str,
    action_type: str,
    gsc_rows: dict[str, dict[str, Any]] | None = None,
    source: str = "geo",
    hypothesis: str | None = None,
) -> dict[str, Any]:
    """Build a before-optimization snapshot for one product or collection."""
    resource = _find_resource(snapshot, resource_type, resource_id)
    if resource is None:
        raise ValueError(f"{resource_type} {resource_id} not found in snapshot")

    handle = str(resource.get("handle") or "")
    title = str(resource.get("title") or "")
    path = _resource_path(resource_type, handle)
    gsc = _gsc_for_path(path, gsc_rows or {})
    description = _description(resource)
    seo_score = _seo_score(resource)

    if resource_type == "product":
        readiness = score_product_readiness(resource)
        facts = analyze_product_facts(resource)
        variant = _first_variant(resource)
        commerce = {
            "price": variant.get("price"),
            "sku": variant.get("sku"),
            "inventory_quantity": variant.get(
                "inventoryQuantity", variant.get("inventory_quantity")
            ),
            "status": resource.get("status", ""),
        }
        readiness_score = int(readiness["readiness_score"])
        fact_payload: dict[str, Any] = {
            "confirmed_count": facts["confirmed_count"],
            "missing_count": facts["missing_count"],
            "missing_facts": facts["missing_facts"],
        }
    else:
        readiness = {"readiness_score": 0, "components": {}, "recommendations": []}
        commerce = {"status": resource.get("status", "")}
        readiness_score = 0
        fact_payload = {"confirmed_count": 0, "missing_count": 0, "missing_facts": []}

    snapshot_payload = {
        "shop": shop,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_title": title,
        "path": path,
        "action_type": action_type,
        "source": source,
        "hypothesis": hypothesis,
        "captured_at": datetime.now(UTC).isoformat(),
        "scores": {
            "readiness_score": readiness_score,
            "seo_score": seo_score,
            "readiness_components": readiness.get("components", {}),
        },
        "content": {
            "title": title,
            "handle": handle,
            "description": description[:1000],
            "description_word_count": len(description.split()),
            "seo": resource.get("seo") or {},
        },
        "facts": fact_payload,
        "commerce": commerce,
        "recommendations": readiness.get("recommendations", []),
    }
    metrics_payload = {
        "gsc": {
            "clicks": int(gsc.get("clicks", 0) or 0),
            "impressions": int(gsc.get("impressions", 0) or 0),
            "ctr": float(gsc.get("ctr", 0.0) or 0.0),
            "position": float(gsc.get("position", 0.0) or 0.0),
        },
        "measurement_note": "Baseline metrics captured before optimization; learning compares J+14/J+28 windows and keeps J+60 as long-term history.",
    }
    return {
        "shop": shop,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_title": title,
        "action_type": action_type,
        "source": source,
        "hypothesis": hypothesis,
        "snapshot": snapshot_payload,
        "metrics": metrics_payload,
        "readiness_score": readiness_score,
        "seo_score": seo_score,
        "content_hash": _content_hash(snapshot_payload),
    }


def create_optimization_snapshot(
    *,
    shop: str,
    snapshot_data: dict[str, Any],
    notes: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Persist a built optimization snapshot and return its ID."""
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO geo_optimization_snapshots (
                shop, created_at, resource_type, resource_id, resource_title,
                action_type, source, hypothesis, snapshot_json, metrics_json,
                readiness_score, seo_score, content_hash, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                now,
                snapshot_data["resource_type"],
                snapshot_data["resource_id"],
                snapshot_data["resource_title"],
                snapshot_data["action_type"],
                snapshot_data["source"],
                snapshot_data.get("hypothesis"),
                _json_dumps(snapshot_data["snapshot"]),
                _json_dumps(snapshot_data["metrics"]),
                snapshot_data["readiness_score"],
                snapshot_data["seo_score"],
                snapshot_data["content_hash"],
                notes,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM geo_optimization_snapshots
            WHERE shop = ? AND created_at = ? AND resource_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (shop, now, snapshot_data["resource_id"]),
        ).fetchone()
        return int((row or {}).get("id", 0))


def get_optimization_snapshot(
    *,
    shop: str,
    snapshot_id: int,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return one persisted optimization snapshot for a shop."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM geo_optimization_snapshots
            WHERE shop = ? AND id = ?
            """,
            (shop, snapshot_id),
        ).fetchone()

    if row is None:
        return None
    return {
        "id": row["id"],
        "shop": row["shop"],
        "created_at": row["created_at"],
        "resource_type": row["resource_type"],
        "resource_id": row["resource_id"],
        "resource_title": row["resource_title"],
        "action_type": row["action_type"],
        "source": row["source"],
        "hypothesis": row["hypothesis"],
        "snapshot": _json_loads(row["snapshot_json"]),
        "metrics": _json_loads(row["metrics_json"]),
        "readiness_score": row["readiness_score"],
        "seo_score": row["seo_score"],
        "content_hash": row["content_hash"],
        "notes": row["notes"],
    }


def list_optimization_snapshots(
    shop: str,
    *,
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """List persisted optimization snapshots for one shop."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) AS total FROM geo_optimization_snapshots WHERE shop = ?",
            (shop,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT *
            FROM geo_optimization_snapshots
            WHERE shop = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (shop, limit, offset),
        ).fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "shop": row["shop"],
                "created_at": row["created_at"],
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "resource_title": row["resource_title"],
                "action_type": row["action_type"],
                "source": row["source"],
                "hypothesis": row["hypothesis"],
                "snapshot": _json_loads(row["snapshot_json"]),
                "metrics": _json_loads(row["metrics_json"]),
                "readiness_score": row["readiness_score"],
                "seo_score": row["seo_score"],
                "content_hash": row["content_hash"],
                "notes": row["notes"],
            }
        )

    return {
        "total": int((total_row or {}).get("total", 0)),
        "limit": limit,
        "offset": offset,
        "snapshots": items,
    }
