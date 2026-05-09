"""Update alt text on Shopify product images. Dry-run by default."""

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

from scripts._paths import DB_PATH as _DB_PATH

load_dotenv()

console = Console()

_ENDPOINT_TMPL = "https://{domain}/admin/api/2025-01/graphql.json"

_UPDATE_IMAGE_ALT = """
mutation productImageUpdate($productId: ID!, $image: ImageInput!) {
  productImageUpdate(productId: $productId, image: $image) {
    image {
      id
      altText
    }
    userErrors { field message }
  }
}
"""


class ShopifyUserError(Exception):
    """Raised when Shopify returns userErrors in a mutation response."""


def _log_change(
    resource_id: str,
    field: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "INSERT INTO seo_changes (applied_at, resource_type, resource_id, field, old_value, new_value, status)"
        " VALUES (?, 'product', ?, ?, ?, ?, 'applied')",
        (datetime.now(UTC).isoformat(), resource_id, field, old_value, new_value),
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


def update_image_alt(
    product_id: str,
    image_id: str,
    alt_text: str,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Update the alt text of a single product image.

    Args:
        product_id: Shopify Product GID.
        image_id: Shopify ProductImage GID.
        alt_text: New alt text (max 125 chars).
        endpoint: GraphQL endpoint (resolved from .env if omitted).
        headers: Request headers (resolved from .env if omitted).

    Raises:
        ShopifyUserError: If Shopify returns userErrors.
    """
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    variables = {
        "productId": product_id,
        "image": {"id": image_id, "altText": alt_text},
    }

    for attempt in range(3):
        response = requests.post(
            endpoint,
            headers=headers,
            json={"query": _UPDATE_IMAGE_ALT, "variables": variables},
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

    user_errors = (data.get("data") or {}).get("productImageUpdate", {}).get("userErrors", [])
    if user_errors:
        raise ShopifyUserError(f"Shopify userErrors for image {image_id}: {user_errors}")

    return data


@click.command()
@click.option("--suggestions", default="data/raw/alt_suggestions.json", show_default=True)
@click.option(
    "--dry-run/--apply",
    default=True,
    show_default=True,
    help="Dry-run by default. Pass --apply to write to Shopify.",
)
@click.option("--delay", default=0.5, show_default=True, help="Seconds between mutations")
def main(suggestions: str, dry_run: bool, delay: float) -> None:
    """Update image alt texts on Shopify products.

    Reads alt_suggestions.json produced by generate_suggestions.py.
    Requires explicit --apply to write anything to Shopify.
    """
    with open(suggestions, encoding="utf-8") as f:
        suggestion_list: list[dict[str, Any]] = json.load(f)

    table = Table(title="Alt Text Updates Preview", show_lines=True)
    table.add_column("Produit", style="cyan", max_width=28)
    table.add_column("Old alt", max_width=35)
    table.add_column("New alt", style="green", max_width=50)
    table.add_column("Chars", width=5)

    for s in suggestion_list:
        table.add_row(
            s.get("product_name", "?"),
            str(s.get("old_alt") or "—"),
            s.get("new_alt", ""),
            str(len(s.get("new_alt", ""))),
        )

    console.print(table)
    console.print(f"\n[bold]{len(suggestion_list)}[/bold] image(s) to update\n")

    if dry_run:
        console.print("[yellow]Dry-run — no changes written to Shopify.[/yellow]")
        console.print("[dim]Re-run with --apply to push changes.[/dim]")
        return

    # Human confirmation gate (CLAUDE.md rule #3)
    console.print("[bold red]⚠  You are about to write to Shopify.[/bold red]")
    confirm = click.prompt("Type 'yes' to confirm")
    if confirm.strip().lower() != "yes":
        console.print("[yellow]Aborted.[/yellow]")
        return

    endpoint, headers = _get_client()
    applied = errors = 0

    for s in suggestion_list:
        name = s.get("product_name", "?")
        try:
            update_image_alt(
                s["product_id"],
                s["image_id"],
                s["new_alt"],
                endpoint,
                headers,
            )
            _log_change(
                s["product_id"], f"image.altText:{s['image_id']}", s.get("old_alt"), s["new_alt"]
            )
            console.print(f"  [green]✓[/green] {name} — {s['new_alt'][:50]}")
            applied += 1
        except ShopifyUserError as exc:
            console.print(f"  [red]✗[/red] {name}: {exc}")
            errors += 1

        time.sleep(delay)

    console.print(f"\n[bold]Done:[/bold] {applied} applied, {errors} errors")


if __name__ == "__main__":
    main()
