"""Generate ICE-scored priority matrix from detected SEO issues and GSC data."""

import json
from pathlib import Path
from typing import Any

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from scripts._config import get_config
from scripts.audit.detect_issues import (
    detect_alt_text_issues,
    detect_meta_description_issues,
    detect_meta_title_issues,
)
from scripts.models import Issue

console = Console()

_CONFIDENCE: dict[str, int] = {
    "missing_meta_title": 9,
    "too_long_meta_title": 8,
    "missing_meta_description": 8,
    "too_short_meta_title": 7,
    "missing_alt_text": 7,
    "redirect_chain": 7,
    "page_404": 9,
    "duplicate_meta_title": 6,
    "too_short_meta_description": 6,
    "duplicate_meta_description": 6,
    "temporary_redirect_302": 6,
    "too_long_meta_description": 4,
    "too_long_alt_text": 4,
    "shopify_duplicate_url": 3,
}

_EFFORT: dict[str, int] = {
    "missing_alt_text": 1,
    "missing_meta_title": 2,
    "missing_meta_description": 2,
    "too_long_alt_text": 2,
    "temporary_redirect_302": 2,
    "too_long_meta_title": 3,
    "too_long_meta_description": 3,
    "redirect_chain": 3,
    "page_404": 3,
    "too_short_meta_title": 4,
    "too_short_meta_description": 4,
    "duplicate_meta_title": 5,
    "duplicate_meta_description": 5,
    "shopify_duplicate_url": 6,
}

_SEVERITY_BASE: dict[str, float] = {
    "critical": 10.0,
    "high": 8.0,
    "medium": 5.0,
    "low": 2.0,
    "info": 1.0,
}


def _build_url_map(
    products: list[dict[str, Any]], collections: list[dict[str, Any]], cfg=None
) -> dict[str, str]:
    """Map Shopify GID → canonical page URL."""
    _cfg = cfg or get_config()
    base = _cfg.base_url
    mapping: dict[str, str] = {}
    for p in products:
        if handle := p.get("handle"):
            mapping[p["id"]] = f"{base}/products/{handle}"
    for c in collections:
        if handle := c.get("handle"):
            mapping[c["id"]] = f"{base}/collections/{handle}"
    return mapping


def _gsc_factors(url: str | None, gsc: pd.DataFrame) -> tuple[float, int, float | None]:
    """Return (impact_multiplier, impressions, position) from GSC data for a URL."""
    if url is None or gsc.empty:
        return 1.0, 0, None

    row = gsc[gsc["url"] == url]
    if row.empty:
        return 1.0, 0, None

    impressions = int(row["impressions"].iloc[0])
    position = float(row["position"].iloc[0])

    if impressions >= 100:
        imp_mult = 2.0
    elif impressions >= 50:
        imp_mult = 1.5
    elif impressions >= 10:
        imp_mult = 1.2
    else:
        imp_mult = 1.0

    if 4 <= position <= 10:
        pos_mult = 1.5
    elif 11 <= position <= 20:
        pos_mult = 1.3
    else:
        pos_mult = 1.0

    return imp_mult * pos_mult, impressions, position


def score_issue(issue: Issue, url: str | None, gsc: pd.DataFrame) -> dict[str, Any]:
    """Compute ICE score for a single issue.

    Args:
        issue: Detected SEO issue.
        url: Canonical URL of the affected page (None if unknown).
        gsc: GSC performance DataFrame with columns url/impressions/position.

    Returns:
        Dict with ice_score, impact, confidence, effort, and issue metadata.
    """
    base = _SEVERITY_BASE.get(issue.severity.value, 1.0)
    gsc_mult, impressions, position = _gsc_factors(url, gsc)

    impact = round(base * gsc_mult, 1)
    confidence = _CONFIDENCE.get(issue.issue_type, 5)
    effort = _EFFORT.get(issue.issue_type, 5)
    ice = round((impact * confidence) / effort, 1)

    return {
        "ice_score": ice,
        "impact": impact,
        "confidence": confidence,
        "effort": effort,
        "resource_type": issue.resource_type,
        "resource_title": issue.resource_title,
        "issue_type": issue.issue_type,
        "severity": issue.severity.value,
        "impressions": impressions,
        "position": position,
        "url": url,
        "detail": issue.detail,
    }


