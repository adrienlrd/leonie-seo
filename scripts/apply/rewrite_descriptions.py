"""Generate SEO-optimised long-tail product descriptions and push to Shopify."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import requests
from dotenv import load_dotenv
from rich.console import Console

from scripts._paths import DB_PATH as _DB_PATH

load_dotenv()

console = Console()

_SHOPIFY_API_VERSION = "2025-01"

# ── Product classification ─────────────────────────────────────────────────

_CATEGORY_SIGNALS: dict[str, list[str]] = {
    "filtres": ["filtre", "filtres", "pompe", "pump"],
    "fontaines": ["abreuvoir", "fontaine", "drinking machine", "distributeur"],
    "vetements_chien": [
        "pardessus pour chien",
        "tour de cou pour chien",
        "pull",
        "harnais",
        "windbreaker",
    ],
    "vetements_chat": ["pardessus pour chat", "tour de cou pour chat"],
    "accessoires": ["bol", "griffoir", "arbre", "ensemble", "clawcount", "félin"],
}

# ── Rich description templates per category ────────────────────────────────
# Each template has: intro, features_hook, eeat, cta
# {title}, {existing} placeholders are filled at render time

_TEMPLATES: dict[str, dict[str, str]] = {
    "vetements_chien": {
        "intro": (
            "{title} est une pièce unique conçue pour les chiens qui méritent le meilleur. "
            "Fabriquée à la main par nos couturières expertes en France, elle allie confort, "
            "durabilité et élégance dans un style résolument premium."
        ),
        "features": (
            "Sa conception soignée garantit une liberté de mouvement totale, sans gêner les articulations "
            "ni irriter la peau. Les matières sélectionnées — laine d'alpaga, soie naturelle ou cuir "
            "pleine fleur — offrent une régulation thermique naturelle, idéale pour les promenades hivernales "
            "comme pour les sorties en ville."
        ),
        "eeat": (
            "Chez Léonie Delacroix, chaque accessoire pour chien est pensé avec la même exigence qu'une pièce "
            "de mode haut de gamme. Nos modèles sont testés sur des chiens de différentes morphologies pour "
            "garantir un ajustement parfait et un confort durable."
        ),
        "cta": (
            "Disponible en plusieurs tailles. Livraison soignée en France métropolitaine. "
            "Satisfait ou remboursé sous 14 jours."
        ),
    },
    "vetements_chat": {
        "intro": (
            "{title} est pensé pour les chats qui acceptent les vêtements sans contrainte. "
            "Doux contre la peau, léger et non-restrictif, il respecte la liberté de mouvement "
            "et le bien-être de votre compagnon félin."
        ),
        "features": (
            "Confectionné dans des matières naturelles choisies pour leur douceur — laine d'alpaga, "
            "jersey de soie ou coton biologique — il s'adapte aux morphologies félines sans gêner les "
            "déplacements, les sauts ni le toilettage. La coupe est étudiée pour éviter tout stress."
        ),
        "eeat": (
            "Léonie Delacroix travaille avec des comportementalistes félins pour s'assurer que chaque "
            "modèle respecte les besoins sensoriels du chat. Résultat : des vêtements que votre chat "
            "peut vraiment porter confortablement."
        ),
        "cta": (
            "Guide des tailles disponible pour trouver le modèle idéal. "
            "Livraison en France — satisfait ou remboursé sous 14 jours."
        ),
    },
    "fontaines": {
        "intro": (
            "{title} est la solution idéale pour encourager votre chat à boire suffisamment au quotidien. "
            "Les chats sont naturellement attirés par l'eau en mouvement — une fontaine filtrante peut "
            "augmenter leur consommation d'eau de 50 %, réduisant ainsi les risques d'insuffisance rénale."
        ),
        "features": (
            "Équipée d'un système de filtration multi-couches, elle élimine les impuretés, les poils et "
            "les résidus calcaires pour offrir une eau toujours fraîche et propre. Le moteur ultra-silencieux "
            "ne perturbe pas le sommeil de votre animal ni le vôtre. Sans fil pour une installation "
            "flexible partout dans votre intérieur."
        ),
        "eeat": (
            "Recommandée par des vétérinaires français pour les chats sujets aux infections urinaires ou "
            "aux calculs rénaux. Un investissement pour la santé long terme de votre compagnon."
        ),
        "cta": (
            "Filtres de remplacement disponibles dans notre boutique. "
            "Livraison rapide en France — garantie constructeur incluse."
        ),
    },
    "filtres": {
        "intro": (
            "{title} est conçu pour maintenir la qualité de l'eau de votre fontaine ou abreuvoir "
            "au niveau optimal, semaine après semaine."
        ),
        "features": (
            "Chaque filtre combine charbon actif, mousse filtrante et résine échangeuse d'ions pour "
            "retenir les impuretés, éliminer les odeurs et réduire le calcaire. À changer toutes les "
            "2 à 4 semaines selon la dureté de votre eau et le nombre d'animaux. Compatible avec "
            "l'ensemble des fontaines Léonie Delacroix."
        ),
        "eeat": (
            "Un filtre propre, c'est une eau saine — et un chat qui boit davantage. "
            "Nos filtres sont fabriqués selon les normes européennes de qualité alimentaire."
        ),
        "cta": (
            "Disponible à l'unité ou en pack économique. "
            "Livraison en France — abonnement mensuel disponible pour ne jamais manquer de filtres."
        ),
    },
    "accessoires": {
        "intro": (
            "{title} allie design contemporain et fonctionnalité pensée pour le bien-être de votre animal. "
            "Conçu pour s'intégrer harmonieusement à votre intérieur, il reflète l'exigence de la marque "
            "Léonie Delacroix : des accessoires premium pour animaux qui ont du style."
        ),
        "features": (
            "Fabriqué à partir de matériaux durables et sûrs — céramique de qualité, inox alimentaire, "
            "bois naturel ou cuir végétal — il est pensé pour durer et résister à un usage quotidien "
            "intensif. Sa conception ergonomique respecte la posture naturelle de votre animal "
            "pour un confort optimal à chaque utilisation."
        ),
        "eeat": (
            "Chaque accessoire Léonie Delacroix est sélectionné ou conçu en collaboration avec des "
            "spécialistes du comportement animal. Parce que le bien-être de votre compagnon "
            "passe aussi par son environnement quotidien."
        ),
        "cta": (
            "Livraison soignée en France métropolitaine. Satisfait ou remboursé sous 14 jours."
        ),
    },
}


def classify_product(title: str, description: str) -> str:
    """Return the product category — title takes priority, description as fallback."""
    title_lower = title.lower()
    for category, signals in _CATEGORY_SIGNALS.items():
        if any(s in title_lower for s in signals):
            return category
    desc_lower = description.lower()
    for category, signals in _CATEGORY_SIGNALS.items():
        if any(s in desc_lower for s in signals):
            return category
    return "accessoires"


def strip_html(html: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", html or "").strip()


def build_description(title: str, category: str) -> str:
    """Build a rich 150-250 word SEO description for a product."""
    tpl = _TEMPLATES.get(category, _TEMPLATES["accessoires"])
    parts = [
        tpl["intro"].format(title=title),
        tpl["features"],
        tpl["eeat"],
        tpl["cta"],
    ]
    return "\n\n".join(parts)


def load_products(snapshot_path: str) -> list[dict[str, Any]]:
    """Load products from Shopify snapshot JSON."""
    with open(snapshot_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [])


def _shopify_headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
    }


def _graphql_url(domain: str) -> str:
    return f"https://{domain}/admin/api/{_SHOPIFY_API_VERSION}/graphql.json"


class ShopifyUserError(Exception):
    pass


def push_description(
    product_id: str, description: str, endpoint: str, headers: dict[str, str]
) -> None:
    """Push a new body_html description to Shopify via productUpdate."""
    mutation = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product { id }
        userErrors { field message }
      }
    }
    """
    variables = {
        "input": {"id": product_id, "descriptionHtml": description.replace("\n\n", "<br><br>")}
    }
    resp = requests.post(
        endpoint, json={"query": mutation, "variables": variables}, headers=headers, timeout=30
    )
    resp.raise_for_status()
    body = resp.json()
    errors = body.get("data", {}).get("productUpdate", {}).get("userErrors", [])
    if errors:
        raise ShopifyUserError(str(errors))


