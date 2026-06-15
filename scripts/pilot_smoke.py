"""Pilot environment smoke checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import click
import requests

DEFAULT_WEB_URL = "https://pilot.leoniedelacroixfrance.com"
DEFAULT_API_URL = "https://leonie-seo-pilot-api.onrender.com"


@dataclass(frozen=True)
class SmokeResult:
    """Result of one public pilot smoke check."""

    name: str
    url: str
    ok: bool
    detail: str


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _get_text(url: str, timeout: float) -> tuple[int, str]:
    response = requests.get(url, timeout=timeout)
    return response.status_code, response.text.strip()


def _get_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    response = requests.get(url, timeout=timeout)
    payload = response.json() if response.content else {}
    return response.status_code, payload


def run_public_smoke_checks(
    *,
    web_url: str = DEFAULT_WEB_URL,
    api_url: str = DEFAULT_API_URL,
    timeout: float = 90.0,
) -> list[SmokeResult]:
    """Run public smoke checks against the pilot web and API services.

    Args:
        web_url: Public Remix app origin.
        api_url: Public Python API origin.
        timeout: Per-request timeout in seconds.

    Returns:
        One result per smoke check.
    """
    results: list[SmokeResult] = []

    web_health_url = _join_url(web_url, "/healthz")
    try:
        status, text = _get_text(web_health_url, timeout)
        results.append(
            SmokeResult(
                name="web_health",
                url=web_health_url,
                ok=status == 200 and text == "ok",
                detail=f"status={status} body={text!r}",
            )
        )
    except requests.RequestException as exc:
        results.append(SmokeResult("web_health", web_health_url, False, str(exc)))

    api_health_url = _join_url(api_url, "/health")
    try:
        status, payload = _get_json(api_health_url, timeout)
        missing_env = payload.get("missing_env") if isinstance(payload, dict) else None
        ok = status == 200 and payload.get("status") == "ok" and missing_env == []
        results.append(
            SmokeResult(
                name="api_health",
                url=api_health_url,
                ok=ok,
                detail=f"status={status} missing_env={missing_env}",
            )
        )
    except (requests.RequestException, ValueError) as exc:
        results.append(SmokeResult("api_health", api_health_url, False, str(exc)))

    privacy_url = _join_url(api_url, "/privacy")
    try:
        status, _text = _get_text(privacy_url, timeout)
        results.append(
            SmokeResult(
                name="privacy",
                url=privacy_url,
                ok=status == 200,
                detail=f"status={status}",
            )
        )
    except requests.RequestException as exc:
        results.append(SmokeResult("privacy", privacy_url, False, str(exc)))

    return results


@click.command()
@click.option("--web-url", default=DEFAULT_WEB_URL, show_default=True)
@click.option("--api-url", default=DEFAULT_API_URL, show_default=True)
@click.option("--timeout", default=90.0, show_default=True, type=float)
def smoke_public(web_url: str, api_url: str, timeout: float) -> None:
    """Run public smoke checks against the real-store pilot."""
    results = run_public_smoke_checks(web_url=web_url, api_url=api_url, timeout=timeout)
    failed = [result for result in results if not result.ok]

    for result in results:
        marker = "OK" if result.ok else "FAIL"
        click.echo(f"{marker} {result.name}: {result.detail} ({result.url})")

    if failed:
        raise click.ClickException(f"{len(failed)} pilot smoke check(s) failed")
