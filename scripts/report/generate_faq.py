"""Generate structured FAQ content per product category with JSON-LD schema."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console

from scripts._config import get_config, load_niche

load_dotenv()

console = Console()


def load_keywords(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_faq(category: str, niche=None) -> list[dict[str, str]]:
    """Return the FAQ list for a given category from niche config."""
    _niche = niche or load_niche(get_config().niche)
    return _niche.faq_templates.get(category, [])


def build_json_ld(faq: list[dict[str, str]]) -> dict[str, Any]:
    """Build a schema.org/FAQPage JSON-LD object."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["a"],
                },
            }
            for item in faq
        ],
    }


def render_markdown(
    faqs_by_category: dict[str, list[dict[str, str]]],
    date: str,
    cfg=None,
) -> str:
    """Render all FAQs as a Markdown document."""
    _cfg = cfg or get_config()
    _site = _cfg.domain
    total = sum(len(v) for v in faqs_by_category.values())
    lines = [
        f"# FAQ Structurée — {_site} — {date}",
        "",
        f"**{total} questions** réparties sur {len(faqs_by_category)} catégories",
        "",
        "> Ces FAQ sont prêtes à intégrer sur les pages produits et articles de blog.",
        "> Le JSON-LD associé est disponible dans `data/raw/faq_suggestions.json`",
        "> pour injection via metafield Shopify ou theme Liquid.",
        "",
        "---",
        "",
    ]

    category_labels = _cfg.category_labels

    for category, faq in faqs_by_category.items():
        label = category_labels.get(category, category)
        lines += [f"## {label}", ""]
        for item in faq:
            lines += [
                f"**Q : {item['q']}**",
                "",
                item["a"],
                "",
            ]
        lines += ["---", ""]

    lines.append(f"*Généré automatiquement par le pipeline SEO {_site}*")
    return "\n".join(lines)


@click.command()
@click.option("--keywords", default="config/keywords.yaml", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--json-output", default="data/raw/faq_suggestions.json", show_default=True)
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(keywords: str, output_dir: str, json_output: str, tenant: str | None) -> None:
    """Generate structured FAQ content per product category with JSON-LD schema."""
    cfg = get_config(tenant)
    niche = load_niche(cfg.niche)
    console.print("[bold cyan]► Generating structured FAQ[/bold cyan]")

    categories = list(niche.faq_templates.keys())
    faqs_by_category: dict[str, list[dict[str, str]]] = {}
    json_output_data: dict[str, Any] = {}

    for category in categories:
        faq = generate_faq(category, niche)
        faqs_by_category[category] = faq
        json_output_data[category] = {
            "faq": faq,
            "json_ld": build_json_ld(faq),
        }
        console.print(f"  {category}: {len(faq)} questions")

    # Save JSON-LD
    Path(json_output).parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(json_output_data, f, ensure_ascii=False, indent=2)

    # Save Markdown report
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "faq_suggestions.md"
    out_path.write_text(render_markdown(faqs_by_category, date), encoding="utf-8")

    total = sum(len(v) for v in faqs_by_category.values())
    console.print(f"  [green]✓[/green] {total} Q/R → {out_path}")
    console.print(f"  [green]✓[/green] JSON-LD → {json_output}")


if __name__ == "__main__":
    main()
