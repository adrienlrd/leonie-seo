"""Create 301 URL redirects on Shopify in bulk from a validated CSV. Dry-run by default."""

import csv
import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
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

_CREATE_REDIRECT = """
mutation urlRedirectCreate($urlRedirect: UrlRedirectInput!) {
  urlRedirectCreate(urlRedirect: $urlRedirect) {
    urlRedirect {
      id
      path
      target
    }
    userErrors { field message code }
  }
}
"""


class ShopifyUserError(Exception):
    """Raised when Shopify returns userErrors in a mutation response."""


class InvalidRedirectError(Exception):
    """Raised when a redirect row fails validation."""


def _log_redirect(from_path: str, to_path: str) -> None:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "INSERT INTO seo_changes (applied_at, resource_type, resource_id, field, old_value, new_value, status)"
        " VALUES (?, 'redirect', ?, 'url_redirect', ?, ?, 'applied')",
        (datetime.now(UTC).isoformat(), from_path, None, to_path),
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


def validate_redirects(
    rows: list[dict[str, str]],
    existing_handles: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    """Validate redirect rows and return (valid_rows, warnings).

    Args:
        rows: List of dicts with keys from_path and to_path.
        existing_handles: Set of live product/collection handles to warn on conflicts.

    Returns:
        Tuple of (valid rows, list of warning strings for skipped/suspicious rows).
    """
    valid: list[dict[str, str]] = []
    warnings: list[str] = []
    seen_from: set[str] = set()

    for i, row in enumerate(rows, 1):
        from_path = row.get("from_path", "").strip()
        to_path = row.get("to_path", "").strip()

        if not from_path or not to_path:
            warnings.append(f"Row {i}: empty from_path or to_path — skipped")
            continue

        if not from_path.startswith("/"):
            warnings.append(f"Row {i}: from_path '{from_path}' must start with '/' — skipped")
            continue

        if not (to_path.startswith("/") or to_path.startswith("https://")):
            warnings.append(
                f"Row {i}: to_path '{to_path}' must start with '/' or 'https://' — skipped"
            )
            continue

        if from_path == to_path:
            warnings.append(f"Row {i}: self-redirect '{from_path}' → skipped")
            continue

        if from_path in seen_from:
            warnings.append(f"Row {i}: duplicate from_path '{from_path}' — skipped")
            continue

        # Warn if from_path matches a live handle (product may still exist)
        if existing_handles:
            handle = from_path.lstrip("/").split("/")[-1]
            if handle in existing_handles:
                warnings.append(
                    f"Row {i}: '{from_path}' matches a live handle '{handle}' — "
                    "redirect will only trigger if the page is deleted or unpublished"
                )

        seen_from.add(from_path)
        valid.append({"from_path": from_path, "to_path": to_path})

    return valid, warnings


def create_redirect(
    from_path: str,
    to_path: str,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a single 301 redirect on Shopify.

    Args:
        from_path: Source path (e.g. /old-product).
        to_path: Destination path or URL.
        endpoint: GraphQL endpoint (resolved from .env if omitted).
        headers: Request headers (resolved from .env if omitted).

    Returns:
        Raw mutation response dict.

    Raises:
        ShopifyUserError: If Shopify returns userErrors.
    """
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    variables = {"urlRedirect": {"path": from_path, "target": to_path}}

    for attempt in range(3):
        response = requests.post(
            endpoint,
            headers=headers,
            json={"query": _CREATE_REDIRECT, "variables": variables},
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

    user_errors = (data.get("data") or {}).get("urlRedirectCreate", {}).get("userErrors", [])
    if user_errors:
        raise ShopifyUserError(f"Shopify userErrors for '{from_path}': {user_errors}")

    return data


def _load_snapshot_handles(snapshot_path: str) -> set[str]:
    """Return all product and collection handles from the Shopify snapshot."""
    p = Path(snapshot_path)
    if not p.exists():
        return set()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    handles: set[str] = set()
    for product in data.get("products", []):
        if h := product.get("handle"):
            handles.add(h)
    for collection in data.get("collections", []):
        if h := collection.get("handle"):
            handles.add(h)
    return handles


@click.command()
@click.option("--csv", "csv_path", required=True, help="CSV file with columns: from_path, to_path")
@click.option(
    "--dry-run/--apply",
    default=True,
    show_default=True,
    help="Dry-run by default. Pass --apply to write to Shopify.",
)
@click.option("--delay", default=0.5, show_default=True, help="Seconds between mutations")
@click.option(
    "--snapshot",
    default="data/raw/shopify_snapshot.json",
    show_default=True,
    help="Shopify snapshot for handle conflict detection",
)
def main(csv_path: str, dry_run: bool, delay: float, snapshot: str) -> None:
    """Create 301 URL redirects on Shopify in bulk from a CSV file.

    CSV must have two columns: from_path and to_path.
    Always shows a preview. Requires explicit --apply to write to Shopify.
    """
    # Load and validate
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        console.print("[red]CSV is empty.[/red]")
        return

    if "from_path" not in rows[0] or "to_path" not in rows[0]:
        console.print("[red]CSV must have columns: from_path, to_path[/red]")
        return

    existing_handles = _load_snapshot_handles(snapshot)
    valid_rows, warnings = validate_redirects(rows, existing_handles)

    for w in warnings:
        console.print(f"  [yellow]⚠[/yellow] {w}")

    if not valid_rows:
        console.print("[red]No valid redirects to process.[/red]")
        return

    # Preview table
    table = Table(title="Redirects Preview (301)", show_lines=True)
    table.add_column("From path", style="yellow", max_width=45)
    table.add_column("To path", style="green", max_width=45)

    for row in valid_rows:
        table.add_row(row["from_path"], row["to_path"])

    console.print(table)
    console.print(f"\n  [bold]{len(valid_rows)}[/bold] redirect(s) à créer\n")

    if dry_run:
        console.print("[yellow]Dry-run — aucune écriture sur Shopify.[/yellow]")
        console.print("[dim]Relancer avec --apply pour créer les redirections.[/dim]")
        return

    # Human confirmation gate (CLAUDE.md rule #3)
    console.print("[bold red]⚠  Vous allez écrire des redirections sur Shopify.[/bold red]")
    confirm = click.prompt("Tapez 'yes' pour confirmer")
    if confirm.strip().lower() != "yes":
        console.print("[yellow]Annulé.[/yellow]")
        return

    endpoint, headers = _get_client()
    applied = errors = 0

    for row in valid_rows:
        from_path = row["from_path"]
        to_path = row["to_path"]
        try:
            create_redirect(from_path, to_path, endpoint, headers)
            _log_redirect(from_path, to_path)
            console.print(f"  [green]✓[/green] {from_path} → {to_path}")
            applied += 1
        except ShopifyUserError as exc:
            console.print(f"  [red]✗[/red] {from_path}: {exc}")
            errors += 1

        time.sleep(delay)

    console.print(f"\n[bold]Done:[/bold] {applied} créées, {errors} erreurs")


if __name__ == "__main__":
    main()
