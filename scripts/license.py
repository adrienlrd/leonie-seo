"""License key management — HMAC-signed keys for per-boutique authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta

import click
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

_KEY_PREFIX = "LEO-"
_ENV_API_KEY = "LEONIE_API_KEY"
_ENV_SECRET = "LICENSE_SECRET"
_DEFAULT_SECRET = "leonie-seo-v1"


class LicenseError(Exception):
    """Raised when a license key is missing, invalid, or expired."""


def _secret(override: str | None = None) -> str:
    return override or os.getenv(_ENV_SECRET, _DEFAULT_SECRET)


def _sign(payload: dict, secret: str) -> str:
    data = json.dumps(payload, sort_keys=True)
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


_VALID_PLANS = frozenset({"free", "pro", "agency"})


def issue_key(
    tenant_id: str,
    days: int,
    secret: str | None = None,
    plan: str = "pro",
) -> str:
    """Generate a signed license key for a tenant.

    Args:
        tenant_id: Tenant identifier embedded in the key.
        days: Days until expiry (negative = already expired, useful in tests).
        secret: Signing secret. Defaults to LICENSE_SECRET env var.
        plan: Pricing plan — "free", "pro", or "agency". Defaults to "pro".

    Returns:
        A LEO-prefixed, base64-encoded signed key string.
    """
    if plan not in _VALID_PLANS:
        raise LicenseError(f"Plan inconnu : {plan!r}. Valeurs acceptées : {sorted(_VALID_PLANS)}")
    sec = _secret(secret)
    expiry = (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%d")
    payload = {"expiry": expiry, "plan": plan, "tenant_id": tenant_id}
    sig = _sign(payload, sec)
    raw = json.dumps({**payload, "sig": sig}, sort_keys=True)
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"{_KEY_PREFIX}{encoded}"


def decode_key(api_key: str) -> dict:
    """Decode a license key to its raw payload dict (no signature check).

    Args:
        api_key: LEO-prefixed key string.

    Returns:
        Decoded dict including the sig field.

    Raises:
        LicenseError: If the key format or encoding is invalid.
    """
    if not api_key.startswith(_KEY_PREFIX):
        raise LicenseError(f"Format invalide — la clé doit commencer par {_KEY_PREFIX}")
    try:
        b64 = api_key[len(_KEY_PREFIX) :]
        padded = b64 + "=" * (-len(b64) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return json.loads(raw)
    except Exception as e:
        raise LicenseError(f"Clé illisible : {e}") from e


def validate_key(api_key: str, secret: str | None = None) -> dict:
    """Validate a license key: signature integrity and expiry date.

    Args:
        api_key: LEO-prefixed key string.
        secret: Signing secret. Defaults to LICENSE_SECRET env var.

    Returns:
        Payload dict with tenant_id and expiry on success.

    Raises:
        LicenseError: If signature is wrong, key is expired, or format invalid.
    """
    sec = _secret(secret)
    data = decode_key(api_key)
    sig = data.pop("sig", None)
    if sig is None:
        raise LicenseError("Clé sans signature")
    expected = _sign(data, sec)
    if not hmac.compare_digest(sig, expected):
        raise LicenseError("Signature invalide — clé corrompue ou non autorisée")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if today > data["expiry"]:
        raise LicenseError(f"Licence expirée le {data['expiry']}")
    # Backward compat: legacy keys without a plan field default to "pro"
    data.setdefault("plan", "pro")
    return data


def require_valid_license(
    api_key: str | None = None,
    secret: str | None = None,
) -> dict | None:
    """Check the active license key. No-op if LEONIE_API_KEY is not set.

    Allows personal/local use without a key. Only validates when a key is
    explicitly configured — enabling the tool to require licensing per client
    while remaining frictionless for the owner's own boutique.

    Args:
        api_key: Override key (defaults to LEONIE_API_KEY env var).
        secret: Override signing secret.

    Returns:
        Payload dict if key is present and valid, None if no key is configured.

    Raises:
        LicenseError: If a key is set but invalid or expired.
    """
    key = api_key or os.getenv(_ENV_API_KEY)
    if not key:
        return None
    return validate_key(key, secret)


# ── CLI ────────────────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """License key management — issue and validate per-boutique API keys."""


@cli.command("issue")
@click.option("--tenant", required=True, help="Tenant ID to embed in the key")
@click.option("--days", default=365, show_default=True, help="Days until expiry")
@click.option(
    "--plan",
    default="pro",
    show_default=True,
    type=click.Choice(["free", "pro", "agency"]),
    help="Pricing plan",
)
@click.option("--secret", default=None, help="Override LICENSE_SECRET env var")
def cmd_issue(tenant: str, days: int, plan: str, secret: str | None) -> None:
    """Generate a new signed license key for a boutique."""
    key = issue_key(tenant, days, secret, plan=plan)
    expiry = (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%d")
    console.print(
        f"\n  [green]✓[/green] Clé générée pour [cyan]{tenant}[/cyan]"
        f" — plan [magenta]{plan}[/magenta]"
        f" — expire le [yellow]{expiry}[/yellow]\n"
    )
    console.print(f"  [bold]{key}[/bold]\n")
    console.print(
        f"  [dim]→ Ajouter dans le .env du client :[/dim] [cyan]LEONIE_API_KEY={key}[/cyan]"
    )


@cli.command("check")
@click.option("--key", default=None, help="Override LEONIE_API_KEY env var")
@click.option("--secret", default=None, help="Override LICENSE_SECRET env var")
def cmd_check(key: str | None, secret: str | None) -> None:
    """Validate the current license key from .env."""
    try:
        result = require_valid_license(api_key=key, secret=secret)
        if result is None:
            console.print(
                "  [yellow]⚠[/yellow] LEONIE_API_KEY non définie"
                " — mode usage personnel (sans licence commerciale)"
            )
        else:
            console.print(
                f"  [green]✓[/green] Licence valide"
                f" — tenant [cyan]{result['tenant_id']}[/cyan]"
                f", plan [magenta]{result.get('plan', 'pro')}[/magenta]"
                f", expire le [yellow]{result['expiry']}[/yellow]"
            )
    except LicenseError as e:
        console.print(f"  [red]✗[/red] Licence invalide : {e}")


if __name__ == "__main__":
    cli()
