"""Fetch PageSpeed Insights scores and Core Web Vitals per URL."""

import os
import time
from pathlib import Path
from typing import Any

import click
import pandas as pd
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

console = Console()

_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def fetch_score(url: str, strategy: str = "mobile") -> dict[str, Any]:
    """Fetch PageSpeed score and CWV for a single URL and strategy.

    Args:
        url: Full URL to audit.
        strategy: "mobile" or "desktop".

    Returns:
        Dict with url, strategy, performance_score (0-1), lcp_ms, cls, tbt_ms, fcp_ms.
    """
    params = {
        "url": url,
        "strategy": strategy,
        "key": os.environ["PAGESPEED_API_KEY"],
        "category": "performance",
    }

    response = requests.get(_API_URL, params=params, timeout=600)

    if response.status_code == 429:
        console.print("[yellow]Rate limit — waiting 10s[/yellow]")
        time.sleep(10)
        return fetch_score(url, strategy)

    response.raise_for_status()
    data = response.json()

    lr = data["lighthouseResult"]
    audits = lr["audits"]

    return {
        "url": url,
        "strategy": strategy,
        "performance_score": lr["categories"]["performance"]["score"],
        "lcp_ms": audits.get("largest-contentful-paint", {}).get("numericValue"),
        "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
        "tbt_ms": audits.get("total-blocking-time", {}).get("numericValue"),
        "fcp_ms": audits.get("first-contentful-paint", {}).get("numericValue"),
    }


def fetch_scores_for_urls(urls: list[str], delay: float = 1.5) -> list[dict[str, Any]]:
    """Fetch mobile and desktop scores for a list of URLs.

    Args:
        urls: List of URLs to audit.
        delay: Seconds to wait between API calls to avoid rate limits.
    """
    results: list[dict[str, Any]] = []
    for url in urls:
        for strategy in ("mobile", "desktop"):
            try:
                result = fetch_score(url, strategy)
                results.append(result)
                console.print(
                    f"  [green]✓[/green] {strategy:8} {result['performance_score']:.0%}  {url}"
                )
            except (requests.exceptions.Timeout, requests.exceptions.HTTPError) as exc:
                console.print(
                    f"  [yellow]⚠ {type(exc).__name__}, retrying…[/yellow] {strategy:8} {url}"
                )
                try:
                    result = fetch_score(url, strategy)
                    results.append(result)
                    console.print(
                        f"  [green]✓[/green] {strategy:8} {result['performance_score']:.0%}  {url} (retry)"
                    )
                except (requests.exceptions.Timeout, requests.exceptions.HTTPError):
                    console.print(f"  [red]✗ failed x2[/red] {strategy:8} {url} — skipped")
            time.sleep(delay)
    return results


@click.command()
@click.argument("urls", nargs=-1)
@click.option("--output", default="data/raw/pagespeed.csv", show_default=True)
def main(urls: tuple[str, ...], output: str) -> None:
    """Fetch PageSpeed scores for given URLs (mobile + desktop).

    Pass URLs as arguments, or omit to audit the homepage only.
    """
    console.print("[bold cyan]► Fetching PageSpeed scores[/bold cyan]")

    if not urls:
        domain = os.getenv("SHOPIFY_STORE_DOMAIN")
        if not domain:
            from scripts._config import get_config

            domain = get_config().domain
        urls = (f"https://{domain}",)
        console.print("  [dim]No URLs given — auditing homepage only[/dim]")

    results = fetch_scores_for_urls(list(urls))
    df = pd.DataFrame(results)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    table = Table(title="PageSpeed Results")
    for col in df.columns:
        table.add_column(col)
    for _, row in df.iterrows():
        table.add_row(*[str(v) for v in row])
    console.print(table)
    console.print(f"  [green]✓[/green] Saved → {output}")


if __name__ == "__main__":
    main()
