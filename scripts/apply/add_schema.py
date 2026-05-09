"""Push JSON-LD Product structured data to Shopify via metafields. Dry-run by default."""

import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from typing import Any

import click
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from scripts._config import get_config
from scripts._paths import DB_PATH as _DB_PATH

load_dotenv()

console = Console()

_ENDPOINT_TMPL = "https://{domain}/admin/api/2025-01/graphql.json"

_METAFIELDS_SET = """
mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id namespace key value }
    userErrors { field message code }
  }
}
"""

_THEME_SNIPPET = """
  [bold cyan]── Theme integration (one-time manual edit) ──[/bold cyan]
  Add this snippet to your [yellow]product.liquid[/yellow] or [yellow]product.json[/yellow] theme file,
  just before the closing [yellow]</head>[/yellow] tag:

  [dim]{% if product.metafields.custom.json_ld %}
    <script type="application/ld+json">
      {{ product.metafields.custom.json_ld.value }}
    </script>
  {% endif %}[/dim]
"""


class ShopifyUserError(Exception):
    """Raised when Shopify returns userErrors in a mutation response."""


def _log_schema(product_id: str, json_ld_value: str) -> None:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "INSERT INTO seo_changes (applied_at, resource_type, resource_id, field, old_value, new_value, status)"
        " VALUES (?, 'product', ?, 'metafield.custom.json_ld', NULL, ?, 'applied')",
        (datetime.now(UTC).isoformat(), product_id, json_ld_value[:500]),
    )
    conn.commit()
    conn.close()


def _get_client() -> tuple[str, dict[str, str]]:
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    token = os.environ["SHOPIFY_ACCESS_TOKEN"]
    return _ENDPOINT_TMPL.format(domain=domain), {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }


def build_product_schema(product: dict[str, Any], cfg=None) -> dict[str, Any]:
    """Build a schema.org Product JSON-LD dict for a single Shopify product.

    Args:
        product: Raw product dict from Shopify snapshot (must have id, title, handle).
        cfg: Optional TenantConfig (defaults to TENANT_ID env var).

    Returns:
        JSON-LD dict ready to be serialized as application/ld+json.
    """
    _cfg = cfg or get_config()
    handle = product.get("handle", "")
    url = f"{_cfg.base_url}/products/{handle}"
    image_urls = [edge["node"]["url"] for edge in (product.get("images") or {}).get("edges", [])]

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.get("title", ""),
        "url": url,
        "brand": {"@type": "Brand", "name": _cfg.brand},
    }

    if desc := product.get("description", "").strip():
        schema["description"] = desc

    if image_urls:
        schema["image"] = image_urls if len(image_urls) > 1 else image_urls[0]

    # Offers — only if price data available (requires updated snapshot)
    variants = (product.get("variants") or {}).get("edges", [])
    if variants:
        price = variants[0]["node"].get("price")
        status = product.get("status", "ACTIVE")
        availability = (
            "https://schema.org/InStock" if status == "ACTIVE" else "https://schema.org/OutOfStock"
        )
        if price is not None:
            schema["offers"] = {
                "@type": "Offer",
                "price": str(price),
                "priceCurrency": "EUR",
                "availability": availability,
                "url": url,
            }

    return schema


