"""Detect internal linking opportunities between blog topics and product pages."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import pandas as pd
import yaml
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

_STOP_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "pour", "par",
    "en", "et", "ou", "à", "au", "aux", "ce", "cet", "cette", "ces",
    "mon", "ton", "son", "notre", "votre", "leur", "dans", "sur", "avec",
    "comment", "quel", "quelle", "quels", "meilleur", "bien", "choisir",
}

# Keyword category → product handles eligible for internal links
_CATEGORY_TO_HANDLES: dict[str, list[str]] = {
    "vetements_chien": [
        "le-pardessus-pour-chien",
        "le-harnais-haute-couture",
        "le-harnais-tout-en-un",
        "le-tour-de-cou-pour-chien",
        "le-pull-le-leonie",
    ],
    "vetements_chat": [
        "le-pardessus-pour-chat",
        "le-tour-de-cou-pour-chat",
    ],
    "fontaines_abreuvoirs": [
        "labreuvoir",
        "fontaine-smart-cordless",
        "distributeur-pet-feeder",
    ],
    "accessoires_maison": [
        "griffoir-dimitrios",
        "arbre-a-chat-boho",
        "bol-felin-raffine",
    ],
    "informational": [
        "labreuvoir",
        "fontaine-smart-cordless",
        "le-pardessus-pour-chien",
        "le-harnais-haute-couture",
        "griffoir-dimitrios",
    ],
}

# Keyword category → collection handles eligible for internal links
_CATEGORY_TO_COLLECTIONS: dict[str, list[str]] = {
    "vetements_chien": ["chien"],
    "vetements_chat": ["chat"],
    "fontaines_abreuvoirs": ["frontpage"],
    "accessoires_maison": ["accessoire"],
    "informational": ["chien", "chat"],
}

_BASE_URL = "https://www.leoniedelacroix.com"


def _tokenize(text: str) -> set[str]:
    """Return significant tokens from a string."""
    tokens = re.findall(r"[a-zàâäéèêëïîôùûüç]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


def load_keywords(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_products(snapshot_path: str) -> list[dict[str, Any]]:
    with open(snapshot_path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        p for p in data.get("products", [])
        if not p["title"].startswith("Pet ") and p["title"] != "Le Harnais Haute Couture (test)"
    ]


def load_collections(snapshot_path: str) -> list[dict[str, Any]]:
    with open(snapshot_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("collections", [])


def load_gsc(path: str) -> set[str]:
    """Return set of product/collection URLs that have GSC impressions."""
    p = Path(path)
    if not p.exists():
        return set()
    df = pd.read_csv(p)
    return set(df[df["impressions"] > 0]["url"].tolist())


def _anchor_from_keyword(keyword: str, product_title: str) -> str:
    """Build a natural anchor text from keyword + product title."""
    kw_tokens = _tokenize(keyword)
    title_tokens = _tokenize(product_title)
    shared = kw_tokens & title_tokens
    if shared:
        return " ".join(sorted(shared)[:4])
    return product_title.lower()


def detect_opportunities(
    keywords: dict[str, list[str]],
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match each keyword to target product/collection pages for internal linking."""
    product_map = {p["handle"]: p for p in products}
    collection_map = {c["handle"]: c for c in collections}
    opportunities: list[dict[str, Any]] = []

    for category, kw_list in keywords.items():
        if category == "brand":
            continue
        target_handles = _CATEGORY_TO_HANDLES.get(category, [])
        target_colls = _CATEGORY_TO_COLLECTIONS.get(category, [])

        for keyword in kw_list:
            kw_tokens = _tokenize(keyword)

            # Match products
            for handle in target_handles:
                product = product_map.get(handle)
                if not product:
                    continue
                title_tokens = _tokenize(product["title"])
                overlap = len(kw_tokens & title_tokens)
                score = round(overlap / max(len(kw_tokens), 1), 2)
                anchor = _anchor_from_keyword(keyword, product["title"])
                opportunities.append({
                    "source_keyword": keyword,
                    "source_category": category,
                    "source_article_h1": keyword.capitalize(),
                    "target_type": "product",
                    "target_title": product["title"],
                    "target_url": f"{_BASE_URL}/products/{handle}",
                    "anchor_text": anchor,
                    "relevance_score": score,
                })

            # Match collections
            for chandle in target_colls:
                coll = collection_map.get(chandle)
                if not coll:
                    continue
                anchor = _anchor_from_keyword(keyword, coll.get("title", chandle))
                opportunities.append({
                    "source_keyword": keyword,
                    "source_category": category,
                    "source_article_h1": keyword.capitalize(),
                    "target_type": "collection",
                    "target_title": coll.get("title", chandle),
                    "target_url": f"{_BASE_URL}/collections/{chandle}",
                    "anchor_text": anchor,
                    "relevance_score": 0.1,
                })

    # Sort by score desc, deduplicate (keyword, target_url) pairs
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for opp in sorted(opportunities, key=lambda x: -x["relevance_score"]):
        key = (opp["source_keyword"], opp["target_url"])
        if key not in seen:
            seen.add(key)
            unique.append(opp)

    return unique


