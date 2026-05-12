"""Generate a monthly SEO synthesis report as print-ready HTML."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import pandas as pd
from rich.console import Console

from scripts._config import get_config

console = Console()

_CSS = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Georgia, serif; color: #1a1a1a; background: #fff; max-width: 900px; margin: 0 auto; padding: 2rem; }
  h1 { font-size: 1.8rem; border-bottom: 3px solid #1a1a1a; padding-bottom: .5rem; margin-bottom: 1.5rem; }
  h2 { font-size: 1.2rem; text-transform: uppercase; letter-spacing: .08em; color: #444; margin: 2rem 0 .75rem; border-left: 4px solid #1a1a1a; padding-left: .75rem; }
  h3 { font-size: 1rem; margin: 1rem 0 .4rem; }
  p, li { font-size: .92rem; line-height: 1.6; }
  .meta { color: #666; font-size: .82rem; margin-bottom: 2rem; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1rem 0 2rem; }
  .kpi { border: 1px solid #ddd; border-radius: 4px; padding: .9rem 1rem; text-align: center; }
  .kpi .val { font-size: 2rem; font-weight: bold; display: block; }
  .kpi .lbl { font-size: .75rem; color: #666; text-transform: uppercase; letter-spacing: .05em; }
  table { width: 100%; border-collapse: collapse; font-size: .85rem; margin-bottom: 1.5rem; }
  th { background: #1a1a1a; color: #fff; padding: .4rem .6rem; text-align: left; font-weight: normal; }
  td { padding: .35rem .6rem; border-bottom: 1px solid #eee; }
  tr:hover td { background: #fafafa; }
  .badge { display: inline-block; padding: .15rem .4rem; border-radius: 3px; font-size: .75rem; font-weight: bold; }
  .red { background: #fee; color: #c00; }
  .yellow { background: #ffd; color: #850; }
  .green { background: #efe; color: #060; }
  ul.actions { padding-left: 1.2rem; }
  ul.actions li { margin-bottom: .4rem; }
  footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; font-size: .75rem; color: #999; }
  @media print {
    body { max-width: 100%; padding: 1cm; font-size: 10pt; }
    .kpi-grid { grid-template-columns: repeat(4, 1fr); }
    h2 { page-break-before: auto; }
    table { page-break-inside: avoid; }
  }
</style>
"""


def load_gsc(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["url", "clicks", "impressions", "ctr", "position"])
    return pd.read_csv(p)


def load_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def compute_kpis(gsc: pd.DataFrame) -> dict[str, Any]:
    if gsc.empty:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0, "pages": 0}
    return {
        "clicks": int(gsc["clicks"].sum()),
        "impressions": int(gsc["impressions"].sum()),
        "ctr": round(float(gsc["ctr"].mean()) * 100, 2),
        "position": round(float(gsc["position"].mean()), 1),
        "pages": len(gsc),
    }


def top_pages(gsc: pd.DataFrame, n: int = 10) -> list[dict[str, Any]]:
    if gsc.empty:
        return []
    top = gsc.nlargest(n, "clicks")[["url", "clicks", "impressions", "ctr", "position"]]
    return top.to_dict("records")


def top_queries_from_opportunities(opportunities: list[dict]) -> list[dict[str, Any]]:
    rows = [
        {
            "query": o.get("query", ""),
            "impressions": o.get("impressions", 0),
            "position": o.get("position", 0),
            "zone": o.get("zone", ""),
        }
        for o in opportunities
    ]
    rows.sort(key=lambda x: -x["impressions"])
    return rows[:10]


def quick_wins(opportunities: list[dict], n: int = 5) -> list[dict[str, Any]]:
    wins = [o for o in opportunities if o.get("zone") == "quick_win"]
    wins.sort(key=lambda x: -x.get("impressions", 0))
    return wins[:n]


def _avg_eeat(eeat_scores: list[dict]) -> float:
    if not eeat_scores:
        return 0.0
    return round(sum(r.get("global_score", 0) for r in eeat_scores) / len(eeat_scores), 3)


def _recommendations(
    kpis: dict[str, Any],
    wins: list[dict],
    cannibal: list[dict],
    eeat_avg: float,
) -> list[str]:
    recs: list[str] = []
    if wins:
        recs.append(
            f"Optimiser les {len(wins)} pages en positions 11–20 : enrichir le contenu + méta title/description."
        )
    high_cannibal = [c for c in cannibal if c.get("severity", 0) >= 0.6]
    if high_cannibal:
        recs.append(
            f"Résoudre {len(high_cannibal)} cas de cannibalisation sévère : canonical ou consolidation de pages."
        )
    if eeat_avg < 0.35:
        recs.append(
            "Score E-E-A-T moyen faible — ajouter références vétérinaires, 'fabriqué en France' et garanties dans toutes les fiches produit."
        )
    if kpis["ctr"] < 3.0:
        recs.append(
            "CTR moyen sous 3 % — réécrire les méta titles des 10 premières pages pour améliorer l'accroche."
        )
    if kpis["position"] > 20:
        recs.append(
            "Position moyenne > 20 — créer des contenus longue traîne ciblant les requêtes niche petfood FR."
        )
    if not recs:
        recs.append(
            "Maintenir le rythme : audit hebdomadaire + publication d'un article blog mensuel."
        )
    return recs[:5]


