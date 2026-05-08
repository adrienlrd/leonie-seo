"""Generate meta title, description, and alt text suggestions from a Shopify snapshot."""

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from scripts._config import get_config

_OLD_BRAND = "Léonie de la Croix"

_ENGLISH_SIGNALS = {
    "for",
    "and",
    "with",
    "the",
    "pet",
    "dog",
    "cat",
    "in",
    "of",
    "keeping",
    "warm",
    "sensing",
    "dispensing",
    "stainless",
    "steel",
    "large",
    "capacity",
    "drinking",
    "machine",
    "windproof",
    "windbreaker",
}

console = Console()


def _is_english_name(title: str) -> bool:
    words = set(title.lower().split())
    return len(words & _ENGLISH_SIGNALS) >= 2


def _infer_animal(title: str, collection_titles: list[str]) -> str:
    text = " ".join([title] + collection_titles).lower()
    if any(w in text for w in ("chien", "dog", "canin")):
        return "chien"
    if any(w in text for w in ("chat", "cat", "félin", "felin")):
        return "chat"
    return "animal"


def suggest_meta_title(
    title: str,
    animal: str,
    existing: str | None = None,
    cfg=None,
) -> dict[str, Any]:
    """Suggest an SEO meta title (target 50-65 chars).

    Returns dict with keys: value, is_review_needed, reason.
    """
    _cfg = cfg or get_config()
    brand = _cfg.brand
    title_min = _cfg.seo_rules.title_min_chars
    title_max = _cfg.seo_rules.title_max_chars

    if existing and existing.strip():
        e = existing.strip().replace(_OLD_BRAND, brand)
        in_range = title_min <= len(e) <= title_max
        return {
            "value": e,
            "is_review_needed": not in_range,
            "reason": "already set"
            if in_range
            else f"existant hors plage ({len(e)} chars) — vérifier",
        }

    if _is_english_name(title):
        return {
            "value": None,
            "is_review_needed": True,
            "reason": "nom en anglais — traduire avant publication",
        }

    base = f"{title} | {brand}"

    if title_min <= len(base) <= title_max:
        return {"value": base, "is_review_needed": False, "reason": "ok"}

    if len(base) < title_min:
        # Only add animal qualifier if that word isn't already in the title
        if animal != "animal" and animal.lower() not in title.lower():
            qualifier = f"Pour {animal.title()}"
        else:
            qualifier = "Premium"
        candidate = f"{title} {qualifier} | {brand}"
        if len(candidate) <= title_max:
            in_range = len(candidate) >= title_min
            return {
                "value": candidate,
                "is_review_needed": not in_range,
                "reason": "étendu" if in_range else f"court ({len(candidate)} chars) — compléter",
            }
        # qualifier made it too long, keep base
        return {
            "value": base,
            "is_review_needed": len(base) < title_min,
            "reason": f"court ({len(base)} chars) — compléter"
            if len(base) < title_min
            else "court mais acceptable",
        }

    # Too long: truncate title to fit
    max_title_len = title_max - len(f" | {brand}")
    truncated = title[:max_title_len].rstrip(" —,")
    return {
        "value": f"{truncated} | {brand}",
        "is_review_needed": True,
        "reason": f"tronqué ({len(title)} → {max_title_len} chars) — vérifier",
    }