def build_ice_matrix(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    gsc: pd.DataFrame,
    cfg=None,
) -> list[dict[str, Any]]:
    """Build the full ICE matrix from all detected issues, sorted by score desc.

    Args:
        products: Raw product list from Shopify snapshot.
        collections: Raw collection list from Shopify snapshot.
        gsc: GSC performance DataFrame.
        cfg: Optional TenantConfig (defaults to TENANT_ID env var).

    Returns:
        List of scored issue dicts, highest ICE first.
    """
    url_map = _build_url_map(products, collections, cfg)

    all_issues: list[Issue] = (
        detect_meta_title_issues(products, "product")
        + detect_meta_title_issues(collections, "collection")
        + detect_meta_description_issues(products, "product")
        + detect_meta_description_issues(collections, "collection")
        + detect_alt_text_issues(products)
    )

    rows = [score_issue(issue, url_map.get(issue.resource_id), gsc) for issue in all_issues]
    return sorted(rows, key=lambda r: r["ice_score"], reverse=True)


def _severity_color(severity: str) -> str:
    return {"critical": "red", "high": "yellow", "medium": "cyan", "low": "dim", "info": "dim"}.get(
        severity, "white"
    )


@click.command()
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--gsc", "gsc_path", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--output", default="data/raw/ice_matrix.json", show_default=True)
@click.option("--top", default=20, show_default=True, help="Number of issues to display")
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(snapshot: str, gsc_path: str, output: str, top: int, tenant: str | None) -> None:
    """Generate ICE priority matrix from Shopify issues and GSC data.

    ICE = (Impact × Confidence) / Effort
    Reads the Shopify snapshot and GSC CSV, writes ice_matrix.json.
    """
    cfg = get_config(tenant)
    console.print("[bold cyan]► Building ICE priority matrix[/bold cyan]")

    with open(snapshot, encoding="utf-8") as f:
        data = json.load(f)
    products: list[dict[str, Any]] = data.get("products", [])
    collections: list[dict[str, Any]] = data.get("collections", [])

    gsc_df = pd.read_csv(gsc_path) if Path(gsc_path).exists() else pd.DataFrame()
    if gsc_df.empty:
        console.print(
            "[yellow]  ⚠ No GSC data found — impact scores won't use impressions[/yellow]"
        )

    matrix = build_ice_matrix(products, collections, gsc_df, cfg)

    table = Table(title=f"ICE Priority Matrix — Top {top}", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("ICE", width=6, style="bold green")
    table.add_column("Ressource", style="cyan", max_width=28)
    table.add_column("Problème", max_width=28)
    table.add_column("Sév.", width=8)
    table.add_column("Imp.", width=6)
    table.add_column("GSC", width=16)

    for i, row in enumerate(matrix[:top], 1):
        sev_color = _severity_color(row["severity"])
        gsc_info = (
            f"{row['impressions']} imp. / #{row['position']:.0f}"
            if row["position"] is not None
            else f"{row['impressions']} imp."
        )
        table.add_row(
            str(i),
            str(row["ice_score"]),
            row["resource_title"][:28],
            row["issue_type"].replace("_", " "),
            f"[{sev_color}]{row['severity']}[/{sev_color}]",
            str(row["impact"]),
            gsc_info,
        )

    console.print(table)
    console.print(f"\n  Total issues détectées : [bold]{len(matrix)}[/bold]")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"  [green]✓[/green] ICE matrix → {output}")


if __name__ == "__main__":
    main()
