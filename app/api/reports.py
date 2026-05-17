"""Exportable SEO reports — audit Markdown, delta before/after, available report list."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.db_adapter import DB_PATH, get_conn

router = APIRouter(prefix="/api", tags=["reports"])

_SEVERITY_LABEL = {"critical": "🔴 Critique", "high": "🟠 Haute", "medium": "🟡 Moyenne", "low": "🔵 Basse"}


# ---------------------------------------------------------------------------
# Helpers — issue detection (snapshot-native, no Screaming Frog dependency)
# ---------------------------------------------------------------------------


def _strip_html(html: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _audit_products(products: list[dict[str, Any]]) -> list[dict]:
    issues = []
    seen_titles: dict[str, str] = {}

    for p in products:
        pid = p.get("id", "")
        title = p.get("title", pid)
        seo = p.get("seo") or {}
        meta_title = (seo.get("title") or "").strip()
        meta_desc = (seo.get("description") or "").strip()
        images = (p.get("images") or {}).get("edges", [])

        # Meta title
        if not meta_title:
            issues.append({"type": "missing_meta_title", "severity": "critical", "resource": title, "id": pid})
        elif len(meta_title) < 30:
            issues.append({"type": "short_meta_title", "severity": "high", "resource": title, "id": pid,
                           "detail": f"{len(meta_title)} chars"})
        elif len(meta_title) > 70:
            issues.append({"type": "long_meta_title", "severity": "medium", "resource": title, "id": pid,
                           "detail": f"{len(meta_title)} chars"})
        else:
            norm = meta_title.lower()
            if norm in seen_titles:
                issues.append({"type": "duplicate_meta_title", "severity": "high", "resource": title, "id": pid,
                               "detail": f"Même titre que « {seen_titles[norm]} »"})
            seen_titles[norm] = title

        # Meta description
        if not meta_desc:
            issues.append({"type": "missing_meta_description", "severity": "high", "resource": title, "id": pid})
        elif len(meta_desc) < 70:
            issues.append({"type": "short_meta_description", "severity": "medium", "resource": title, "id": pid,
                           "detail": f"{len(meta_desc)} chars"})
        elif len(meta_desc) > 160:
            issues.append({"type": "long_meta_description", "severity": "low", "resource": title, "id": pid,
                           "detail": f"{len(meta_desc)} chars"})

        # Alt text
        for edge in images:
            node = edge.get("node", {})
            if not node.get("altText"):
                issues.append({"type": "missing_alt_text", "severity": "medium", "resource": title, "id": pid,
                               "detail": node.get("url", "")})

    return issues


def _audit_collections(collections: list[dict[str, Any]]) -> list[dict]:
    issues = []
    for c in collections:
        cid = c.get("id", "")
        title = c.get("title", cid)
        seo = c.get("seo") or {}
        meta_title = (seo.get("title") or "").strip()
        meta_desc = (seo.get("description") or "").strip()

        if not meta_title:
            issues.append({"type": "missing_meta_title", "severity": "critical", "resource": f"[Collection] {title}",
                           "id": cid})
        if not meta_desc:
            issues.append({"type": "missing_meta_description", "severity": "high",
                           "resource": f"[Collection] {title}", "id": cid})
    return issues


def _build_audit_markdown(shop: str, snapshot: dict) -> str:
    products = snapshot.get("products", [])
    collections = snapshot.get("collections", [])
    issues = _audit_products(products) + _audit_collections(collections)

    by_severity = {"critical": [], "high": [], "medium": [], "low": []}
    for iss in issues:
        by_severity.setdefault(iss["severity"], []).append(iss)

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Rapport d'audit SEO — {shop}",
        f"*Généré le {now}*",
        "",
        "## Résumé",
        "",
        f"- **Produits analysés :** {len(products)}",
        f"- **Collections analysées :** {len(collections)}",
        f"- **Problèmes détectés :** {len(issues)}",
        f"  - 🔴 Critiques : {len(by_severity['critical'])}",
        f"  - 🟠 Hautes : {len(by_severity['high'])}",
        f"  - 🟡 Moyennes : {len(by_severity['medium'])}",
        f"  - 🔵 Basses : {len(by_severity['low'])}",
        "",
    ]

    for sev, label in _SEVERITY_LABEL.items():
        group = by_severity.get(sev, [])
        if not group:
            continue
        lines.append(f"## {label} ({len(group)})")
        lines.append("")
        lines.append("| Ressource | Problème | Détail |")
        lines.append("|---|---|---|")
        for iss in group:
            detail = iss.get("detail", "")
            issue_label = iss["type"].replace("_", " ").title()
            lines.append(f"| {iss['resource']} | {issue_label} | {detail} |")
        lines.append("")

    if not issues:
        lines.append("✅ Aucun problème détecté sur les ressources analysées.")
        lines.append("")

    return "\n".join(lines)


def _build_delta_markdown(shop: str, changes: list[dict]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Rapport de modifications SEO — {shop}",
        f"*Généré le {now}*",
        "",
        f"## {len(changes)} modification(s) enregistrée(s)",
        "",
    ]

    if not changes:
        lines.append("Aucune modification enregistrée dans la base.")
        return "\n".join(lines)

    lines.append("| Date | Type | Ressource | Champ | Avant | Après | Statut |")
    lines.append("|---|---|---|---|---|---|---|")

    for ch in changes:
        date = ch.get("applied_at", "")[:10]
        rtype = ch.get("resource_type", "")
        rid = str(ch.get("resource_id", "")).split("/")[-1]
        field = ch.get("field", "")
        old_v = (ch.get("old_value") or "—")[:60]
        new_v = (ch.get("new_value") or "—")[:60]
        status = ch.get("status", "")
        lines.append(f"| {date} | {rtype} | {rid} | {field} | {old_v} | {new_v} | {status} |")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/reports/list")
async def list_reports(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return available report types and their status (data available or not)."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)

    with get_conn(DB_PATH) as conn:
        change_count = (
            conn.execute(
                "SELECT COUNT(*) FROM seo_changes WHERE shop = ?",
                (ctx.shop,),
            ).fetchone()
            or {}
        ).get("COUNT(*)", 0)

    return {
        "shop": ctx.shop,
        "reports": [
            {
                "type": "audit",
                "label": "Audit SEO complet",
                "description": "Méta titles, méta descriptions, alt text — toutes les ressources du snapshot.",
                "format": "markdown",
                "available": snapshot is not None,
            },
            {
                "type": "delta",
                "label": "Rapport de modifications",
                "description": f"Historique avant/après des {change_count} modification(s) enregistrée(s).",
                "format": "markdown",
                "available": change_count > 0,
            },
        ],
    }


@router.get("/shops/{shop}/reports/audit", response_class=PlainTextResponse)
async def get_audit_report(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> str:
    """Generate and return a Markdown audit report from the current snapshot.

    Returns raw Markdown text suitable for download.
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )
    return _build_audit_markdown(ctx.shop, snapshot)


@router.get("/shops/{shop}/reports/delta", response_class=PlainTextResponse)
async def get_delta_report(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: int = 90,
) -> str:
    """Generate and return a Markdown delta report from seo_changes.

    Args:
        days: Lookback window in days (default 90).
    Returns raw Markdown text suitable for download.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            """SELECT applied_at, resource_type, resource_id, field,
                      old_value, new_value, status
               FROM seo_changes
               WHERE shop = ? AND applied_at >= ?
               ORDER BY applied_at DESC""",
            (ctx.shop, cutoff),
        ).fetchall()

    changes = [dict(r) for r in rows]
    return _build_delta_markdown(ctx.shop, changes)
