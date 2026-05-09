"""Update meta titles and descriptions on Shopify products. Dry-run by default."""

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
from scripts.license import LicenseError, require_valid_license

load_dotenv()

console = Console()

_ENDPOINT_TMPL = "https://{domain}/admin/api/2025-01/graphql.json"

_UPDATE_PRODUCT_SEO = """
mutation UpdateProductSEO($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      seo { title description }
    }
    userErrors { field message }
  }
}
"""

_UPDATE_COLLECTION_SEO = """
mutation UpdateCollectionSEO($input: CollectionInput!) {
  collectionUpdate(collection: $input) {
    collection {
      id
      seo { title description }
    }
    userErrors { field message }
  }
}
"""


class ShopifyUserError(Exception):
    """Raised when Shopify returns userErrors in a mutation response."""


def _log_change(
    resource_id: str,
    resource_type: str,
    field: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "INSERT INTO seo_changes (applied_at, resource_type, resource_id, field, old_value, new_value, status)"
        " VALUES (?, ?, ?, ?, ?, ?, 'applied')",
        (datetime.now(UTC).isoformat(), resource_type, resource_id, field, old_value, new_value),
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


def update_product_seo(
    product_id: str,
    seo_title: str | None,
    seo_description: str | None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply an SEO mutation for a single product.

    Args:
        product_id: Shopify GID (e.g. gid://shopify/Product/123).
        seo_title: New meta title, or None to leave unchanged.
        seo_description: New meta description, or None to leave unchanged.
        endpoint: GraphQL endpoint (resolved from .env if omitted).
        headers: Request headers (resolved from .env if omitted).

    Returns:
        Raw mutation response dict.

    Raises:
        ShopifyUserError: If Shopify returns userErrors.
    """
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    seo_input: dict[str, str] = {}
    if seo_title is not None:
        seo_input["title"] = seo_title
    if seo_description is not None:
        seo_input["description"] = seo_description

    variables = {"input": {"id": product_id, "seo": seo_input}}

    for attempt in range(3):
        response = requests.post(
            endpoint,
            headers=headers,
            json={"query": _UPDATE_PRODUCT_SEO, "variables": variables},
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

    user_errors = (data.get("data") or {}).get("productUpdate", {}).get("userErrors", [])
    if user_errors:
        raise ShopifyUserError(f"Shopify userErrors for {product_id}: {user_errors}")

    return data


def update_collection_seo(
    collection_id: str,
    seo_title: str | None,
    seo_description: str | None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply an SEO mutation for a single collection.

    Args:
        collection_id: Shopify Collection GID.
        seo_title: New meta title, or None to leave unchanged.
        seo_description: New meta description, or None to leave unchanged.
        endpoint: GraphQL endpoint (resolved from .env if omitted).
        headers: Request headers (resolved from .env if omitted).

    Raises:
        ShopifyUserError: If Shopify returns userErrors.
    """
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    seo_input: dict[str, str] = {}
    if seo_title is not None:
        seo_input["title"] = seo_title
    if seo_description is not None:
        seo_input["description"] = seo_description

    variables = {"input": {"id": collection_id, "seo": seo_input}}

    for attempt in range(3):
        response = requests.post(
            endpoint,
            headers=headers,
            json={"query": _UPDATE_COLLECTION_SEO, "variables": variables},
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

    user_errors = (data.get("data") or {}).get("collectionUpdate", {}).get("userErrors", [])
    if user_errors:
        raise ShopifyUserError(f"Shopify userErrors for {collection_id}: {user_errors}")

    return data


def _preview_table(updates: list[dict[str, Any]]) -> Table:
    table = Table(title="SEO Updates Preview", show_lines=True)
    table.add_column("Product", style="cyan", max_width=40)
    table.add_column("Field", style="yellow")
    table.add_column("Old value", max_width=40)
    table.add_column("New value", style="green", max_width=40)

    for u in updates:
        for field in ("title", "description"):
            new_val = u.get(f"new_{field}")
            if new_val is not None:
                table.add_row(
                    u.get("name", u.get("id", "?")),
                    f"seo.{field}",
                    str(u.get(f"old_{field}") or "—"),
                    str(new_val),
                )
    return table


@click.command()
@click.option(
    "--updates",
    required=True,
    help=(
        "JSON file — list of objects with keys: id, name, "
        "new_title, new_description, old_title, old_description"
    ),
)
@click.option(
    "--dry-run/--apply",
    default=True,
    show_default=True,
    help="Dry-run by default. Pass --apply to write to Shopify.",
)
@click.option("--delay", default=0.5, show_default=True, help="Seconds between mutations")
def main(updates: str, dry_run: bool, delay: float) -> None:
    """Update meta titles and descriptions on Shopify products.

    Reads a JSON file of pre-computed updates. Always shows a preview table.
    Requires explicit --apply to write anything to Shopify.
    """
    try:
        require_valid_license()
    except LicenseError as e:
        console.print(f"  [red]✗[/red] Licence invalide : {e}")
        raise SystemExit(1)
    with open(updates, encoding="utf-8") as f:
        update_list: list[dict[str, Any]] = json.load(f)

    console.print(_preview_table(update_list))
    console.print(f"\n[bold]{len(update_list)}[/bold] product(s) to update\n")

    if dry_run:
        console.print("[yellow]Dry-run mode — no changes written to Shopify.[/yellow]")
        console.print("[dim]Re-run with --apply to push these changes.[/dim]")
        return

    # Human confirmation gate (CLAUDE.md rule #3)
    console.print("[bold red]⚠  You are about to write to Shopify.[/bold red]")
    confirm = click.prompt("Type 'yes' to confirm")
    if confirm.strip().lower() != "yes":
        console.print("[yellow]Aborted.[/yellow]")
        return

    endpoint, headers = _get_client()
    applied = errors = 0

    for update in update_list:
        name = update.get("name", update.get("id", "?"))
        resource_id: str = update["id"]
        is_collection = resource_id.startswith("gid://shopify/Collection/")
        try:
            if is_collection:
                update_collection_seo(
                    resource_id,
                    update.get("new_title"),
                    update.get("new_description"),
                    endpoint,
                    headers,
                )
            else:
                update_product_seo(
                    resource_id,
                    update.get("new_title"),
                    update.get("new_description"),
                    endpoint,
                    headers,
                )
            resource_type = "collection" if is_collection else "product"
            for field in ("title", "description"):
                new_val = update.get(f"new_{field}")
                if new_val is not None:
                    _log_change(
                        resource_id,
                        resource_type,
                        f"seo.{field}",
                        update.get(f"old_{field}"),
                        new_val,
                    )
            console.print(f"  [green]✓[/green] {name}")
            applied += 1
        except ShopifyUserError as exc:
            console.print(f"  [red]✗[/red] {name}: {exc}")
            errors += 1

        time.sleep(delay)

    console.print(f"\n[bold]Done:[/bold] {applied} applied, {errors} errors")


if __name__ == "__main__":
    main()