def render_html(
    kpis: dict[str, Any],
    pages: list[dict],
    queries: list[dict],
    wins: list[dict],
    cannibal: list[dict],
    eeat_scores: list[dict],
    date: str,
) -> str:
    eeat_avg = _avg_eeat(eeat_scores)
    recs = _recommendations(kpis, wins, cannibal, eeat_avg)
    cannibal_high = sum(1 for c in cannibal if c.get("severity", 0) >= 0.6)

    def badge(val: float, thresholds: tuple[float, float]) -> str:
        cls = "green" if val >= thresholds[1] else "yellow" if val >= thresholds[0] else "red"
        return f'<span class="badge {cls}">{val}</span>'

    # KPI cards
    kpi_html = f"""
    <div class="kpi-grid">
      <div class="kpi"><span class="val">{kpis["clicks"]:,}</span><span class="lbl">Clics (90j)</span></div>
      <div class="kpi"><span class="val">{kpis["impressions"]:,}</span><span class="lbl">Impressions</span></div>
      <div class="kpi"><span class="val">{kpis["ctr"]}%</span><span class="lbl">CTR moyen</span></div>
      <div class="kpi"><span class="val">{kpis["position"]}</span><span class="lbl">Position moy.</span></div>
    </div>"""

    # Top pages table
    pages_rows = "".join(
        f"<tr><td><code>{r['url'].split('/')[-1] or '/'}</code></td>"
        f"<td>{int(r['clicks'])}</td>"
        f"<td>{int(r['impressions'])}</td>"
        f"<td>{r['ctr']:.1%}</td>"
        f"<td>{r['position']:.1f}</td></tr>"
        for r in pages
    )
    pages_table = (
        f"""
    <table>
      <thead><tr><th>Page</th><th>Clics</th><th>Impressions</th><th>CTR</th><th>Position</th></tr></thead>
      <tbody>{pages_rows}</tbody>
    </table>"""
        if pages_rows
        else "<p><em>Données GSC non disponibles.</em></p>"
    )

    # Quick wins table
    wins_rows = "".join(
        f"<tr><td>{w.get('query', '')[:50]}</td>"
        f"<td>{int(w.get('impressions', 0))}</td>"
        f"<td>{w.get('position', 0):.1f}</td>"
        f"<td>{w.get('action', '—')[:60]}</td></tr>"
        for w in wins
    )
    wins_table = (
        f"""
    <table>
      <thead><tr><th>Requête</th><th>Impressions</th><th>Position</th><th>Action</th></tr></thead>
      <tbody>{wins_rows}</tbody>
    </table>"""
        if wins_rows
        else "<p><em>Aucun quick win identifié.</em></p>"
    )

    # Recommendations list
    recs_html = "".join(f"<li>{r}</li>" for r in recs)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rapport SEO mensuel — {get_config().domain} — {date}</title>
  {_CSS}
</head>
<body>
  <h1>Rapport SEO mensuel</h1>
  <p class="meta">{get_config().domain} &nbsp;·&nbsp; {date} &nbsp;·&nbsp; {kpis["pages"]} pages indexées</p>

  <h2>KPIs clés — 90 derniers jours</h2>
  {kpi_html}

  <h2>Top 10 pages par clics</h2>
  {pages_table}

  <h2>Quick wins — positions 11–20</h2>
  {wins_table}

  <h2>Santé SEO globale</h2>
  <table>
    <thead><tr><th>Indicateur</th><th>Valeur</th><th>Seuil cible</th></tr></thead>
    <tbody>
      <tr><td>Score E-E-A-T moyen</td><td>{badge(round(eeat_avg * 100, 1), (25, 45))}%</td><td>≥ 45%</td></tr>
      <tr><td>Cannibalisation haute sévérité</td><td>{badge(cannibal_high, (0.1, 0.1))} cas</td><td>0</td></tr>
      <tr><td>CTR moyen</td><td>{badge(kpis["ctr"], (2, 4))}%</td><td>≥ 4%</td></tr>
      <tr><td>Position moyenne</td><td>{kpis["position"]}</td><td>≤ 20</td></tr>
    </tbody>
  </table>

  <h2>Recommandations du mois</h2>
  <ul class="actions">
    {recs_html}
  </ul>

  <footer>
    Généré automatiquement par le pipeline SEO {get_config().domain} &nbsp;·&nbsp; {date}<br>
    Pour imprimer en PDF : Ctrl+P → Enregistrer en PDF (désactiver les en-têtes/pieds de page).
  </footer>
</body>
</html>"""


@click.command()
@click.option("--gsc", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--opportunities", default="data/raw/gsc_opportunities.json", show_default=True)
@click.option("--cannibalization", default="data/raw/cannibalization.json", show_default=True)
@click.option("--eeat", default="data/raw/eeat_scores.json", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(
    gsc: str,
    opportunities: str,
    cannibalization: str,
    eeat: str,
    output_dir: str,
    tenant: str | None,
) -> None:
    """Generate a monthly SEO synthesis report as print-ready HTML."""
    get_config(tenant)  # preload tenant
    console.print("[bold cyan]► Generating monthly SEO report[/bold cyan]")

    gsc_df = load_gsc(gsc)
    opps = load_json(opportunities)
    cannibal = load_json(cannibalization)
    eeat_scores = load_json(eeat)

    kpis = compute_kpis(gsc_df)
    pages = top_pages(gsc_df)
    queries = top_queries_from_opportunities(opps)
    wins = quick_wins(opps)

    now = datetime.now(UTC)
    date = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    out_dir = Path(output_dir) / month
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "monthly_report.html"
    out_path.write_text(
        render_html(kpis, pages, queries, wins, cannibal, eeat_scores, date),
        encoding="utf-8",
    )

    console.print(
        f"  [green]✓[/green] {kpis['clicks']:,} clics · {kpis['impressions']:,} impressions"
    )
    console.print(f"  [green]✓[/green] Rapport → {out_path}")
    console.print("  [dim]→ Ouvrir dans un navigateur et Ctrl+P pour exporter en PDF[/dim]")


if __name__ == "__main__":
    main()