def log_change(db_path: str, resource_id: str, old_val: str, new_val: str) -> None:
    """Log description rewrite to SQLite history."""
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seo_changes (applied_at, resource_type, resource_id, field, old_value, new_value, status) "
            "VALUES (?, 'product', ?, 'description', ?, ?, 'applied')",
            (datetime.now(UTC).isoformat(), resource_id, old_val, new_val),
        )
        con.commit()
    finally:
        con.close()


@click.command()
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--output", default="data/raw/description_suggestions.json", show_default=True)
@click.option("--dry-run/--apply", default=True, show_default=True)
def main(snapshot: str, output: str, dry_run: bool) -> None:
    """Generate and optionally push long-tail SEO descriptions for all products."""
    console.print("[bold cyan]► Rewriting product descriptions[/bold cyan]")

    products = load_products(snapshot)
    # Exclude accessory-only products with non-French titles
    products = [
        p
        for p in products
        if not p["title"].startswith("Pet ") and p["title"] != "Le Harnais Haute Couture (test)"
    ]

    suggestions: list[dict[str, Any]] = []
    for p in products:
        title = p["title"]
        existing = strip_html(p.get("description") or "")
        category = classify_product(title, existing)
        new_desc = build_description(title, category)
        word_count = len(new_desc.split())
        suggestions.append(
            {
                "id": p["id"],
                "handle": p.get("handle", ""),
                "title": title,
                "category": category,
                "old_description": existing,
                "new_description": new_desc,
                "word_count": word_count,
            }
        )
        console.print(f"  [dim]{title}[/dim] → {category} ({word_count} mots)")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(suggestions, f, ensure_ascii=False, indent=2)
    console.print(f"\n  [green]✓[/green] {len(suggestions)} suggestions → {output}")

    if dry_run:
        console.print("  [dim]Dry-run — utiliser --apply pour pousser vers Shopify[/dim]")
        return

    token = os.environ["SHOPIFY_ACCESS_TOKEN"]
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    endpoint = _graphql_url(domain)
    headers = _shopify_headers(token)

    pushed = 0
    for s in suggestions:
        try:
            push_description(s["id"], s["new_description"], endpoint, headers)
            log_change(_DB_PATH, s["id"], s["old_description"], s["new_description"])
            console.print(f"  [green]✓[/green] {s['title']}")
            pushed += 1
        except (ShopifyUserError, requests.RequestException) as exc:
            console.print(f"  [red]✗[/red] {s['title']}: {exc}")

    console.print(f"\n  [bold green]{pushed}/{len(suggestions)} descriptions poussées[/bold green]")


if __name__ == "__main__":
    main()