def detect_orphans(
    products: list[dict[str, Any]],
    gsc_urls: set[str],
) -> list[dict[str, Any]]:
    """Return product pages with zero GSC impressions — need incoming links."""
    orphans = []
    for p in products:
        handle = p.get("handle", "")
        url = f"{_BASE_URL}/products/{handle}"
        if url not in gsc_urls:
            orphans.append({"title": p["title"], "url": url, "handle": handle})
    return orphans


def render_markdown(
    opportunities: list[dict[str, Any]],
    orphans: list[dict[str, Any]],
    date: str,
) -> str:
    """Render linking opportunities as a Markdown report."""
    lines = [
        f"# Maillage Interne — leoniedelacroix.com — {date}",
        "",
        f"**{len(opportunities)} opportunités de liens** · "
        f"**{len(orphans)} pages orphelines** (zéro trafic GSC)",
        "",
        "---",
        "",
        "## Opportunités par article blog → page produit/collection",
        "",
        "| Article source | Page cible | Ancre suggérée | Score |",
        "|---|---|---|---|",
    ]
    for opp in opportunities[:40]:
        source = opp["source_article_h1"][:50]
        target = opp["target_title"][:40]
        anchor = f"`{opp['anchor_text']}`"
        score = opp["relevance_score"]
        lines.append(f"| {source} | [{target}]({opp['target_url']}) | {anchor} | {score} |")

    lines += [
        "",
        "---",
        "",
        "## Pages orphelines — priorité à mailler",
        "",
        "*Ces pages n'apparaissent pas dans Google Search Console. "
        "Créer des liens internes vers elles depuis les articles de blog "
        "et les pages de collection est la première action à prendre.*",
        "",
    ]
    for orphan in orphans:
        lines.append(f"- [{orphan['title']}]({orphan['url']})")

    lines += [
        "",
        "---",
        "",
        "## Plan d'action recommandé",
        "",
        "1. **Rédiger les 6 articles informationnels** (briefs dans `blog_briefs.md`)",
        "2. **Insérer les liens** selon le tableau ci-dessus en priorité score ≥ 0.2",
        "3. **Soumettre le sitemap** dans Google Search Console après publication",
        "4. **Relancer l'audit** (`python -m scripts.audit.crawl_shopify`) pour vérifier l'indexation",
        "",
        "---",
        "",
        "*Généré automatiquement par le pipeline SEO leoniedelacroix.com*",
    ]
    return "\n".join(lines)


@click.command()
@click.option("--keywords", default="config/keywords.yaml", show_default=True)
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--gsc", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
def main(keywords: str, snapshot: str, gsc: str, output_dir: str) -> None:
    """Detect internal linking opportunities between blog topics and product pages."""
    console.print("[bold cyan]► Detecting internal linking opportunities[/bold cyan]")

    kw_data = load_keywords(keywords)
    products = load_products(snapshot)
    collections = load_collections(snapshot)
    gsc_urls = load_gsc(gsc)

    opportunities = detect_opportunities(kw_data, products, collections)
    orphans = detect_orphans(products, gsc_urls)

    console.print(f"  {len(opportunities)} opportunités · {len(orphans)} pages orphelines")

    date = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "internal_links.md"
    out_path.write_text(render_markdown(opportunities, orphans, date), encoding="utf-8")
    console.print(f"  [green]✓[/green] Rapport → {out_path}")


if __name__ == "__main__":
    main()
