"""PageSpeed Insights import and summary helpers."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.api.snapshot_store import load_latest_snapshot_from_db
from app.paths import data_dir
from app.tenant_config import find_tenant_by_shop_domain
from scripts.audit.fetch_pagespeed import fetch_scores_for_urls

_DATA_DIR = data_dir()


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["url", "strategy", "performance_score", "lcp_ms", "cls", "tbt_ms", "fcp_ms"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _base_url_for_shop(shop: str, site_url: str | None = None) -> str:
    if site_url:
        return site_url.rstrip("/")
    tenant = find_tenant_by_shop_domain(shop)
    if tenant and tenant.base_url:
        return tenant.base_url.rstrip("/")
    return f"https://{shop}".rstrip("/")


def _resource_url(base_url: str, prefix: str, resource: dict[str, Any]) -> str | None:
    if url := resource.get("onlineStoreUrl"):
        return str(url)
    handle = str(resource.get("handle", "")).strip("/")
    if not handle:
        return None
    return f"{base_url}/{prefix}/{handle}"


def priority_urls_for_shop(shop: str, max_urls: int = 5, site_url: str | None = None) -> list[str]:
    """Return PageSpeed target URLs ordered by expected SEO impact."""
    tenant = find_tenant_by_shop_domain(shop)
    urls: list[str] = []
    if tenant and tenant.pagespeed_urls:
        urls.extend(tenant.pagespeed_urls)

    base_url = _base_url_for_shop(shop, site_url)
    urls.append(base_url)

    snapshot = load_latest_snapshot_from_db(shop)
    if snapshot:
        for collection in snapshot.get("collections", []):
            url = _resource_url(base_url, "collections", collection)
            if url:
                urls.append(url)
        for product in snapshot.get("products", []):
            url = _resource_url(base_url, "products", product)
            if url:
                urls.append(url)

    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        normalized = str(url).rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
        if len(unique) >= max_urls:
            break
    return unique


def _recommendations(row: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    score = _float(row.get("performance_score"))
    lcp = _float(row.get("lcp_ms"))
    cls = _float(row.get("cls"))
    tbt = _float(row.get("tbt_ms"))
    fcp = _float(row.get("fcp_ms"))

    if score is not None and score < 0.5:
        recommendations.append("Priorité haute: la page est lente pour les visiteurs.")
    elif score is not None and score < 0.75:
        recommendations.append("Priorité moyenne: la page peut être rendue plus confortable.")
    if lcp is not None and lcp > 2500:
        recommendations.append("Alléger l'élément principal visible au chargement.")
    if cls is not None and cls > 0.1:
        recommendations.append("Stabiliser la mise en page pour éviter les déplacements visuels.")
    if tbt is not None and tbt > 200:
        recommendations.append("Réduire les scripts bloquants et apps tierces trop lourdes.")
    if fcp is not None and fcp > 1800:
        recommendations.append("Accélérer le premier affichage visible de la page.")
    return recommendations


def _severity(row: dict[str, Any]) -> str:
    score = _float(row.get("performance_score"))
    lcp = _float(row.get("lcp_ms"))
    cls = _float(row.get("cls"))
    if score is not None and score < 0.5:
        return "critical"
    if lcp is not None and lcp > 4000:
        return "critical"
    if cls is not None and cls > 0.25:
        return "critical"
    if score is not None and score < 0.75:
        return "warning"
    if lcp is not None and lcp > 2500:
        return "warning"
    if cls is not None and cls > 0.1:
        return "warning"
    return "good"


def _row_to_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": row.get("url"),
        "strategy": row.get("strategy"),
        "performance_score": _float(row.get("performance_score")),
        "lcp_ms": _float(row.get("lcp_ms")),
        "cls": _float(row.get("cls")),
        "tbt_ms": _float(row.get("tbt_ms")),
        "fcp_ms": _float(row.get("fcp_ms")),
        "severity": _severity(row),
        "recommendations": _recommendations(row),
    }


def regression_alerts(current_rows: list[dict[str, Any]], previous_rows: list[dict[str, Any]]) -> list[dict]:
    """Return score-drop alerts between two PageSpeed imports."""
    previous_by_key = {
        (str(row.get("url")), str(row.get("strategy"))): _float(row.get("performance_score"))
        for row in previous_rows
    }
    alerts: list[dict] = []
    for row in current_rows:
        key = (str(row.get("url")), str(row.get("strategy")))
        previous = previous_by_key.get(key)
        current = _float(row.get("performance_score"))
        if previous is None or current is None:
            continue
        drop = previous - current
        if drop >= 0.1:
            alerts.append(
                {
                    "url": key[0],
                    "strategy": key[1],
                    "previous_score": previous,
                    "current_score": current,
                    "drop": round(drop, 3),
                    "severity": "critical" if drop >= 0.2 else "warning",
                }
            )
    return alerts


def latest_pagespeed_status(shop: str) -> dict[str, Any]:
    """Return latest PageSpeed import status and merchant-facing summary."""
    latest_path = _DATA_DIR / shop / "pagespeed.csv"
    rows = [_row_to_summary(row) for row in _read_csv(latest_path)]
    if not rows:
        return {
            "available": False,
            "row_count": 0,
            "url_count": 0,
            "imported_at": None,
            "mobile_average": None,
            "desktop_average": None,
            "alerts": [],
            "rows": [],
        }

    mobile = [
        row["performance_score"]
        for row in rows
        if row["strategy"] == "mobile" and row["performance_score"] is not None
    ]
    desktop = [
        row["performance_score"]
        for row in rows
        if row["strategy"] == "desktop" and row["performance_score"] is not None
    ]
    alerts = [row for row in rows if row["severity"] in {"warning", "critical"}]
    return {
        "available": True,
        "row_count": len(rows),
        "url_count": len({row["url"] for row in rows}),
        "imported_at": datetime.fromtimestamp(latest_path.stat().st_mtime, UTC).isoformat(),
        "mobile_average": round(sum(mobile) / len(mobile), 3) if mobile else None,
        "desktop_average": round(sum(desktop) / len(desktop), 3) if desktop else None,
        "alerts": alerts[:10],
        "rows": rows,
    }


def fetch_and_store_pagespeed(
    shop: str,
    *,
    urls: list[str] | None = None,
    max_urls: int = 5,
    site_url: str | None = None,
    delay: float = 1.5,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch PageSpeed scores and persist shop-scoped latest and timestamped CSVs."""
    targets = urls or priority_urls_for_shop(shop, max_urls=max_urls, site_url=site_url)
    previous_rows = _read_csv(_DATA_DIR / shop / "pagespeed.csv")
    rows = fetch_scores_for_urls(targets, delay=delay, api_key=api_key)

    shop_dir = _DATA_DIR / shop
    latest_path = shop_dir / "pagespeed.csv"
    timestamped_path = shop_dir / f"pagespeed_{_timestamp()}.csv"
    _write_csv(latest_path, rows)
    _write_csv(timestamped_path, rows)

    regressions = regression_alerts(rows, previous_rows)
    status = latest_pagespeed_status(shop)
    return {
        "shop": shop,
        "urls": len(targets),
        "rows": len(rows),
        "latest_path": str(latest_path),
        "timestamped_path": str(timestamped_path),
        "regression_alerts": regressions,
        "alerts": status["alerts"],
    }
