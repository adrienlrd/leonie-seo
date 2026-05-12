"""Score product pages on E-E-A-T dimensions (Experience, Expertise, Authoritativeness, Trust)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from scripts._config import get_config, load_niche

console = Console()


def _count_signals(text: str, signals: list[str]) -> tuple[int, int]:
    """Return (found, total) for a signal list against normalized text."""
    norm = text.lower()
    found = sum(1 for s in signals if s in norm)
    return found, len(signals)


def score_page(product: dict[str, Any], niche=None) -> dict[str, Any]:
    """Compute E-E-A-T scores for a single product.

    Args:
        product: Product dict with keys: handle, title, description.
        niche: Optional NicheConfig. Defaults to active tenant's niche.

    Returns:
        Dict with dimension scores, global score, and missing signals.
    """
    _niche = niche or load_niche(get_config().niche)
    dim = _niche.eeat_dimensions
    weights = dim.weights

    title = product.get("title", "")
    description = (product.get("description") or "").strip()
    text = f"{title} {description}"

    exp_found, exp_total = _count_signals(text, dim.experience)
    exp_found2, exp_total2 = _count_signals(text, dim.expertise)
    auth_found, auth_total = _count_signals(text, dim.authority)
    trust_found, trust_total = _count_signals(text, dim.trust)

    exp_score = round(exp_found / max(exp_total, 1), 3)
    expertise_score = round(exp_found2 / max(exp_total2, 1), 3)
    auth_score = round(auth_found / max(auth_total, 1), 3)
    trust_score = round(trust_found / max(trust_total, 1), 3)

    global_score = round(
        weights.get("experience", 0.20) * exp_score
        + weights.get("expertise", 0.30) * expertise_score
        + weights.get("authority", 0.25) * auth_score
        + weights.get("trust", 0.25) * trust_score,
        3,
    )

    exp_missing = [s for s in dim.experience if s not in text.lower()]
    expertise_missing = [s for s in dim.expertise if s not in text.lower()]
    auth_missing = [s for s in dim.authority if s not in text.lower()]
    trust_missing = [s for s in dim.trust if s not in text.lower()]

    return {
        "handle": product.get("handle", ""),
        "title": title,
        "description_words": len(description.split()),
        "experience_score": exp_score,
        "expertise_score": expertise_score,
        "authority_score": auth_score,
        "trust_score": trust_score,
        "global_score": global_score,
        "top_missing_experience": exp_missing[:3],
        "top_missing_expertise": expertise_missing[:3],
        "top_missing_authority": auth_missing[:3],
        "top_missing_trust": trust_missing[:3],
    }


def load_products(snapshot_path: str) -> list[dict[str, Any]]:
    with open(snapshot_path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        p
        for p in data.get("products", [])
        if not p["title"].startswith("Pet ") and p["title"] != "Le Harnais Haute Couture (test)"
    ]


def render_markdown(results: list[dict[str, Any]], date: str) -> str:
    """Render E-E-A-T scores as a Markdown report."""
    _site = get_config().domain
    if not results:
        return f"# Score E-E-A-T — {_site} — {date}\n\nAucun produit analysé.\n"

    avg_global = round(sum(r["global_score"] for r in results) / len(results), 3)
    avg_exp = round(sum(r["experience_score"] for r in results) / len(results), 2)
    avg_expertise = round(sum(r["expertise_score"] for r in results) / len(results), 2)
    avg_auth = round(sum(r["authority_score"] for r in results) / len(results), 2)
    avg_trust = round(sum(r["trust_score"] for r in results) / len(results), 2)

    lines = [
        f"# Score E-E-A-T — {_site} — {date}",
        "",
        "## Résumé",
        "",
        "| Dimension | Score moyen | Poids |",
        "|---|---|---|",
        f"| **Global pondéré** | **{avg_global:.0%}** | — |",
        f"| Experience | {avg_exp:.0%} | 20% |",
        f"| Expertise | {avg_expertise:.0%} | 30% |",
        f"| Authoritativeness | {avg_auth:.0%} | 25% |",
        f"| Trustworthiness | {avg_trust:.0%} | 25% |",
        "",
        "> Seuil minimum recommandé : **40%** par dimension, **45%** global.",
        "> Référence marché premium petfood FR : ~55–65%.",
        "",
        "---",
        "",
        "## Scores par produit",
        "",
        "| Produit | Global | Exp. | Expert. | Auth. | Trust | Mots |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in sorted(results, key=lambda x: -x["global_score"]):
        emoji = "✅" if r["global_score"] >= 0.45 else "⚠️" if r["global_score"] >= 0.25 else "🔴"
        lines.append(
            f"| {r['title'][:35]} "
            f"| {emoji} **{r['global_score']:.0%}** "
            f"| {r['experience_score']:.0%} "
            f"| {r['expertise_score']:.0%} "
            f"| {r['authority_score']:.0%} "
            f"| {r['trust_score']:.0%} "
            f"| {r['description_words']} |"
        )

    lines += ["", "---", "", "## Actions prioritaires (score < 45%)", ""]

    weak = [r for r in sorted(results, key=lambda x: x["global_score"]) if r["global_score"] < 0.45]
    if not weak:
        lines += ["Tous les produits atteignent le seuil minimum. 🎉", ""]
    else:
        for r in weak:
            lines += [
                f"### {r['title']} — {r['global_score']:.0%}",
                "",
            ]
            if r["experience_score"] < 0.1:
                lines += [
                    "**Experience** — ajouter témoignages ou retours d'usage concrets :",
                    *[f"- `{s}`" for s in r["top_missing_experience"][:2]],
                    "",
                ]
            if r["expertise_score"] < 0.15:
                lines += [
                    "**Expertise** — citer une validation professionnelle :",
                    *[f"- `{s}`" for s in r["top_missing_expertise"][:2]],
                    "",
                ]
            if r["authority_score"] < 0.15:
                lines += [
                    "**Autorité** — rappeler l'origine et la fabrication :",
                    *[f"- `{s}`" for s in r["top_missing_authority"][:2]],
                    "",
                ]
            if r["trust_score"] < 0.15:
                lines += [
                    "**Confiance** — ajouter signaux de sécurité et garanties :",
                    *[f"- `{s}`" for s in r["top_missing_trust"][:2]],
                    "",
                ]

    lines += [
        "---",
        "",
        "## Recommandations globales",
        "",
        "1. **Experience** — intégrer 1-2 phrases de retour client ou d'usage terrain par fiche produit",
        "2. **Expertise** — mentionner `vétérinaire` ou `recommandé` dans toutes les fiches fontaines/filtres",
        "3. **Autorité** — systématiser `fabriqué en France` dans toutes les fiches vêtements",
        "4. **Confiance** — rappeler `garantie`, `sans BPA`, matériaux `certifiés alimentaires` pour fontaines et accessoires",
        "",
        f"*Généré automatiquement par le pipeline SEO {get_config().domain}*",
    ]
    return "\n".join(lines)


@click.command()
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--json-output", default="data/raw/eeat_scores.json", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(snapshot: str, output_dir: str, json_output: str, tenant: str | None) -> None:
    """Score all product pages on E-E-A-T dimensions."""
    get_config(tenant)  # preload tenant
    console.print("[bold cyan]► Scoring E-E-A-T per product page[/bold cyan]")

    products = load_products(snapshot)
    results = [score_page(p) for p in products]

    table = Table(title="E-E-A-T Scores")
    table.add_column("Product", max_width=30)
    table.add_column("Global", justify="right")
    table.add_column("Expertise", justify="right")
    table.add_column("Authority", justify="right")
    table.add_column("Trust", justify="right")

    for r in sorted(results, key=lambda x: -x["global_score"]):
        color = (
            "green"
            if r["global_score"] >= 0.45
            else "yellow"
            if r["global_score"] >= 0.25
            else "red"
        )
        table.add_row(
            r["title"][:30],
            f"[{color}]{r['global_score']:.0%}[/{color}]",
            f"{r['expertise_score']:.0%}",
            f"{r['authority_score']:.0%}",
            f"{r['trust_score']:.0%}",
        )
    console.print(table)

    Path(json_output).parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "eeat_scores.md"
    out_path.write_text(render_markdown(results, date), encoding="utf-8")

    avg = round(sum(r["global_score"] for r in results) / max(len(results), 1), 3)
    console.print(f"  [green]✓[/green] {len(results)} pages scored — avg {avg:.0%} → {out_path}")
    console.print(f"  [green]✓[/green] JSON → {json_output}")


if __name__ == "__main__":
    main()