def suggest_meta_description(
    title: str,
    animal: str,
    existing: str | None = None,
    cfg=None,
) -> dict[str, Any]:
    """Suggest an SEO meta description (target 120-155 chars).

    Returns dict with keys: value, is_review_needed, reason.
    """
    _cfg = cfg or get_config()
    brand = _cfg.brand
    desc_min = _cfg.seo_rules.description_min_chars
    desc_max = _cfg.seo_rules.description_max_chars

    if existing and len(existing.strip()) >= desc_min:
        desc = existing.strip()
        if len(desc) > desc_max:
            desc = desc[: desc_max - 3].rstrip() + "..."
            return {"value": desc, "is_review_needed": True, "reason": "trop longue — tronquée"}
        return {"value": desc, "is_review_needed": False, "reason": "already set"}

    if _is_english_name(title):
        return {
            "value": None,
            "is_review_needed": True,
            "reason": "nom en anglais — rédiger manuellement",
        }

    animal_label = {"chien": "votre chien", "chat": "votre chat"}.get(animal, "votre animal")

    templates = [
        (
            f"Découvrez {title} par {brand} — accessoire premium pour {animal_label}. "
            f"Fabrication soignée, design élégant. Livraison rapide en France."
        ),
        (
            f"{title} — l'accessoire premium pour {animal_label} signé {brand}. "
            f"Qualité artisanale et design élégant. Livraison rapide en France."
        ),
        (
            f"L'accessoire premium pour {animal_label} : {title} par {brand}. "
            f"Design élégant, fabrication soignée. Livraison rapide en France."
        ),
    ]

    for tpl in templates:
        if desc_min <= len(tpl) <= desc_max:
            return {"value": tpl, "is_review_needed": False, "reason": "généré"}

    # Fallback: use shortest template, truncate or flag
    desc = min(templates, key=len)
    if len(desc) < desc_min:
        return {
            "value": desc,
            "is_review_needed": True,
            "reason": f"court ({len(desc)} chars) — compléter",
        }
    desc = desc[: desc_max - 3].rstrip() + "..."
    return {"value": desc, "is_review_needed": True, "reason": "tronqué — vérifier"}


def suggest_alt_text(product_title: str, image_index: int = 0, cfg=None) -> str:
    """Suggest alt text for a product image (max 125 chars)."""
    brand = (cfg or get_config()).brand
    suffix = f" | {brand}"
    if image_index > 0:
        suffix = f" — vue {image_index + 1} | {brand}"
    max_title = 125 - len(suffix)
    return f"{product_title[:max_title].rstrip()}{suffix}"


def build_meta_suggestions(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    cfg=None,
) -> list[dict[str, Any]]:
    """Build the full list of meta update suggestions for products and collections."""
    _cfg = cfg or get_config()
    suggestions: list[dict[str, Any]] = []

    for p in products:
        col_titles = [e["node"]["title"] for e in (p.get("collections") or {}).get("edges", [])]
        animal = _infer_animal(p["title"], col_titles)
        existing_seo = p.get("seo") or {}

        title_sug = suggest_meta_title(p["title"], animal, existing_seo.get("title"), _cfg)
        desc_sug = suggest_meta_description(p["title"], animal, existing_seo.get("description"), _cfg)

        if title_sug["value"] is None and desc_sug["value"] is None:
            continue  # nothing actionable (e.g. English name)

        suggestions.append(
            {
                "id": p["id"],
                "resource_type": "product",
                "name": p["title"],
                "old_title": existing_seo.get("title"),
                "new_title": title_sug["value"],
                "title_review": title_sug["is_review_needed"],
                "title_reason": title_sug["reason"],
                "old_description": existing_seo.get("description"),
                "new_description": desc_sug["value"],
                "description_review": desc_sug["is_review_needed"],
                "description_reason": desc_sug["reason"],
            }
        )

    _SYSTEM_COLLECTIONS = {"home page"}
    for c in collections:
        if c["title"].lower() in _SYSTEM_COLLECTIONS:
            continue
        animal = _infer_animal(c["title"], [])
        existing_seo = c.get("seo") or {}

        title_sug = suggest_meta_title(c["title"], animal, existing_seo.get("title"), _cfg)
        desc_sug = suggest_meta_description(c["title"], animal, existing_seo.get("description"), _cfg)

        if title_sug["value"] is None and desc_sug["value"] is None:
            continue

        suggestions.append(
            {
                "id": c["id"],
                "resource_type": "collection",
                "name": c["title"],
                "old_title": existing_seo.get("title"),
                "new_title": title_sug["value"],
                "title_review": title_sug["is_review_needed"],
                "title_reason": title_sug["reason"],
                "old_description": existing_seo.get("description"),
                "new_description": desc_sug["value"],
                "description_review": desc_sug["is_review_needed"],
                "description_reason": desc_sug["reason"],
            }
        )

    return suggestions


