"""Crawl Shopify catalog: all products and collections with SEO fields."""

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

from scripts.license import LicenseError, require_valid_license

load_dotenv()

console = Console()

_ENDPOINT_TMPL = "https://{domain}/admin/api/2025-01/graphql.json"

# Pagination size — Shopify GraphQL caps connection arguments at 250.
# Increasing from 50 → 250 divides round-trips by 5.
_PAGE_SIZE = 250

# Max consecutive 429s before giving up on the request.
_MAX_THROTTLE_RETRIES = 3

_PRODUCTS_QUERY = f"""
query GetProducts($cursor: String) {{
  products(first: {_PAGE_SIZE}, after: $cursor) {{
    pageInfo {{ hasNextPage endCursor }}
    edges {{
      node {{
        id title handle status publishedAt onlineStoreUrl
        description
        seo {{ title description }}
        images(first: 10) {{
          edges {{ node {{ id url altText }} }}
        }}
        collections(first: 5) {{
          edges {{ node {{ title }} }}
        }}
        variants(first: 1) {{
          edges {{ node {{ price }} }}
        }}
      }}
    }}
  }}
}}
"""

_COLLECTIONS_QUERY = f"""
query GetCollections($cursor: String) {{
  collections(first: {_PAGE_SIZE}, after: $cursor) {{
    pageInfo {{ hasNextPage endCursor }}
    edges {{
      node {{
        id title handle
        seo {{ title description }}
      }}
    }}
  }}
}}
"""

_PAGES_QUERY = f"""
query GetPages($cursor: String) {{
  pages(first: {_PAGE_SIZE}, after: $cursor) {{
    pageInfo {{ hasNextPage endCursor }}
    edges {{
      node {{
        id title handle body
        seo {{ title description }}
        onlineStoreUrl
      }}
    }}
  }}
}}
"""

# Note: nested articles(first: {_PAGE_SIZE}) silently truncates blogs with more
# articles. Acceptable trade-off — content pages are only consumed by /crawl/l3.
_BLOGS_QUERY = f"""
query GetBlogs($cursor: String) {{
  blogs(first: {_PAGE_SIZE}, after: $cursor) {{
    pageInfo {{ hasNextPage endCursor }}
    edges {{
      node {{
        id title handle
        articles(first: {_PAGE_SIZE}) {{
          edges {{
            node {{
              id title handle body
              seo {{ title description }}
              onlineStoreUrl
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""

_URL_REDIRECTS_QUERY = f"""
query GetUrlRedirects($cursor: String) {{
  urlRedirects(first: {_PAGE_SIZE}, after: $cursor) {{
    pageInfo {{ hasNextPage endCursor }}
    edges {{
      node {{ id path target }}
    }}
  }}
}}
"""

_SHOP_METADATA_QUERY = """
query GetShopMetadata {
  shop {
    name
    myshopifyDomain
    primaryDomain { host url }
    domains { host url }
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
    """Execute a single GraphQL request against Shopify Admin API.

    Bounded retry on 429 (up to ``_MAX_THROTTLE_RETRIES``) — replaces the prior
    recursive implementation which could spin forever on persistent throttling.
    """
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    payload = {"query": query, "variables": variables or {}}
    for attempt in range(_MAX_THROTTLE_RETRIES + 1):
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
        if attempt == _MAX_THROTTLE_RETRIES:
            response.raise_for_status()
        retry_after = int(response.headers.get("Retry-After", 5))
        console.print(f"[yellow]Rate limit — waiting {retry_after}s (attempt {attempt + 1})[/yellow]")
        time.sleep(retry_after)
    raise RuntimeError("unreachable")  # for type-checkers


def _check_throttle(data: dict[str, Any]) -> None:
    """Pause briefly if the GraphQL bucket is near empty.

    Shopify restores 50 points/s on a 1000-point bucket. We only pause when we
    are close to exhaustion to avoid throttling the entire crawl needlessly.
    """
    available = (
        data.get("extensions", {})
        .get("cost", {})
        .get("throttleStatus", {})
        .get("currentlyAvailable", 1000)
    )
    if available < 50:
        time.sleep(1)


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


def fetch_pages(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch CMS pages with SEO and Online Store URL fields."""
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = graphql_request(_PAGES_QUERY, {"cursor": cursor}, endpoint, headers)
        _check_throttle(data)

        pages = data["data"]["pages"]
        for edge in pages["edges"]:
            results.append(edge["node"])

        if not pages["pageInfo"]["hasNextPage"]:
            break
        cursor = pages["pageInfo"]["endCursor"]

    return results


def fetch_articles(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch blog articles with their parent blog handle."""
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = graphql_request(_BLOGS_QUERY, {"cursor": cursor}, endpoint, headers)
        _check_throttle(data)

        blogs = data["data"]["blogs"]
        for edge in blogs["edges"]:
            blog = edge["node"]
            for article_edge in blog.get("articles", {}).get("edges", []):
                article = dict(article_edge["node"])
                article["blog_id"] = blog.get("id")
                article["blog_handle"] = blog.get("handle")
                article["blog_title"] = blog.get("title")
                results.append(article)

        if not blogs["pageInfo"]["hasNextPage"]:
            break
        cursor = blogs["pageInfo"]["endCursor"]

    return results


def fetch_url_redirects(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch Shopify URL redirects."""
    if endpoint is None or headers is None:
        endpoint, headers = _get_client()

    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = graphql_request(_URL_REDIRECTS_QUERY, {"cursor": cursor}, endpoint, headers)
        _check_throttle(data)

        redirects = data["data"]["urlRedirects"]
        for edge in redirects["edges"]:
            results.append(edge["node"])

        if not redirects["pageInfo"]["hasNextPage"]:
            break
        cursor = redirects["pageInfo"]["endCursor"]

    return results


def fetch_shop_metadata(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch shop domain metadata used by Crawl L3."""
    data = graphql_request(_SHOP_METADATA_QUERY, {}, endpoint, headers)
    _check_throttle(data)
    return data.get("data", {}).get("shop", {})


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
    now = datetime.now(UTC).isoformat()
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

    pages = fetch_pages()
    console.print(f"  [green]✓[/green] {len(pages)} pages")

    articles = fetch_articles()
    console.print(f"  [green]✓[/green] {len(articles)} articles")

    redirects = fetch_url_redirects()
    console.print(f"  [green]✓[/green] {len(redirects)} redirects")

    shop = fetch_shop_metadata()

    conn = init_db(db_path)
    save_snapshot(conn, "product", products)
    save_snapshot(conn, "collection", collections)
    save_snapshot(conn, "page", pages)
    save_snapshot(conn, "article", articles)
    save_snapshot(conn, "url_redirect", redirects)
    conn.close()
    console.print(f"  [green]✓[/green] Snapshot → {db_path}")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(
        json.dumps(
            {
                "shop": shop,
                "products": products,
                "collections": collections,
                "pages": pages,
                "articles": articles,
                "redirects": redirects,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    console.print(f"  [green]✓[/green] JSON → {output}")


if __name__ == "__main__":
    main()
