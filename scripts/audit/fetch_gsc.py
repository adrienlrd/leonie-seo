"""Fetch Google Search Console performance data for the last 90 days."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click
import pandas as pd
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from rich.console import Console

load_dotenv()

console = Console()

_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _default_site_url() -> str:
    if url := os.getenv("GSC_SITE_URL"):
        return url
    domain = os.getenv("SHOPIFY_STORE_DOMAIN", "www.leoniedelacroix.com")
    return f"https://{domain}"


def get_gsc_service(
    client_path: str | None = None,
    token_path: str | None = None,
) -> Any:
    """Authenticate and return a Search Console API service client.

    On first run, opens a browser window for OAuth consent.
    Subsequent runs reuse the saved token.
    """
    client_path = client_path or os.environ["GOOGLE_OAUTH_CLIENT_PATH"]
    token_path = token_path or os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", "./token.json")

    creds = None
    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_path, _SCOPES)
            creds = flow.run_local_server(port=0)
        Path(token_path).write_text(creds.to_json(), encoding="utf-8")

    return build("searchconsole", "v1", credentials=creds)


def fetch_search_performance(
    service: Any,
    site_url: str,
    days: int = 90,
) -> pd.DataFrame:
    """Fetch search performance grouped by URL for the last N days.

    Args:
        service: Authenticated Search Console API client.
        site_url: Property URL registered in GSC (e.g. https://www.example.com).
        days: Number of days to look back.

    Returns:
        DataFrame with columns: url, clicks, impressions, ctr, position.
    """
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)

    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page"],
        "rowLimit": 25000,
    }

    response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = response.get("rows", [])

    if not rows:
        return pd.DataFrame(columns=["url", "clicks", "impressions", "ctr", "position"])

    return pd.DataFrame(
        [
            {
                "url": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": row["ctr"],
                "position": row["position"],
            }
            for row in rows
        ]
    )


def fetch_query_page_performance(
    service: Any,
    site_url: str,
    days: int = 90,
) -> pd.DataFrame:
    """Fetch search performance grouped by query + page for the last N days.

    Args:
        service: Authenticated Search Console API client.
        site_url: Property URL registered in GSC.
        days: Number of days to look back.

    Returns:
        DataFrame with columns: query, url, clicks, impressions, ctr, position.
    """
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days)

    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["query", "page"],
        "rowLimit": 25000,
    }

    response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = response.get("rows", [])

    if not rows:
        return pd.DataFrame(columns=["query", "url", "clicks", "impressions", "ctr", "position"])

    return pd.DataFrame(
        [
            {
                "query": row["keys"][0],
                "url": row["keys"][1],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": row["ctr"],
                "position": row["position"],
            }
            for row in rows
        ]
    )


@click.command()
@click.option("--days", default=90, show_default=True)
@click.option("--output", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--query-page-output", default="data/raw/gsc_query_page.csv", show_default=True)
@click.option(
    "--site-url", default=None, help="GSC property URL (default: https://<SHOPIFY_STORE_DOMAIN>)"
)
def main(days: int, output: str, query_page_output: str, site_url: str | None) -> None:
    """Export Google Search Console performance data to CSV."""
    console.print("[bold cyan]► Fetching Google Search Console data[/bold cyan]")

    service = get_gsc_service()
    target = site_url or _default_site_url()

    df = fetch_search_performance(service, target, days)
    console.print(f"  [green]✓[/green] {len(df)} URLs fetched ({days} days, site: {target})")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    console.print(f"  [green]✓[/green] Saved → {output}")

    df_qp = fetch_query_page_performance(service, target, days)
    console.print(f"  [green]✓[/green] {len(df_qp)} query×page rows fetched")

    Path(query_page_output).parent.mkdir(parents=True, exist_ok=True)
    df_qp.to_csv(query_page_output, index=False)
    console.print(f"  [green]✓[/green] Saved → {query_page_output}")


if __name__ == "__main__":
    main()