def push_schema(
    product_id: str,
    schema: dict[str, Any],
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Push a JSON-LD schema as a Shopify metafield (custom.json_ld).

    Args:
        product_id: Shopify Product GID.
        schema: JSON-LD dict to store.
        endpoint: GraphQL endpoint (resolved from .env if omitted).
        headers: Request headers (resolved from .env if omitted).

    Returns:
        Raw mutation response dict.

    Raises:
        ShopifyUserError: If Shopify returns userErrors.
    """
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    variables = {
        "metafields": [
            {
                "ownerId": product_id,
                "namespace": "custom",
                "key": "json_ld",
                "type": "json",
                "value": json.dumps(schema, ensure_ascii=False),
            }
        ]
    }

    for attempt in range(3):
        response = requests.post(
            endpoint,
            headers=headers,
            json={"query": _METAFIELDS_SET, "variables": variables},
            timeout=30,
        )
        if response.status_code != 429:
            break
        retry_after = int(response.headers.get("Retry-After", 10))
        console.print(
            f"[yellow]Rate limit — waiting {retry_after}s (attempt {attempt + 1}/3)[/yellow]"
        )
        time.sleep(retry_after)

    response.raise_for_status()
    data = response.json()

    user_errors = (data.get("data") or {}).get("metafieldsSet", {}).get("userErrors", [])
    if user_errors:
        raise ShopifyUserError(f"Shopify userErrors for {product_id}: {user_errors}")

    return data


@click.command()
@click.option("--snapshot", default="data/raw/shopify_snapshot.json", show_default=True)
@click.option(
    "--dry-run/--apply",
    default=True,
    show_default=True,
    help="Dry-run by default. Pass --apply to write to Shopify.",
)
@click.option("--delay", default=0.5, show_default=True, help="Seconds between mutations")
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(snapshot: str, dry_run: bool, delay: float, tenant: str | None) -> None:
    """Push JSON-LD Product structured data to Shopify via metafields (custom.json_ld).

    Reads the Shopify snapshot. Re-run crawl_shopify first to get price data.
    Requires --apply to write. After applying, add the Liquid snippet to your theme.
    """
    cfg = get_config(tenant)
    console.print("[bold cyan]► Generating JSON-LD structured data[/bold cyan]")

    with open(snapshot, encoding="utf-8") as f:
        data = json.load(f)
    products: list[dict[str, Any]] = data.get("products", [])

    has_price = any((p.get("variants") or {}).get("edges") for p in products)
    if not has_price:
        console.print(
            "[yellow]  ⚠ No price data in snapshot — offers will be omitted.\n"
            "  Re-run: python -m scripts.audit.crawl_shopify[/yellow]"
        )

    schemas = [(p, build_product_schema(p, cfg)) for p in products]

    # Preview table
    table = Table(title="JSON-LD Preview", show_lines=True)
    table.add_column("Produit", style="cyan", max_width=30)
    table.add_column("Type", width=8)
    table.add_column("Prix", width=8)
    table.add_column("Dispo", width=10)
    table.add_column("Images", width=6)

    for product, schema in schemas:
        offers = schema.get("offers", {})
        table.add_row(
            product.get("title", "?")[:30],
            schema["@type"],
            offers.get("price", "—"),
            "InStock"
            if "InStock" in offers.get("availability", "")
            else ("OutOfStock" if offers else "—"),
            str(
                len(schema.get("image", []))
                if isinstance(schema.get("image"), list)
                else (1 if "image" in schema else 0)
            ),
        )

    console.print(table)
    console.print(f"\n  [bold]{len(schemas)}[/bold] produit(s) à mettre à jour\n")

    if dry_run:
        console.print("[yellow]Dry-run — aucune écriture sur Shopify.[/yellow]")
        console.print("[dim]Relancer avec --apply pour pousser les metafields.[/dim]")
        console.print(_THEME_SNIPPET)
        return

    # Human confirmation gate (CLAUDE.md rule #3)
    console.print("[bold red]⚠  Vous allez écrire des metafields sur Shopify.[/bold red]")
    confirm = click.prompt("Tapez 'yes' pour confirmer")
    if confirm.strip().lower() != "yes":
        console.print("[yellow]Annulé.[/yellow]")
        return

    endpoint, headers = _get_client()
    applied = errors = 0

    for product, schema in schemas:
        name = product.get("title", "?")
        try:
            push_schema(product["id"], schema, endpoint, headers)
            _log_schema(product["id"], json.dumps(schema, ensure_ascii=False))
            console.print(f"  [green]✓[/green] {name}")
            applied += 1
        except ShopifyUserError as exc:
            console.print(f"  [red]✗[/red] {name}: {exc}")
            errors += 1

        time.sleep(delay)

    console.print(f"\n[bold]Done:[/bold] {applied} mis à jour, {errors} erreurs")
    console.print(_THEME_SNIPPET)


if __name__ == "__main__":
    main()
