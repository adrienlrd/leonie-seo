"""Detect SEO opportunities from Google Search Console data."""

import json
from pathlib import Path
from typing import Any

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()

# CTR benchmarks by position used to estimate traffic gain
_CTR_BY_POSITION: dict[int, float] = {
    1: 0.28,
    2: 0.15,
    3: 0.11,
    4: 0.08,
    5: 0.06,
    6: 0.05,
    7: 0.04,
    8: 0.03,
    9: 0.03,
    10: 0.025,
}
_CTR_TARGET_PAGE1 = 0.05  # conservative target CTR for a page-1 result


def _page_type(url: str) -> str:
    """Infer page type from URL path."""
    path = url.split("//", 1)[-1].split("/", 1)[-1] if "//" in url else url
    if not path or path == "" or path.endswith(".com") or path.endswith(".com/"):
        return "homepage"
    if "/products/" in url:
        return "product"
    if "/collections/" in url:
        return "collection"
    if "/pages/" in url:
        return "page"
    if "/blogs/" in url:
        return "blog"
    return "other"


def _action_for_zone(zone: str, page_type: str) -> str:
    """Return a concrete recommended action given the zone and page type."""
    if zone == "quick_win":
        if page_type in ("product", "collection"):
            return "Enrichir contenu + optimiser méta title/description"
        return "Optimiser méta title et enrichir contenu de page"
    if zone == "low_ctr":
        return "Réécrire méta title (accroche) + méta description (CTA)"
    if zone == "long_term":
        return "Créer/enrichir contenu longue traîne, renforcer maillage interne"
    return "Surveiller"


def _estimated_gain(impressions: float, current_ctr: float, target_pos: int = 5) -> int:
    """Estimate additional monthly clicks if the page reaches target_pos.

    Args:
        impressions: Current impressions over the period.
        current_ctr: Current click-through rate (0–1).
        target_pos: Target position after optimization.

    Returns:
        Estimated additional clicks (rounded, minimum 0).
    """
    target_ctr = _CTR_BY_POSITION.get(target_pos, _CTR_TARGET_PAGE1)
    gain = impressions * (target_ctr - current_ctr)
    return max(0, round(gain))


def classify_url(
    url: str,
    position: float,
    impressions: int,
    ctr: float,
    min_impressions: int = 10,
) -> str | None:
    """Classify a URL into an opportunity zone, or return None if not eligible.

    Args:
        url: Full page URL.
        position: Average GSC position.
        impressions: Total impressions over the period.
        ctr: Click-through rate (0–1).
        min_impressions: Minimum impressions threshold to be considered.

    Returns:
        Zone string ('quick_win', 'low_ctr', 'long_term') or None.
    """
    if impressions < min_impressions:
        return None
    if 11 <= position <= 20:
        return "quick_win"
    if 4 <= position <= 10 and ctr < _CTR_TARGET_PAGE1:
        return "low_ctr"
    if 21 <= position <= 50 and impressions >= 50:
        return "long_term"
    return None


def score_opportunity(impressions: float, position: float) -> float:
    """Compute an opportunity score: high impressions close to page 1 score highest.

    Args:
        impressions: Total impressions over the period.
        position: Average GSC position.

    Returns:
        Opportunity score (higher = better).
    """
    if position <= 0:
        return 0.0
    return round(impressions / position, 2)


def detect_opportunities(
    df: pd.DataFrame,
    min_impressions: int = 10,
    top: int = 20,
) -> list[dict[str, Any]]:
    """Identify the top SEO opportunities from a GSC performance DataFrame.

    Args:
        df: DataFrame with columns url, clicks, impressions, ctr, position.
        min_impressions: Minimum impressions to include a URL.
        top: Maximum number of results to return.

    Returns:
        List of opportunity dicts sorted by opportunity_score descending.
    """
    results: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        url = str(row["url"])
        position = float(row["position"])
        impressions = int(row["impressions"])
        clicks = int(row["clicks"])
        ctr = float(row["ctr"])

        zone = classify_url(url, position, impressions, ctr, min_impressions)
        if zone is None:
            continue

        ptype = _page_type(url)
        target_pos = 5 if zone == "quick_win" else 3 if zone == "low_ctr" else 8
        gain = _estimated_gain(impressions, ctr, target_pos)

        results.append(
            {
                "url": url,
                "page_type": ptype,
                "zone": zone,
                "position": round(position, 1),
                "impressions": impressions,
                "clicks": clicks,
                "ctr_pct": round(ctr * 100, 1),
                "opportunity_score": score_opportunity(impressions, position),
                "estimated_gain_clicks": gain,
                "action": _action_for_zone(zone, ptype),
            }
        )

    results.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return results[:top]


def _opportunities_table(opps: list[dict[str, Any]]) -> Table:
    table = Table(title="GSC Opportunities", show_lines=True)
    table.add_column("URL", style="cyan", max_width=45)
    table.add_column("Zone", width=12)
    table.add_column("Pos", width=5)
    table.add_column("Impr.", width=6)
    table.add_column("CTR%", width=6)
    table.add_column("+Clics", width=7)
    table.add_column("Action", max_width=42)

    zone_colors = {
        "quick_win": "green",
        "low_ctr": "yellow",
        "long_term": "blue",
    }

    for o in opps:
        color = zone_colors.get(o["zone"], "white")
        label = {"quick_win": "Quick win", "low_ctr": "CTR faible", "long_term": "Long terme"}.get(
            o["zone"], o["zone"]
        )
        path = o["url"].split("leoniedelacroix.com")[-1] or "/"
        table.add_row(
            path,
            f"[{color}]{label}[/{color}]",
            str(o["position"]),
            str(o["impressions"]),
            f"{o['ctr_pct']}%",
            f"[green]+{o['estimated_gain_clicks']}[/green]",
            o["action"],
        )

    return table


@click.command()
@click.option("--gsc", "gsc_path", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--output", default="data/raw/gsc_opportunities.json", show_default=True)
@click.option("--min-impressions", default=10, show_default=True)
@click.option("--top", default=20, show_default=True, help="Max results to show")
def main(gsc_path: str, output: str, min_impressions: int, top: int) -> None:
    """Detect SEO opportunities from Google Search Console data.

    Classifies URLs into three zones:
    - Quick wins (pos 11-20): push to page 1
    - Low CTR (pos 4-10): improve meta title/description
    - Long term (pos 21-50, high impressions): invest in content
    """
    console.print("[bold cyan]► Detecting GSC opportunities[/bold cyan]")

    df = pd.read_csv(gsc_path)
    if df.empty:
        console.print("[yellow]No GSC data found.[/yellow]")
        return

    opps = detect_opportunities(df, min_impressions=min_impressions, top=top)

    if not opps:
        console.print("[yellow]No opportunities found with current thresholds.[/yellow]")
        return

    console.print(_opportunities_table(opps))

    zone_counts = {}
    for o in opps:
        zone_counts[o["zone"]] = zone_counts.get(o["zone"], 0) + 1

    console.print(f"\n  [bold]{len(opps)}[/bold] opportunité(s) détectée(s) :", end="  ")
    for zone, count in zone_counts.items():
        label = {"quick_win": "Quick wins", "low_ctr": "CTR faible", "long_term": "Long terme"}.get(
            zone, zone
        )
        console.print(f"[bold]{count}[/bold] {label}", end="  ")
    console.print()

    total_gain = sum(o["estimated_gain_clicks"] for o in opps)
    console.print(f"  Gain trafic estimé (total) : [bold green]+{total_gain} clics[/bold green]")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(opps, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"  [green]✓[/green] Saved → {output}")


if __name__ == "__main__":
    main()
