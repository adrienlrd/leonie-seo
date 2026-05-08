"""Analyse long-tail keyword coverage: rank target keywords against GSC + Shopify data."""

import json
import re
from pathlib import Path
from typing import Any

import click
import pandas as pd
import yaml
from rich.console import Console
from rich.table import Table

from scripts._config import get_config

console = Console()

_STOP_WORDS = {
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "un",
    "une",
    "pour",
    "en",
    "et",
    "ou",
    "avec",
    "sans",
    "sur",
    "par",
    "au",
    "aux",
    "ce",
    "se",
    "est",
    "son",
    "sa",
    "ses",
    "mon",
    "ma",
    "mes",
    "votre",
    "notre",
}

# Minimum tokens from a keyword that must appear for a match
_MATCH_THRESHOLD = 2


def _tokenize(text: str) -> set[str]:
    """Lowercase, remove punctuation, strip stop words."""
    tokens = re.findall(r"[a-zàâäéèêëïîôùûüç]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


def load_keywords(yaml_path: str) -> dict[str, list[str]]:
    """Load keywords grouped by category from YAML.

    Args:
        yaml_path: Path to keywords.yaml.

    Returns:
        Dict mapping category name to list of keyword strings.
    """
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_snapshot(snapshot_path: str) -> tuple[list[dict], list[dict]]:
    """Return (products, collections) from the Shopify snapshot JSON.

    Args:
        snapshot_path: Path to shopify_snapshot.json.

    Returns:
        Tuple of (products list, collections list).
    """
    with open(snapshot_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", []), data.get("collections", [])


def _site_tokens(products: list[dict], collections: list[dict]) -> list[tuple[str, str, str]]:
    """Build a list of (tokens_set_repr, label, url_path) for all site resources."""
    entries: list[tuple[set[str], str, str]] = []
    for p in products:
        title = p.get("title", "")
        handle = p.get("handle", "")
        tokens = _tokenize(title) | _tokenize(handle)
        entries.append((tokens, title, f"/products/{handle}"))
    for c in collections:
        title = c.get("title", "")
        handle = c.get("handle", "")
        tokens = _tokenize(title) | _tokenize(handle)
        entries.append((tokens, title, f"/collections/{handle}"))
    return entries  # type: ignore[return-value]


def match_keyword_to_gsc(keyword: str, gsc_df: pd.DataFrame) -> pd.DataFrame:
    """Find GSC rows whose URL matches the keyword tokens.

    Args:
        keyword: Target keyword string.
        gsc_df: DataFrame with columns url, clicks, impressions, ctr, position.

    Returns:
        Filtered DataFrame of matching rows.
    """
    kw_tokens = _tokenize(keyword)
    if not kw_tokens:
        return gsc_df.iloc[0:0]

    def _url_matches(url: str) -> bool:
        url_tokens = _tokenize(url)
        return len(kw_tokens & url_tokens) >= min(_MATCH_THRESHOLD, len(kw_tokens))

    mask = gsc_df["url"].apply(_url_matches)
    return gsc_df[mask]


def match_keyword_to_site(
    keyword: str,
    site_entries: list[tuple[set[str], str, str]],
) -> list[dict[str, str]]:
    """Find products/collections whose title or handle matches the keyword.

    Args:
        keyword: Target keyword string.
        site_entries: List of (tokens, label, path) tuples from _site_tokens().

    Returns:
        List of dicts with keys: label, path.
    """
    kw_tokens = _tokenize(keyword)
    if not kw_tokens:
        return []

    matches = []
    for tokens, label, path in site_entries:
        # Threshold adapts to the smaller side: a single-word collection
        # ("Chien") matches any keyword containing that word.
        threshold = min(_MATCH_THRESHOLD, len(kw_tokens), len(tokens))
        threshold = max(threshold, 1)
        if len(kw_tokens & tokens) >= threshold:
            matches.append({"label": label, "path": path})
    return matches


def classify_coverage(
    keyword: str,
    gsc_matches: pd.DataFrame,
    site_matches: list[dict],
) -> dict[str, Any]:
    """Classify a keyword's coverage status and compute a priority score.

    Status values:
    - ranking: keyword appears in GSC with impressions > 0
    - on_site: product/collection exists but no GSC data
    - gap: no product and no GSC data

    Args:
        keyword: Target keyword string.
        gsc_matches: Matching GSC rows for this keyword.
        site_matches: Matching site resources for this keyword.

    Returns:
        Dict with keys: keyword, status, position, impressions, clicks,
        site_page, opportunity_score, recommendation.
    """
    has_gsc = not gsc_matches.empty
    has_site = len(site_matches) > 0

    if has_gsc:
        best = gsc_matches.sort_values("impressions", ascending=False).iloc[0]
        status = "ranking"
        position = round(float(best["position"]), 1)
        impressions = int(best["impressions"])
        clicks = int(best["clicks"])
        site_page = best["url"]
        # Opportunity: low CTR or far from page 1
        opp = impressions / position if position > 0 else 0.0
        if position > 10:
            recommendation = "Quick win — enrichir contenu + méta pour passer page 1"
        elif float(best["ctr"]) < 0.05:
            recommendation = "CTR faible — réécrire méta title/description"
        else:
            recommendation = "Bien positionné — maintenir et surveiller"
    elif has_site:
        status = "on_site"
        position = None
        impressions = 0
        clicks = 0
        site_page = site_matches[0]["path"]
        opp = 5.0  # mid priority
        recommendation = "Page existe mais non indexée / pas de trafic GSC — soumettre sitemap, vérifier indexation"
    else:
        status = "gap"
        position = None
        impressions = 0
        clicks = 0
        site_page = None
        opp = 3.0  # lower priority than on_site
        recommendation = "Contenu manquant — créer fiche produit, collection ou article blog"

    return {
        "keyword": keyword,
        "status": status,
        "position": position,
        "impressions": impressions,
        "clicks": clicks,
        "site_page": site_page,
        "opportunity_score": round(opp, 2),
        "recommendation": recommendation,
    }


def build_gap_report(
    keywords_by_cat: dict[str, list[str]],
    gsc_df: pd.DataFrame,
    products: list[dict],
    collections: list[dict],
) -> list[dict[str, Any]]:
    """Build a full keyword coverage report.

    Args:
        keywords_by_cat: Dict of category → keyword list.
        gsc_df: GSC performance DataFrame.
        products: Shopify products list.
        collections: Shopify collections list.

    Returns:
        List of coverage dicts sorted by status priority then opportunity_score.
    """
    site_entries = _site_tokens(products, collections)
    results = []

    for category, keywords in keywords_by_cat.items():
        for kw in keywords:
            gsc_matches = match_keyword_to_gsc(kw, gsc_df)
            site_matches = match_keyword_to_site(kw, site_entries)
            coverage = classify_coverage(kw, gsc_matches, site_matches)
            coverage["category"] = category
            results.append(coverage)

    # Sort: ranking first (by opp score desc), then on_site, then gap
    status_order = {"ranking": 0, "on_site": 1, "gap": 2}
    results.sort(key=lambda x: (status_order[x["status"]], -x["opportunity_score"]))
    return results


def _gap_table(report: list[dict[str, Any]]) -> Table:
    status_styles = {"ranking": "green", "on_site": "yellow", "gap": "red"}
    status_labels = {"ranking": "✅ Ranking", "on_site": "⚠ Sur site", "gap": "❌ Gap"}

    table = Table(title="Analyse longue traîne — Couverture mots-clés", show_lines=True)
    table.add_column("Mot-clé", style="cyan", max_width=38)
    table.add_column("Catégorie", width=12)
    table.add_column("Statut", width=12)
    table.add_column("Pos.", width=5)
    table.add_column("Impr.", width=6)
    table.add_column("Page", max_width=32)
    table.add_column("Recommandation", max_width=40)

    for r in report:
        color = status_styles[r["status"]]
        label = status_labels[r["status"]]
        pos = str(r["position"]) if r["position"] else "—"
        impr = str(r["impressions"]) if r["impressions"] else "—"
        page = str(r["site_page"] or "—")
        if page.startswith("https://"):
            page = page.split(get_config().domain)[-1]

        table.add_row(
            r["keyword"],
            r["category"],
            f"[{color}]{label}[/{color}]",
            pos,
            impr,
            page[:32],
            r["recommendation"],
        )

    return table


def _summary(report: list[dict[str, Any]]) -> None:
    counts = {"ranking": 0, "on_site": 0, "gap": 0}
    for r in report:
        counts[r["status"]] += 1

    console.print(
        f"\n  [green]✅ {counts['ranking']} ranking[/green]  "
        f"[yellow]⚠ {counts['on_site']} sur site sans trafic[/yellow]  "
        f"[red]❌ {counts['gap']} gaps (contenu manquant)[/red]"
    )

    gaps = [r for r in report if r["status"] == "gap"]
    if gaps:
        console.print("\n  [bold red]Gaps prioritaires à combler :[/bold red]")
        for g in gaps[:5]:
            console.print(
                f"    • [cyan]{g['keyword']}[/cyan] [{g['category']}] — {g['recommendation']}"
            )


@click.command()
@click.option("--keywords", "kw_path", default="config/keywords.yaml", show_default=True)
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--gsc", "gsc_path", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--output", default="data/raw/longtail_gaps.json", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(kw_path: str, snapshot: str, gsc_path: str, output: str, tenant: str | None) -> None:
    """Analyse long-tail keyword coverage against GSC data and Shopify catalog.

    For each target keyword, reports:
    - ranking: already getting impressions in GSC
    - on_site: product/collection exists but no GSC data
    - gap: no coverage at all → content to create
    """
    get_config(tenant)  # preload tenant
    console.print("[bold cyan]► Analyse couverture mots-clés longue traîne[/bold cyan]")

    keywords_by_cat = load_keywords(kw_path)
    products, collections = load_snapshot(snapshot)
    gsc_df = pd.read_csv(gsc_path)

    total_kw = sum(len(v) for v in keywords_by_cat.values())
    console.print(
        f"  {total_kw} mots-clés · {len(products)} produits · {len(collections)} collections · {len(gsc_df)} URLs GSC"
    )

    report = build_gap_report(keywords_by_cat, gsc_df, products, collections)

    console.print(_gap_table(report))
    _summary(report)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n  [green]✓[/green] Saved → {output}")


if __name__ == "__main__":
    main()
