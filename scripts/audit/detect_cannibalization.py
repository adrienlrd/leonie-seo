"""Detect keyword cannibalization: multiple pages competing for the same query."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from scripts._config import get_config

console = Console()

_MIN_IMPRESSIONS = 10  # default; overridden by tenant config


def _page_type(url: str) -> str:
    if "/products/" in url:
        return "product"
    if "/collections/" in url:
        return "collection"
    if "/blogs/" in url:
        return "blog"
    if "/pages/" in url:
        return "page"
    return "other"


def load_gsc_query_page(path: str) -> pd.DataFrame:
    """Load query×page GSC data. Returns empty DataFrame if file missing.

    Args:
        path: Path to gsc_query_page.csv.

    Returns:
        DataFrame with columns: query, url, clicks, impressions, ctr, position.
    """
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["query", "url", "clicks", "impressions", "ctr", "position"])
    return pd.read_csv(p)


def detect_cannibal_pairs(
    df: pd.DataFrame,
    min_impressions: int = _MIN_IMPRESSIONS,
) -> list[dict[str, Any]]:
    """Find queries where 2+ pages compete, ranked by severity.

    For each cannibalised query, returns one record with:
    - primary: best-ranked page (lowest position value)
    - cannibal: worst-ranked page (highest position value)
    - severity: 0–1 score (higher = more urgent to fix)

    Args:
        df: query×page DataFrame from load_gsc_query_page.
        min_impressions: Minimum total impressions for a query to be considered.

    Returns:
        List of cannibalisation records sorted by severity descending.
    """
    if df.empty:
        return []

    results: list[dict[str, Any]] = []

    for query, group in df.groupby("query"):
        if len(group) < 2:
            continue
        total_impressions = group["impressions"].sum()
        if total_impressions < min_impressions:
            continue

        sorted_group = group.sort_values("position")
        primary = sorted_group.iloc[0]
        cannibal = sorted_group.iloc[1]

        position_gap = cannibal["position"] - primary["position"]

        # Higher severity when: many impressions, similar positions (< 5 apart), product vs product
        primary_type = _page_type(primary["url"])
        cannibal_type = _page_type(cannibal["url"])
        same_type = primary_type == cannibal_type

        impression_score = min(total_impressions / 500, 1.0)
        closeness_score = max(0.0, 1.0 - position_gap / 20)
        type_penalty = 1.2 if same_type else 1.0

        severity = round(min(1.0, impression_score * 0.5 + closeness_score * 0.5) * type_penalty, 3)

        results.append({
            "query": query,
            "pages_count": len(group),
            "total_impressions": int(total_impressions),
            "primary_url": primary["url"],
            "primary_position": round(float(primary["position"]), 1),
            "primary_type": primary_type,
            "cannibal_url": cannibal["url"],
            "cannibal_position": round(float(cannibal["position"]), 1),
            "cannibal_type": cannibal_type,
            "position_gap": round(position_gap, 1),
            "severity": severity,
        })

    results.sort(key=lambda x: -x["severity"])
    return results


def _recommendation(record: dict[str, Any]) -> str:
    primary_type = record["primary_type"]
    cannibal_type = record["cannibal_type"]
    gap = record["position_gap"]

    if cannibal_type == "blog" and primary_type in ("product", "collection"):
        return f"Ajouter canonical sur l'article blog → {record['primary_url']}"
    if cannibal_type == "collection" and primary_type == "product":
        return "Différencier le contenu collection / rediriger ou canonical vers produit"
    if gap < 5:
        return "Fusionner les deux pages ou canonical de la plus faible vers la plus forte"
    return "Enrichir la page primaire, réduire le contenu ciblant ce mot-clé sur la page cannibale"


def render_markdown(
    results: list[dict[str, Any]],
    date: str,
) -> str:
    """Render cannibalization analysis as a Markdown report."""
    high = [r for r in results if r["severity"] >= 0.6]
    medium = [r for r in results if 0.3 <= r["severity"] < 0.6]
    low = [r for r in results if r["severity"] < 0.3]

    lines = [
        f"# Détecteur de Cannibalisation SEO — leoniedelacroix.com — {date}",
        "",
        "## Résumé",
        "",
        f"**{len(results)} requêtes cannibalisées** détectées",
        f"- 🔴 Sévérité haute (≥ 0.6) : {len(high)}",
        f"- 🟡 Sévérité moyenne (0.3–0.6) : {len(medium)}",
        f"- 🟢 Sévérité faible (< 0.3) : {len(low)}",
        "",
        "> Une requête cannibalisée = 2+ pages du site en compétition pour la même recherche.",
        "> La page primaire est celle avec la meilleure position (chiffre le plus bas).",
        "",
        "---",
        "",
    ]

    if not results:
        lines += [
            "Aucune cannibalisation détectée avec les données disponibles.",
            "",
            "*Généré automatiquement par le pipeline SEO leoniedelacroix.com*",
        ]
        return "\n".join(lines)

    lines += [
        "## Cannibalisation par sévérité",
        "",
        "| Requête | Impressions | Page primaire | Pos. | Page cannibale | Pos. | Sévérité |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in results:
        primary_short = r["primary_url"].split("/")[-1] or "/"
        cannibal_short = r["cannibal_url"].split("/")[-1] or "/"
        emoji = "🔴" if r["severity"] >= 0.6 else "🟡" if r["severity"] >= 0.3 else "🟢"
        lines.append(
            f"| `{r['query'][:40]}` "
            f"| {r['total_impressions']} "
            f"| `{primary_short[:30]}` "
            f"| {r['primary_position']} "
            f"| `{cannibal_short[:30]}` "
            f"| {r['cannibal_position']} "
            f"| {emoji} {r['severity']} |"
        )

    lines += ["", "---", "", "## Actions recommandées", ""]

    for r in [r for r in results if r["severity"] >= 0.3]:
        lines += [
            f"### `{r['query']}` — sévérité {r['severity']}",
            "",
            f"- **Page primaire** : `{r['primary_url']}` (pos. {r['primary_position']}, type: {r['primary_type']})",
            f"- **Page cannibale** : `{r['cannibal_url']}` (pos. {r['cannibal_position']}, type: {r['cannibal_type']})",
            f"- **Action** : {_recommendation(r)}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Bonnes pratiques anti-cannibalisation",
        "",
        "1. **Canonical** — pointer les pages dupliquées vers la page principale",
        "2. **Contenu distinct** — chaque page doit cibler un intent différent",
        "3. **Maillage interne** — ne pas créer de liens internes croisés entre pages cannibales",
        "4. **Consolidation** — fusionner deux pages faibles en une seule plus forte",
        "",
        "*Généré automatiquement par le pipeline SEO leoniedelacroix.com*",
    ]
    return "\n".join(lines)


@click.command()
@click.option("--input", "input_path", default="data/raw/gsc_query_page.csv", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--json-output", default="data/raw/cannibalization.json", show_default=True)
@click.option("--min-impressions", default=None, type=int, help="Override min impressions threshold")
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(input_path: str, output_dir: str, json_output: str, min_impressions: int | None, tenant: str | None) -> None:
    """Detect pages competing for the same queries (keyword cannibalization)."""
    cfg = get_config(tenant)
    t = cfg.alert_thresholds
    effective_min = min_impressions if min_impressions is not None else t.cannibalization_min_impressions
    console.print("[bold cyan]► Detecting keyword cannibalization[/bold cyan]")

    df = load_gsc_query_page(input_path)

    if df.empty:
        console.print(f"  [yellow]⚠[/yellow] No data at {input_path} — skipping")
        return

    results = detect_cannibal_pairs(df, min_impressions=effective_min)

    high = sum(1 for r in results if r["severity"] >= t.cannibalization_severity_high)
    console.print(f"  {len(results)} cannibalized queries found ({high} high severity)")

    table = Table(title="Top Cannibalization Issues")
    table.add_column("Query", max_width=35)
    table.add_column("Impressions", justify="right")
    table.add_column("Primary", max_width=25)
    table.add_column("Cannibal", max_width=25)
    table.add_column("Severity", justify="right")

    for r in results[:10]:
        color = "red" if r["severity"] >= 0.6 else "yellow" if r["severity"] >= 0.3 else "green"
        table.add_row(
            r["query"][:35],
            str(r["total_impressions"]),
            r["primary_url"].split("/")[-1][:25] or "/",
            r["cannibal_url"].split("/")[-1][:25] or "/",
            f"[{color}]{r['severity']}[/{color}]",
        )
    console.print(table)

    Path(json_output).parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    date = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cannibalization.md"
    out_path.write_text(render_markdown(results, date), encoding="utf-8")

    console.print(f"  [green]✓[/green] {len(results)} issues → {out_path}")
    console.print(f"  [green]✓[/green] JSON → {json_output}")


if __name__ == "__main__":
    main()
