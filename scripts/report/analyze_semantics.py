"""Semantic analysis of product descriptions vs competitor vocabulary and keyword targets."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from scripts._config import get_config

load_dotenv()

console = Console()

# ── Competitor semantic signals (Miacara, Zooplus, Wanimo benchmark) ───────

_PREMIUM_SIGNALS: list[str] = [
    # Fabrication / origine
    "made in france", "fabriqué en france", "fabriqué à la main", "fait main",
    "artisanal", "artisan", "couturière", "confectionné",
    # Matières
    "laine d'alpaga", "alpaga", "cachemire", "soie naturelle", "cuir véritable",
    "cuir pleine fleur", "coton bio", "lin naturel", "inox", "céramique",
    # Bien-être animal
    "confort", "ergonomique", "posture naturelle", "liberté de mouvement",
    "non-restrictif", "respirant", "hypoallergénique", "sans bpa", "alimentaire",
    # Durabilité
    "durable", "résistant", "lavable", "entretien facile", "garantie",
    # Design
    "design", "élégant", "premium", "luxe", "haut de gamme", "raffiné",
    # Service
    "livraison", "retour", "satisfait", "remboursé", "france métropolitaine",
]

_EEAT_SIGNALS: list[str] = [
    "vétérinaire", "vétérinaires", "comportementaliste", "comportementalistes",
    "expert", "experts", "spécialiste", "spécialistes",
    "recommandé", "recommandée", "recommandés", "certifié", "certifiée",
    "testé", "testée", "testés", "cliniquement", "approuvé", "approuvée",
    "conseil", "conseils", "étude", "recherche",
]

_LONGTAIL_SIGNALS: list[str] = [
    # Vetements chien
    "pour chien", "chiens", "manteau pour chien", "pull pour chien",
    "harnais pour chien", "taille chien", "morphologie",
    # Vetements chat
    "pour chat", "chats", "félin", "félins", "comportement félin",
    # Fontaines
    "fontaine", "abreuvoir", "hydratation", "eau filtrée", "filtre",
    "sans fil", "silencieux", "silencieuse", "capacité",
    "rein", "urinaire", "santé rénale",
    # Accessoires
    "griffoir", "griffer", "griffes", "arbre à chat", "bol surélevé",
    "digestion", "antidérapant",
]

# ── Category → relevant signal subsets ────────────────────────────────────

_CATEGORY_SIGNALS: dict[str, list[str]] = {
    "vetements_chien": [
        "pour chien", "chiens", "harnais", "manteau pour chien", "pull pour chien",
        "taille chien", "morphologie", "made in france", "artisan", "couturière",
        "confectionné", "laine d'alpaga", "cachemire", "soie naturelle",
        "cuir véritable", "confort", "liberté de mouvement", "respirant",
        "durable", "élégant", "premium",
    ],
    "vetements_chat": [
        "pour chat", "chats", "félin", "comportement félin", "non-restrictif",
        "made in france", "artisan", "couturière", "laine d'alpaga", "soie naturelle",
        "confort", "liberté de mouvement", "respirant", "hypoallergénique",
        "élégant", "premium",
    ],
    "fontaines": [
        "fontaine", "abreuvoir", "hydratation", "eau filtrée", "filtre",
        "sans fil", "silencieux", "silencieuse", "capacité", "rein",
        "urinaire", "santé rénale", "vétérinaire", "recommandé",
        "inox", "alimentaire", "sans bpa", "durable", "design",
    ],
    "filtres": [
        "filtre", "eau filtrée", "charbon actif", "calcaire", "impuretés",
        "hygiène", "remplacement", "compatible", "alimentaire",
        "certifié", "garantie",
    ],
    "accessoires": [
        "design", "élégant", "premium", "raffiné", "ergonomique",
        "posture naturelle", "confort", "céramique", "inox", "sans bpa",
        "alimentaire", "durable", "résistant", "lavable", "made in france",
        "félin", "félins", "digestion", "antidérapant",
    ],
}


def _normalize(text: str) -> str:
    return text.lower()


def _score_signals(text: str, signals: list[str]) -> tuple[int, int, list[str]]:
    """Return (matches, total, missing_list) for a set of signals."""
    norm = _normalize(text)
    found = [s for s in signals if s in norm]
    missing = [s for s in signals if s not in norm]
    return len(found), len(signals), missing


def analyze_product(product: dict[str, Any], cfg=None) -> dict[str, Any]:
    """Score a single product description across all signal categories."""
    _cfg = cfg or get_config()
    handle = product.get("handle", "")
    title = product.get("title", "")
    description = (product.get("description") or "").strip()
    text = f"{title} {description}"

    category = _cfg.category_for_handle(handle)
    category_signals = _CATEGORY_SIGNALS.get(category, _CATEGORY_SIGNALS["accessoires"])

    prem_found, prem_total, prem_missing = _score_signals(text, _PREMIUM_SIGNALS)
    eeat_found, eeat_total, eeat_missing = _score_signals(text, _EEAT_SIGNALS)
    lt_found, lt_total, lt_missing = _score_signals(text, _LONGTAIL_SIGNALS)
    cat_found, cat_total, cat_missing = _score_signals(text, category_signals)

    # Weighted global score: category coverage 40%, premium 30%, longtail 20%, eeat 10%
    global_score = round(
        0.40 * (cat_found / max(cat_total, 1))
        + 0.30 * (prem_found / max(prem_total, 1))
        + 0.20 * (lt_found / max(lt_total, 1))
        + 0.10 * (eeat_found / max(eeat_total, 1)),
        3,
    )

    return {
        "handle": handle,
        "title": title,
        "category": category,
        "description_length": len(description.split()),
        "premium_score": round(prem_found / max(prem_total, 1), 2),
        "eeat_score": round(eeat_found / max(eeat_total, 1), 2),
        "longtail_score": round(lt_found / max(lt_total, 1), 2),
        "category_score": round(cat_found / max(cat_total, 1), 2),
        "global_score": global_score,
        "top_missing_premium": prem_missing[:5],
        "top_missing_eeat": eeat_missing[:3],
        "top_missing_longtail": lt_missing[:5],
        "top_missing_category": cat_missing[:6],
    }


def load_products(snapshot_path: str) -> list[dict[str, Any]]:
    with open(snapshot_path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        p for p in data.get("products", [])
        if not p["title"].startswith("Pet ")
        and p["title"] != "Le Harnais Haute Couture (test)"
    ]


def load_keywords(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_markdown(results: list[dict[str, Any]], date: str) -> str:
    """Render semantic analysis as a Markdown report."""
    avg_global = round(sum(r["global_score"] for r in results) / max(len(results), 1), 3)
    avg_premium = round(sum(r["premium_score"] for r in results) / max(len(results), 1), 2)
    avg_eeat = round(sum(r["eeat_score"] for r in results) / max(len(results), 1), 2)

    _site = get_config().domain
    lines = [
        f"# Analyse Sémantique Produits — {_site} — {date}",
        "",
        "## Résumé",
        "",
        "| Métrique | Score moyen |",
        "|---|---|",
        f"| Score global pondéré | **{avg_global:.0%}** |",
        f"| Couverture vocabulaire premium | {avg_premium:.0%} |",
        f"| Signaux E-E-A-T | {avg_eeat:.0%} |",
        "",
        "> Benchmark concurrent : Miacara ~65%, Zooplus ~55%, Wanimo ~50%",
        "",
        "---",
        "",
        "## Scores par produit",
        "",
        "| Produit | Catégorie | Global | Premium | E-E-A-T | Longue traîne | Mots |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in sorted(results, key=lambda x: -x["global_score"]):
        lines.append(
            f"| {r['title'][:35]} | `{r['category']}` "
            f"| **{r['global_score']:.0%}** "
            f"| {r['premium_score']:.0%} "
            f"| {r['eeat_score']:.0%} "
            f"| {r['longtail_score']:.0%} "
            f"| {r['description_length']} |"
        )

    lines += ["", "---", "", "## Lacunes prioritaires par produit", ""]

    for r in sorted(results, key=lambda x: x["global_score"]):
        if r["global_score"] >= 0.6:
            continue  # Only show products needing work
        lines += [
            f"### {r['title']} — score {r['global_score']:.0%}",
            "",
            "**Termes premium manquants :**",
        ]
        for t in r["top_missing_premium"][:4]:
            lines.append(f"- `{t}`")
        lines += ["", "**Signaux E-E-A-T manquants :**"]
        for t in r["top_missing_eeat"]:
            lines.append(f"- `{t}`")
        lines += ["", "**Mots-clés longue traîne manquants :**"]
        for t in r["top_missing_category"][:5]:
            lines.append(f"- `{t}`")
        lines.append("")

    lines += [
        "---",
        "",
        "## Recommandations globales",
        "",
        "1. **E-E-A-T critique** — ajouter `vétérinaire`, `recommandé`, `testé` dans toutes les descriptions fontaines/filtres",
        "2. **Made in France** — le mentionner explicitement dans chaque description vêtements",
        "3. **Longue traîne** — intégrer les termes de santé animale (`santé rénale`, `urinaire`, `digestion`) dans les produits concernés",
        "4. **Longueur** — viser 150+ mots par description (utiliser `rewrite_descriptions.py --apply`)",
        "",
        f"*Généré automatiquement par le pipeline SEO {get_config().domain}*",
    ]
    return "\n".join(lines)


@click.command()
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--keywords", default="config/keywords.yaml", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(snapshot: str, keywords: str, output_dir: str, tenant: str | None) -> None:
    """Score product descriptions against competitor vocabulary and keyword targets."""
    cfg = get_config(tenant)
    console.print("[bold cyan]► Semantic analysis vs competitor benchmark[/bold cyan]")

    products = load_products(snapshot)
    results = [analyze_product(p, cfg) for p in products]

    table = Table(title="Semantic Scores")
    table.add_column("Product", max_width=30)
    table.add_column("Global", justify="right")
    table.add_column("Premium", justify="right")
    table.add_column("E-E-A-T", justify="right")

    for r in sorted(results, key=lambda x: -x["global_score"]):
        color = "green" if r["global_score"] >= 0.5 else "yellow" if r["global_score"] >= 0.3 else "red"
        table.add_row(
            r["title"][:30],
            f"[{color}]{r['global_score']:.0%}[/{color}]",
            f"{r['premium_score']:.0%}",
            f"{r['eeat_score']:.0%}",
        )
    console.print(table)

    date = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "semantic_analysis.md"
    out_path.write_text(render_markdown(results, date), encoding="utf-8")
    console.print(f"  [green]✓[/green] Rapport → {out_path}")


if __name__ == "__main__":
    main()
