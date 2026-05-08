"""Generate SEO blog brief outlines from keyword gaps and GSC opportunities."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console

from scripts._config import get_config, load_niche

load_dotenv()

console = Console()

# Product URLs for internal linking suggestions
_CATEGORY_TO_URLS: dict[str, list[str]] = {
    "vetements_chien": [
        "/products/le-pardessus-pour-chien",
        "/products/le-harnais-haute-couture",
        "/products/le-tour-de-cou-pour-chien",
        "/collections/chien",
    ],
    "vetements_chat": [
        "/products/le-tour-de-cou-pour-chat",
        "/collections/chat",
    ],
    "fontaines_abreuvoirs": [
        "/products/labreuvoir",
        "/products/fontaine-smart-cordless",
        "/collections/fontaines",
    ],
    "accessoires_maison": [
        "/products/griffoir-dimitrios",
        "/products/le-bol-felin-raffine",
        "/collections/accessoires",
    ],
    "informational": [
        "/collections/chien",
        "/collections/chat",
        "/products/labreuvoir",
        "/products/fontaine-smart-cordless",
    ],
}


def load_keywords(path: str) -> dict[str, list[str]]:
    """Load keywords.yaml and return category → keyword list."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_gaps(path: str) -> list[dict[str, Any]]:
    """Load longtail_gaps.json."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def select_candidates(
    keywords: dict[str, list[str]],
    gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select keywords worth a blog brief.

    Priority order:
    1. informational keywords (always good blog material)
    2. on_site keywords with 0 impressions (page exists, needs content support)
    Excludes brand queries.
    """
    candidates: list[dict[str, Any]] = []

    # 1. All informational keywords
    for kw in keywords.get("informational", []):
        candidates.append(
            {"keyword": kw, "category": "informational", "status": "planned", "impressions": 0}
        )

    # 2. on_site keywords with 0 impressions (sorted by opportunity_score desc)
    gap_map = {g["keyword"]: g for g in gaps if g["status"] in ("on_site", "gap")}
    for category, kw_list in keywords.items():
        if category in ("informational", "brand"):
            continue
        for kw in kw_list:
            if kw in gap_map and gap_map[kw].get("impressions", 0) == 0:
                candidates.append(
                    {
                        "keyword": kw,
                        "category": category,
                        "status": gap_map[kw]["status"],
                        "impressions": 0,
                        "opportunity_score": gap_map[kw].get("opportunity_score", 0),
                    }
                )

    # Deduplicate and limit to 10 briefs
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for c in candidates:
        if c["keyword"] not in seen:
            seen.add(c["keyword"])
            unique.append(c)

    return unique[:10]


def _h1_from_keyword(keyword: str, category: str) -> str:
    """Derive an SEO-friendly H1 from the keyword and category."""
    kw = keyword.capitalize()
    if category == "informational":
        return kw
    if category in ("vetements_chien", "vetements_chat"):
        return f"{kw} : guide complet pour bien choisir"
    if category == "fontaines_abreuvoirs":
        return f"{kw} : guide d'achat et conseils vétérinaires"
    return f"{kw} : notre sélection premium"


def _secondary_keywords(
    keyword: str, category: str, all_keywords: dict[str, list[str]]
) -> list[str]:
    """Return related keywords from the same category, excluding the primary one."""
    pool = all_keywords.get(category, [])
    return [k for k in pool if k != keyword][:4]


def generate_brief(
    candidate: dict[str, Any],
    all_keywords: dict[str, list[str]],
    niche=None,
) -> dict[str, Any]:
    """Build a complete brief dict for one keyword."""
    _niche = niche or load_niche(get_config().niche)
    kw = candidate["keyword"]
    category = candidate["category"]

    fallback = _niche.blog_templates.get("informational")
    template = _niche.blog_templates.get(category) or fallback

    return {
        "keyword": kw,
        "category": category,
        "intent": template.intent if template else "Informatif",
        "h1": _h1_from_keyword(kw, category),
        "h2s": template.h2s if template else [],
        "secondary_keywords": _secondary_keywords(kw, category, all_keywords),
        "target_length": template.target_length if template else "800–1 000 mots",
        "eeat_angle": template.eeat_angle if template else "",
        "internal_links": _CATEGORY_TO_URLS.get(category, []),
        "status": candidate.get("status", "planned"),
    }


def render_markdown(briefs: list[dict[str, Any]], date: str) -> str:
    """Render all briefs as a Markdown document."""
    _site = get_config().domain
    lines = [
        f"# Briefs Articles Blog — {_site} — {date}",
        "",
        f"**{len(briefs)} briefs générés** · Priorité : informationnels d'abord, puis pages catalogue sans trafic",
        "",
        "---",
        "",
    ]

    for i, b in enumerate(briefs, 1):
        lines += [
            f"## Brief #{i} — {b['keyword']}",
            "",
            "| Champ | Valeur |",
            "|---|---|",
            f"| Catégorie | `{b['category']}` |",
            f"| Intent | {b['intent']} |",
            f"| Longueur cible | {b['target_length']} |",
            f"| Statut GSC | {b['status']} |",
            "",
            "### H1 suggéré",
            f"> {b['h1']}",
            "",
            "### Structure H2",
        ]
        for h2 in b["h2s"]:
            lines.append(f"- {h2}")

        lines += [
            "",
            "### Mots-clés secondaires",
        ]
        for sk in b["secondary_keywords"]:
            lines.append(f"- `{sk}`")

        lines += [
            "",
            "### Angle E-E-A-T",
            b["eeat_angle"],
            "",
            "### Liens internes suggérés",
        ]
        for url in b["internal_links"]:
            lines.append(f"- `{url}`")

        lines += ["", "---", ""]

    lines.append(f"*Généré automatiquement par le pipeline SEO {get_config().domain}*")
    return "\n".join(lines)


@click.command()
@click.option("--keywords", default="config/keywords.yaml", show_default=True)
@click.option("--gaps", default="data/raw/longtail_gaps.json", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(keywords: str, gaps: str, output_dir: str, tenant: str | None) -> None:
    """Generate blog brief outlines from keyword gaps and GSC opportunities."""
    cfg = get_config(tenant)
    niche = load_niche(cfg.niche)
    console.print("[bold cyan]► Generating blog briefs[/bold cyan]")

    kw_data = load_keywords(keywords)
    gap_data = load_gaps(gaps)

    candidates = select_candidates(kw_data, gap_data)
    console.print(f"  {len(candidates)} candidats sélectionnés")

    briefs = [generate_brief(c, kw_data, niche) for c in candidates]

    date = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "blog_briefs.md"
    out_path.write_text(render_markdown(briefs, date), encoding="utf-8")

    console.print(f"  [green]✓[/green] {len(briefs)} briefs → {out_path}")


if __name__ == "__main__":
    main()