def build_alt_suggestions(products: list[dict[str, Any]], cfg=None) -> list[dict[str, Any]]:
    """Build alt text suggestions for images that have no alt text."""
    _cfg = cfg or get_config()
    suggestions: list[dict[str, Any]] = []

    for p in products:
        images = (p.get("images") or {}).get("edges", [])
        img_idx = 0
        for img_edge in images:
            img = img_edge["node"]
            alt = img.get("altText")
            if alt is None or alt.strip() == "":
                suggestions.append(
                    {
                        "product_id": p["id"],
                        "product_name": p["title"],
                        "image_id": img["id"],
                        "image_url": img.get("url", ""),
                        "old_alt": alt,
                        "new_alt": suggest_alt_text(p["title"], img_idx, _cfg),
                    }
                )
                img_idx += 1

    return suggestions


def _review_marker(needs_review: bool) -> str:
    return "[yellow]⚠[/yellow]" if needs_review else "[green]✓[/green]"


@click.command()
@click.option("--data", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option("--meta-output", default="data/raw/meta_suggestions.json", show_default=True)
@click.option("--alt-output", default="data/raw/alt_suggestions.json", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(data: str, meta_output: str, alt_output: str, tenant: str | None) -> None:
    """Generate meta title, description, and alt text suggestions.

    Reads the Shopify snapshot and writes two JSON files:
    - meta_suggestions.json → feed into update_meta.py
    - alt_suggestions.json  → feed into update_alt_text.py
    """
    cfg = get_config(tenant)
    console.print("[bold cyan]► Generating SEO suggestions[/bold cyan]")

    with open(data, encoding="utf-8") as f:
        snapshot = json.load(f)

    products: list[dict[str, Any]] = snapshot.get("products", [])
    collections: list[dict[str, Any]] = snapshot.get("collections", [])

    # --- Meta suggestions ---
    meta = build_meta_suggestions(products, collections, cfg)

    table = Table(title="Meta Suggestions", show_lines=True)
    table.add_column("", width=2)
    table.add_column("Ressource", style="cyan", max_width=30)
    table.add_column("Type", width=10)
    table.add_column("Meta title proposé", max_width=55)
    table.add_column("Chars", width=6)

    needs_review_count = 0
    for s in meta:
        marker = _review_marker(s["title_review"] or s["description_review"])
        if s["title_review"] or s["description_review"]:
            needs_review_count += 1
        title_val = s["new_title"] or "[red]— à rédiger[/red]"
        chars = str(len(s["new_title"])) if s["new_title"] else "—"
        table.add_row(marker, s["name"], s["resource_type"], title_val, chars)

    console.print(table)
    console.print(
        f"\n  [green]✓[/green] {len(meta)} suggestions générées "
        f"({needs_review_count} à vérifier [yellow]⚠[/yellow])\n"
    )

    Path(meta_output).parent.mkdir(parents=True, exist_ok=True)
    Path(meta_output).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"  [green]✓[/green] Meta suggestions → {meta_output}")

    # --- Alt text suggestions ---
    alt = build_alt_suggestions(products, cfg)

    if alt:
        alt_table = Table(title="Alt Text Suggestions", show_lines=True)
        alt_table.add_column("Produit", style="cyan", max_width=30)
        alt_table.add_column("Alt text proposé", max_width=60)
        alt_table.add_column("Chars", width=6)
        for s in alt:
            alt_table.add_row(s["product_name"], s["new_alt"], str(len(s["new_alt"])))
        console.print(alt_table)

    Path(alt_output).parent.mkdir(parents=True, exist_ok=True)
    Path(alt_output).write_text(json.dumps(alt, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"  [green]✓[/green] Alt suggestions   → {alt_output}")
    console.print(
        "\n[dim]Prochaines étapes :[/dim]\n"
        "  [dim]python -m scripts.apply.update_meta --updates data/raw/meta_suggestions.json --dry-run[/dim]\n"
        "  [dim]python -m scripts.apply.update_alt_text --dry-run[/dim]"
    )


if __name__ == "__main__":
    main()
