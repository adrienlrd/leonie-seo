"""Generate a before/after SEO delta report from SQLite change history."""

import copy
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from scripts._paths import DB_PATH as _DB_PATH
from scripts.audit.detect_issues import (
    detect_alt_text_issues,
    detect_meta_description_issues,
    detect_meta_title_issues,
)
from scripts.models import Issue
from scripts.report.generate_report import calculate_score

console = Console()

_REPORTS_DIR = "reports"
_RULES_PATH = "config/seo_rules.yaml"


def load_changes(db_path: str) -> list[dict[str, Any]]:
    """Load all applied seo_changes from SQLite.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        List of change dicts (id, applied_at, resource_type, resource_id,
        field, old_value, new_value, status).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM seo_changes WHERE status = 'applied' ORDER BY applied_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reconstruct_before_snapshot(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    changes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild the pre-optimization snapshot by reverting seo_changes old_values.

    Args:
        products: Current Shopify products list.
        collections: Current Shopify collections list.
        changes: Applied seo_changes rows from SQLite.

    Returns:
        Tuple (products_before, collections_before) with old values restored.
    """
    products_before = copy.deepcopy(products)
    collections_before = copy.deepcopy(collections)

    # resource_id → {field: old_value}
    rollback: dict[str, dict[str, str | None]] = {}
    for c in changes:
        rid = c["resource_id"]
        rollback.setdefault(rid, {})[c["field"]] = c["old_value"]

    for p in products_before:
        fields = rollback.get(p["id"], {})
        if not fields:
            continue
        seo = p.setdefault("seo", {}) or {}
        if "seo.title" in fields:
            seo["title"] = fields["seo.title"]
        if "seo.description" in fields:
            seo["description"] = fields["seo.description"]
        p["seo"] = seo
        for field, old_val in fields.items():
            if field.startswith("image.altText:"):
                image_id = field.split(":", 1)[1]
                for edge in (p.get("images") or {}).get("edges", []):
                    if edge["node"].get("id") == image_id:
                        edge["node"]["altText"] = old_val

    for c in collections_before:
        fields = rollback.get(c["id"], {})
        if not fields:
            continue
        seo = c.setdefault("seo", {}) or {}
        if "seo.title" in fields:
            seo["title"] = fields["seo.title"]
        if "seo.description" in fields:
            seo["description"] = fields["seo.description"]
        c["seo"] = seo

    return products_before, collections_before


