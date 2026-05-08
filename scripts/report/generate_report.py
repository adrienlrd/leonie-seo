"""Generate a Markdown SEO report with a weighted score 0-100."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console

from scripts.audit.detect_issues import (
    detect_404_issues,
    detect_alt_text_issues,
    detect_duplicate_content,
    detect_meta_description_issues,
    detect_meta_title_issues,
    detect_redirect_issues,
)
from scripts.audit.parse_screaming_frog import parse_overview, parse_redirects
from scripts.license import LicenseError, require_valid_license
from scripts.models import Issue, SEOScore, Severity

console = Console()

_RULES_PATH = "config/seo_rules.yaml"
_REPORTS_DIR = "reports"

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


def calculate_score(
    issues: list[Issue],
    total_resources: int,
    total_images: int,
    pagespeed_data: list[dict[str, Any]] | None = None,
    rules_path: str = _RULES_PATH,
) -> SEOScore:
    """Calculate a weighted SEO score from 0 to 100.

    Args:
        issues: All detected issues.
        total_resources: Total number of products + collections.
        total_images: Total number of product images.
        pagespeed_data: Optional list of fetch_score() results.
        rules_path: Path to seo_rules.yaml.

    Returns:
        SEOScore with total (0-100) and per-component breakdown.
    """
    with open(rules_path, encoding="utf-8") as f:
        rules = yaml.safe_load(f)

    counts = Counter(i.issue_type for i in issues)
    n = max(total_resources, 1)
    n_img = max(total_images, 1)

    # Meta titles: penalize missing + too-short (high severity)
    title_bad = counts.get("missing_meta_title", 0) + counts.get("too_short_meta_title", 0)
    meta_title_score = max(0.0, 1.0 - title_bad / n)

    # Meta descriptions: penalize missing + duplicates
    desc_bad = counts.get("missing_meta_description", 0) + counts.get(
        "duplicate_meta_description", 0
    )
    meta_desc_score = max(0.0, 1.0 - desc_bad / n)

    # Alt texts
    alt_bad = counts.get("missing_alt_text", 0)
    alt_score = max(0.0, 1.0 - alt_bad / n_img)

    # Core Web Vitals — use PageSpeed data if available, else neutral 0.5
    if pagespeed_data:
        mobile = [r["performance_score"] for r in pagespeed_data if r.get("strategy") == "mobile"]
        cwv_score = sum(mobile) / len(mobile) if mobile else 0.5
    else:
        cwv_score = 0.5

    # Redirections + 404
    redirect_bad = (
        counts.get("redirect_chain", 0)
        + counts.get("page_404", 0)
        + counts.get("temporary_redirect_302", 0)
    )
    redirect_score = max(0.0, 1.0 - redirect_bad / 10.0)

    # Duplicates: only penalize actual duplicate titles/descriptions (not Shopify structural URLs)
    dup_bad = counts.get("duplicate_meta_title", 0) + counts.get("duplicate_meta_description", 0)
    dup_score = max(0.0, 1.0 - dup_bad / n)

    weights = rules
    components = {
        "meta_title": meta_title_score * weights["meta_title"]["weight"],
        "meta_description": meta_desc_score * weights["meta_description"]["weight"],
        "alt_text": alt_score * weights["alt_text"]["weight"],
        "core_web_vitals": cwv_score * weights["core_web_vitals"]["weight"],
        "redirections": redirect_score * weights["redirections"]["weight"],
        "duplicates": dup_score * weights["duplicates"]["weight"],
    }

    return SEOScore(
        total=round(sum(components.values()) * 100, 1),
        components={k: round(v * 100, 1) for k, v in components.items()},
        issue_count=dict(counts),
    )


def generate_markdown_report(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    issues: list[Issue],
    score: SEOScore,
    report_date: str | None = None,
) -> str:
    """Render the full SEO audit report as a Markdown string."""
    date = report_date or datetime.utcnow().strftime("%Y-%m-%d")
    total_images = sum(len((p.get("images") or {}).get("edges", [])) for p in products)

    lines: list[str] = [
        f"# SEO Audit Report — {date}",
        "",
        "**Site :** leoniedelacroix.com  ",
        f"**Products :** {len(products)}  ",
        f"**Collections :** {len(collections)}  ",
        f"**Images :** {total_images}  ",
        "",
        "---",
        "",
        "## Score global",
        "",
        f"### {score.total:.1f} / 100",
        "",
        "| Composant | Score /100 |",
        "|---|---|",
    ]
    for component, val in score.components.items():
        lines.append(f"| {component.replace('_', ' ').title()} | {val:.1f} |")

    lines += [
        "",
        "---",
        "",
        "## Problèmes détectés",
        "",
        f"**Total :** {len(issues)} issues",
        "",
    ]

    for severity in (
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
        Severity.INFO,
    ):
        group = [i for i in issues if i.severity == severity]
        if not group:
            continue
        emoji = _SEVERITY_EMOJI[severity]
        lines += [
            f"### {emoji} {severity.value.upper()} ({len(group)})",
            "",
            "| Ressource | Type | Valeur actuelle | Détail |",
            "|---|---|---|---|",
        ]
        for issue in group:
            current = (issue.current_value or "—").replace("|", "\\|")
            detail = issue.detail.replace("|", "\\|")
            lines.append(
                f"| {issue.resource_title} | `{issue.issue_type}` | {current} | {detail} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        f"*Généré le {date} par leonie-seo*",
    ]

    return "\n".join(lines)


@click.command()
@click.option("--data", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--pagespeed", default=None, help="pagespeed.csv from fetch_pagespeed")
@click.option("--sf-overview", default=None, help="Screaming Frog overview CSV")
@click.option("--sf-redirects", default=None, help="Screaming Frog response codes CSV")
@click.option("--output-dir", default=_REPORTS_DIR, show_default=True)
def main(
    data: str,
    pagespeed: str | None,
    sf_overview: str | None,
    sf_redirects: str | None,
    output_dir: str,
) -> None:
    """Generate a Markdown SEO report from audit data."""
    try:
        require_valid_license()
    except LicenseError as e:
        console.print(f"  [red]✗[/red] Licence invalide : {e}")
        raise SystemExit(1)
    import pandas as pd

    console.print("[bold cyan]► Generating SEO report[/bold cyan]")

    with open(data, encoding="utf-8") as f:
        snapshot = json.load(f)

    products: list[dict[str, Any]] = snapshot.get("products", [])
    collections: list[dict[str, Any]] = snapshot.get("collections", [])

    issues: list[Issue] = []
    issues += detect_meta_title_issues(products, "product")
    issues += detect_meta_title_issues(collections, "collection")
    issues += detect_meta_description_issues(products, "product")
    issues += detect_meta_description_issues(collections, "collection")
    issues += detect_alt_text_issues(products)
    issues += detect_duplicate_content(products)
    issues += detect_redirect_issues(parse_redirects(sf_redirects) if sf_redirects else None)
    issues += detect_404_issues(parse_overview(sf_overview) if sf_overview else None)

    pagespeed_data: list[dict[str, Any]] | None = None
    if pagespeed and Path(pagespeed).exists():
        pagespeed_data = pd.read_csv(pagespeed).to_dict("records")
    elif pagespeed:
        console.print(f"  [yellow]⚠[/yellow] {pagespeed} not found — skipping CWV scores")

    total_images = sum(len((p.get("images") or {}).get("edges", [])) for p in products)
    score = calculate_score(issues, len(products) + len(collections), total_images, pagespeed_data)

    console.print(f"  [green]✓[/green] {len(issues)} issues — score {score.total}/100")

    date = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "audit_report.md"
    report_path.write_text(
        generate_markdown_report(products, collections, issues, score, date),
        encoding="utf-8",
    )
    console.print(f"  [green]✓[/green] Report → {report_path}")


if __name__ == "__main__":
    main()
