"""Crawl Shopify catalog: all products and collections with SEO fields."""

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import requests
from dotenv import load_dotenv
from rich.console import Console

from scripts.license import LicenseError, require_valid_license

load_dotenv()

console = Console()

_ENDPOINT_TMPL = "https://{domain}/admin/api/2025-01/graphql.json"

_PRODUCTS_QUERY = """
query GetProducts($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id title handle status
        description
        seo { title description }
        images(first: 10) {
          edges { node { id url altText } }
        }
        collections(first: 5) {
          edges { node { title } }
        }
        variants(first: 1) {
          edges { node { price } }
        }
      }
    }
  }
}
"""

_COLLECTIONS_QUERY = """
query GetCollections($cursor: String) {
  collections(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id title handle
        seo { title description }
      }
    }
  }
}
"""


def _get_client() -> tuple[str, dict[str, str]]:
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    token = os.environ["SHOPIFY_ACCESS_TOKEN"]
    return _ENDPOINT_TMPL.format(domain=domain), {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }


def graphql_request(
    query: str,
    variables: dict[str, Any] | None = None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute a single GraphQL request against Shopify Admin API."""
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    response = requests.post(
        endpoint,
        headers=headers,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )

    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 10))
        console.print(f"[yellow]Rate limit — waiting {retry_after}s[/yellow]")
        time.sleep(retry_after)
        return graphql_request(query, variables, endpoint, headers)

    response.raise_for_status()
    return response.json()


def _check_throttle(data: dict[str, Any]) -> None:
    available = (
        data.get("extensions", {})
        .get("cost", {})
        .get("throttleStatus", {})
        .get("currentlyAvailable", 1000)
    )
    if available < 100:
        console.print("[yellow]Throttle < 100 — waiting 2s[/yellow]")
        time.sleep(2)


def fetch_products(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all products with SEO fields and images (cursor-paginated)."""
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = graphql_request(_PRODUCTS_QUERY, {"cursor": cursor}, endpoint, headers)
        _check_throttle(data)

        products = data["data"]["products"]
        for edge in products["edges"]:
            results.append(edge["node"])

        if not products["pageInfo"]["hasNextPage"]:
            break
        cursor = products["pageInfo"]["endCursor"]

    return results


def fetch_collections(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all collections with SEO fields (cursor-paginated)."""
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = graphql_request(_COLLECTIONS_QUERY, {"cursor": cursor}, endpoint, headers)
        _check_throttle(data)

        collections = data["data"]["collections"]
        for edge in collections["edges"]:
            results.append(edge["node"])

        if not collections["pageInfo"]["hasNextPage"]:
            break
        cursor = collections["pageInfo"]["endCursor"]

    return results


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Initialize SQLite database. Schema lives in app.db (single source of truth)."""
    from app.db import DB_PATH as _DEFAULT_DB
    from app.db import init_db as _create_tables

    path = Path(db_path) if db_path else _DEFAULT_DB
    _create_tables(path)
    return sqlite3.connect(path)


def save_snapshot(
    conn: sqlite3.Connection,
    resource_type: str,
    resources: list[dict[str, Any]],
) -> None:
    """Insert a timestamped snapshot row for each resource."""
    now = datetime.utcnow().isoformat()
    conn.executemany(
        "INSERT INTO snapshots (snapshot_date, resource_type, resource_id, data_json)"
        " VALUES (?, ?, ?, ?)",
        [(now, resource_type, r["id"], json.dumps(r, ensure_ascii=False)) for r in resources],
    )
    conn.commit()


@click.command()
@click.option("--db-path", default="data/history.db", show_default=True)
@click.option("--output", default="data/raw/shopify_snapshot.json", show_default=True)
def main(db_path: str, output: str) -> None:
    """Crawl the Shopify catalog and save a snapshot to SQLite + JSON."""
    try:
        require_valid_license()
    except LicenseError as e:
        console.print(f"  [red]✗[/red] Licence invalide : {e}")
        raise SystemExit(1)
    console.print("[bold cyan]► Crawling Shopify catalog[/bold cyan]")

    products = fetch_products()
    console.print(f"  [green]✓[/green] {len(products)} products")

    collections = fetch_collections()
    console.print(f"  [green]✓[/green] {len(collections)} collections")

    conn = init_db(db_path)
    save_snapshot(conn, "product", products)
    save_snapshot(conn, "collection", collections)
    conn.close()
    console.print(f"  [green]✓[/green] Snapshot → {db_path}")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(
        json.dumps(
            {"products": products, "collections": collections}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    console.print(f"  [green]✓[/green] JSON → {output}")


if __name__ == "__main__":
    main()