def reconstruct_after_snapshot(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    changes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild the post-optimization snapshot by applying seo_changes new_values.

    Useful when the local snapshot pre-dates the applied changes (i.e. was not
    re-crawled after the mutations ran).

    Args:
        products: Current Shopify products list (may be stale).
        collections: Current Shopify collections list.
        changes: Applied seo_changes rows from SQLite.

    Returns:
        Tuple (products_after, collections_after) with new values applied.
    """
    products_after = copy.deepcopy(products)
    collections_after = copy.deepcopy(collections)

    forward: dict[str, dict[str, str | None]] = {}
    for c in changes:
        rid = c["resource_id"]
        forward.setdefault(rid, {})[c["field"]] = c["new_value"]

    for p in products_after:
        fields = forward.get(p["id"], {})
        if not fields:
            continue
        seo = p.setdefault("seo", {}) or {}
        if "seo.title" in fields:
            seo["title"] = fields["seo.title"]
        if "seo.description" in fields:
            seo["description"] = fields["seo.description"]
        p["seo"] = seo
        for field, new_val in fields.items():
            if field.startswith("image.altText:"):
                image_id = field.split(":", 1)[1]
                for edge in (p.get("images") or {}).get("edges", []):
                    if edge["node"].get("id") == image_id:
                        edge["node"]["altText"] = new_val

    for c in collections_after:
        fields = forward.get(c["id"], {})
        if not fields:
            continue
        seo = c.setdefault("seo", {}) or {}
        if "seo.title" in fields:
            seo["title"] = fields["seo.title"]
        if "seo.description" in fields:
            seo["description"] = fields["seo.description"]
        c["seo"] = seo

    return products_after, collections_after


def compute_issues(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
) -> list[Issue]:
    """Run all meta + alt text detectors on a snapshot.

    Args:
        products: Shopify products list.
        collections: Shopify collections list.

    Returns:
        List of detected Issues.
    """
    issues: list[Issue] = []
    issues += detect_meta_title_issues(products, "product")
    issues += detect_meta_title_issues(collections, "collection")
    issues += detect_meta_description_issues(products, "product")
    issues += detect_meta_description_issues(collections, "collection")
    issues += detect_alt_text_issues(products)
    return issues


def changes_summary(changes: list[dict[str, Any]]) -> dict[str, int]:
    """Count applied changes by category.

    Args:
        changes: Applied seo_changes rows.

    Returns:
        Dict with keys: meta_title, meta_description, alt_text, other.
    """
    counts: dict[str, int] = {"meta_title": 0, "meta_description": 0, "alt_text": 0, "other": 0}
    for c in changes:
        field = c["field"]
        if field == "seo.title":
            counts["meta_title"] += 1
        elif field == "seo.description":
            counts["meta_description"] += 1
        elif field.startswith("image.altText"):
            counts["alt_text"] += 1
        else:
            counts["other"] += 1
    return counts


def _score_row(label: str, before: float, after: float) -> str:
    delta = after - before
    sign = "+" if delta >= 0 else ""
    arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
    return f"| {label} | {before:.1f} | {after:.1f} | {arrow} {sign}{delta:.1f} |"


def generate_delta_markdown(
    products_before: list[dict[str, Any]],
    collections_before: list[dict[str, Any]],
    products_after: list[dict[str, Any]],
    collections_after: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    report_date: str | None = None,
    rules_path: str = _RULES_PATH,
    site: str | None = None,
) -> str:
    """Generate the full before/after Markdown delta report.

    Args:
        products_before: Products in pre-optimization state.
        collections_before: Collections in pre-optimization state.
        products_after: Current products.
        collections_after: Current collections.
        changes: Applied seo_changes rows.
        opportunities: GSC opportunities list.
        gaps: Longtail keyword gaps list.
        report_date: ISO date string (defaults to today).
        rules_path: Path to seo_rules.yaml.
        site: Site domain to display in the report header. Falls back to active tenant.

    Returns:
        Full Markdown report as a string.
    """
    from scripts._config import get_config

    site_label = site or get_config().domain
    date = report_date or datetime.now(UTC).strftime("%Y-%m-%d")

    issues_before = compute_issues(products_before, collections_before)
    issues_after = compute_issues(products_after, collections_after)

    total_imgs_before = sum(len((p.get("images") or {}).get("edges", [])) for p in products_before)
    total_imgs_after = sum(len((p.get("images") or {}).get("edges", [])) for p in products_after)
    n_resources = len(products_after) + len(collections_after)

    score_before = calculate_score(
        issues_before,
        len(products_before) + len(collections_before),
        total_imgs_before,
        rules_path=rules_path,
    )
    score_after = calculate_score(
        issues_after,
        n_resources,
        total_imgs_after,
        rules_path=rules_path,
    )

    summary = changes_summary(changes)
    counts_before = Counter(i.issue_type for i in issues_before)
    counts_after = Counter(i.issue_type for i in issues_after)

    lines: list[str] = [
        f"# Rapport SEO Avant/Après — {site_label}",
        f"**Date :** {date}  ",
        f"**Produits :** {len(products_after)}  |  **Collections :** {len(collections_after)}  ",
        "",
        "---",
        "",
        "## 1. Optimisations appliquées",
        "",
        "| Type | Nombre |",
        "|---|---|",
        f"| Méta titles corrigés | {summary['meta_title']} |",
        f"| Méta descriptions corrigées | {summary['meta_description']} |",
        f"| Alt texts d'images ajoutés | {summary['alt_text']} |",
        f"| **Total changements** | **{len(changes)}** |",
        "",
        "---",
        "",
        "## 2. Score SEO global",
        "",
        "| Composant | Avant | Après | Évolution |",
        "|---|---|---|---|",
        _score_row("**Score global**", score_before.total, score_after.total),
    ]

    component_labels = {
        "meta_title": "Méta titles",
        "meta_description": "Méta descriptions",
        "alt_text": "Alt texts",
        "core_web_vitals": "Core Web Vitals",
        "redirections": "Redirections",
        "duplicates": "Doublons",
    }
    for key, label in component_labels.items():
        b = score_before.components.get(key, 0.0)
        a = score_after.components.get(key, 0.0)
        lines.append(_score_row(label, b, a))

    lines += [
        "",
        "---",
        "",
        "## 3. Issues résolues vs restantes",
        "",
        "| Type d'issue | Avant | Après | Résolues |",
        "|---|---|---|---|",
    ]

    issue_types = sorted(
        set(counts_before.keys()) | set(counts_after.keys()),
        key=lambda t: -counts_before.get(t, 0),
    )
    for itype in issue_types:
        b = counts_before.get(itype, 0)
        a = counts_after.get(itype, 0)
        resolved = b - a
        sign = f"+{resolved}" if resolved > 0 else str(resolved)
        lines.append(f"| `{itype}` | {b} | {a} | {sign} |")

    lines += [
        f"| **Total** | **{len(issues_before)}** | **{len(issues_after)}** | **+{len(issues_before) - len(issues_after)}** |",
        "",
        "---",
        "",
        "## 4. Top 10 changements méta",
        "",
        "| Ressource | Champ | Avant (chars) | Après (chars) |",
        "|---|---|---|---|",
    ]

    meta_changes = [c for c in changes if c["field"] in ("seo.title", "seo.description")]
    for c in meta_changes[:10]:
        rid_short = c["resource_id"].split("/")[-1]
        old_len = len(c["old_value"]) if c["old_value"] else 0
        new_len = len(c["new_value"]) if c["new_value"] else 0
        old_label = f"{'«' + c['old_value'][:30] + '…»' if c['old_value'] else '—'} ({old_len})"
        new_label = f"«{(c['new_value'] or '')[:30]}…» ({new_len})"
        field_short = "title" if c["field"] == "seo.title" else "desc"
        rtype = c["resource_type"]
        lines.append(f"| {rtype}/{rid_short} | {field_short} | {old_label} | {new_label} |")

    lines += [
        "",
        "---",
        "",
        "## 5. Top 5 opportunités GSC restantes",
        "",
        "| URL | Zone | Pos. | Impr. | +Clics estimés | Action |",
        "|---|---|---|---|---|---|",
    ]

    zone_labels = {"quick_win": "Quick win", "low_ctr": "CTR faible", "long_term": "Long terme"}
    for opp in opportunities[:5]:
        path = opp["url"].split(site_label)[-1] or "/"
        zone = zone_labels.get(opp["zone"], opp["zone"])
        lines.append(
            f"| {path} | {zone} | {opp['position']} | {opp['impressions']} "
            f"| +{opp['estimated_gain_clicks']} | {opp['action']} |"
        )

    gap_count = sum(1 for g in gaps if g["status"] == "gap")
    on_site_count = sum(1 for g in gaps if g["status"] == "on_site")
    ranking_count = sum(1 for g in gaps if g["status"] == "ranking")

    lines += [
        "",
        "---",
        "",
        "## 6. Couverture mots-clés longue traîne",
        "",
        "| Statut | Nombre |",
        "|---|---|",
        f"| ✅ Ranking (trafic GSC) | {ranking_count} |",
        f"| ⚠ Sur site, sans trafic | {on_site_count} |",
        f"| ❌ Gap (contenu manquant) | {gap_count} |",
        "",
        "**Gaps prioritaires :**",
    ]

    for g in gaps:
        if g["status"] == "gap":
            lines.append(f"- `{g['keyword']}` [{g['category']}] — {g['recommendation']}")

    lines += [
        "",
        "---",
        "",
        f"*Généré le {date} par leonie-seo*",
    ]

    return "\n".join(lines)


@click.command()
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--db-path", default=_DB_PATH, show_default=True)
@click.option(
    "--opportunities",
    default="data/raw/gsc_opportunities.json",
    show_default=True,
)
@click.option("--gaps", default="data/raw/longtail_gaps.json", show_default=True)
@click.option("--output-dir", default=_REPORTS_DIR, show_default=True)
def main(
    snapshot: str,
    db_path: str,
    opportunities: str,
    gaps: str,
    output_dir: str,
) -> None:
    """Generate a before/after SEO delta report from SQLite change history.

    Reconstructs the pre-optimization state using old_values stored in
    seo_changes, runs issue detection on both states, and produces a
    Markdown report with score delta and top remaining opportunities.
    """
    console.print("[bold cyan]► Generating SEO delta report[/bold cyan]")

    with open(snapshot, encoding="utf-8") as f:
        data = json.load(f)
    products: list[dict[str, Any]] = data.get("products", [])
    collections: list[dict[str, Any]] = data.get("collections", [])

    changes = load_changes(db_path)
    console.print(f"  {len(changes)} changes loaded from history")

    products_before, collections_before = reconstruct_before_snapshot(
        products, collections, changes
    )
    # Always reconstruct "after" from new_values: the local snapshot may pre-date
    # the Shopify mutations and not yet reflect the applied changes.
    products_after, collections_after = reconstruct_after_snapshot(products, collections, changes)

    opps: list[dict[str, Any]] = []
    if Path(opportunities).exists():
        with open(opportunities, encoding="utf-8") as f:
            opps = json.load(f)

    gap_report: list[dict[str, Any]] = []
    if Path(gaps).exists():
        with open(gaps, encoding="utf-8") as f:
            gap_report = json.load(f)

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    report_md = generate_delta_markdown(
        products_before,
        collections_before,
        products_after,
        collections_after,
        changes,
        opps,
        gap_report,
        date,
    )

    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "delta_report.md"
    report_path.write_text(report_md, encoding="utf-8")

    # Quick score preview
    issues_before = compute_issues(products_before, collections_before)
    issues_after = compute_issues(products_after, collections_after)
    n = len(products_after) + len(collections_after)
    imgs = sum(len((p.get("images") or {}).get("edges", [])) for p in products_after)
    score_b = calculate_score(issues_before, n, imgs).total
    score_a = calculate_score(issues_after, n, imgs).total
    delta = score_a - score_b

    console.print(
        f"  Score : [dim]{score_b:.1f}[/dim] → [bold green]{score_a:.1f}[/bold green] "
        f"([green]+{delta:.1f}[/green])"
    )
    console.print(
        f"  Issues : [dim]{len(issues_before)}[/dim] → [bold]{len(issues_after)}[/bold] "
        f"([green]-{len(issues_before) - len(issues_after)} résolues[/green])"
    )
    console.print(f"  [green]✓[/green] Report → {report_path}")


if __name__ == "__main__":
    main()
