"""Universal CLI setup wizard — tenant configuration and environment check."""

from __future__ import annotations

import os
import re
from pathlib import Path

import click
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from scripts._config import get_config, load_tenant, reset_config_cache
from scripts.license import LicenseError, require_valid_license

console = Console()

_TENANTS_DIR = Path(__file__).parent.parent / "config" / "tenants"
_NICHES_DIR = Path(__file__).parent.parent / "config" / "niches"
_ENV_PATH = Path(__file__).parent.parent / ".env"

_REQUIRED_SECRETS: list[tuple[str, str]] = [
    ("SHOPIFY_STORE_DOMAIN", "Domaine Shopify (ex: your-store.myshopify.com)"),
    ("SHOPIFY_ACCESS_TOKEN", "Token Admin Shopify"),
    ("GOOGLE_OAUTH_CLIENT_PATH", "Chemin vers le fichier client OAuth Google"),
]


def list_tenants() -> list[dict[str, str]]:
    """Return metadata for all tenant YAML files in config/tenants/.

    Returns:
        List of dicts with keys: tenant_id, name, domain, niche.
    """
    tenants: list[dict[str, str]] = []
    for path in sorted(_TENANTS_DIR.glob("*.yaml")):
        try:
            cfg = load_tenant(path.stem)
            tenants.append(
                {
                    "tenant_id": cfg.tenant_id,
                    "name": cfg.name,
                    "domain": cfg.domain,
                    "niche": cfg.niche,
                }
            )
        except (OSError, ValidationError, yaml.YAMLError, ValueError):
            tenants.append({"tenant_id": path.stem, "name": "?", "domain": "?", "niche": "?"})
    return tenants


def list_niches() -> list[str]:
    """Return available niche IDs from config/niches/."""
    return [p.stem for p in sorted(_NICHES_DIR.glob("*.yaml"))]


def current_tenant_id() -> str | None:
    """Return TENANT_ID value from .env file, or None if not set."""
    if not _ENV_PATH.exists():
        return None
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("TENANT_ID="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def validate_tenant_id(value: str) -> str:
    """Validate tenant_id: lowercase alphanumeric, hyphens, underscores.

    Args:
        value: Candidate tenant_id string.

    Returns:
        The validated value unchanged.

    Raises:
        click.BadParameter: If the value contains invalid characters.
    """
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", value):
        raise click.BadParameter("Doit être en minuscules, sans espaces (ex: maboutique-fr)")
    return value


def validate_base_url(value: str) -> str:
    """Validate that base_url starts with https://.

    Raises:
        click.BadParameter: If the URL does not start with https://.
    """
    if not value.startswith("https://"):
        raise click.BadParameter("Doit commencer par https://")
    return value.rstrip("/")


def validate_shopify_domain(value: str) -> str:
    """Validate that the Shopify store domain ends with .myshopify.com.

    Raises:
        click.BadParameter: If the domain does not end with .myshopify.com.
    """
    if not value.endswith(".myshopify.com"):
        raise click.BadParameter("Doit finir par .myshopify.com (ex: maboutique.myshopify.com)")
    return value


def generate_yaml(
    tenant_id: str,
    brand: str,
    base_url: str,
    shopify_store_domain: str,
    niche: str,
) -> str:
    """Generate a minimal tenant YAML string with default SEO rules.

    Args:
        tenant_id: Unique tenant identifier.
        brand: Display brand name.
        base_url: Full HTTPS URL of the store (no trailing slash).
        shopify_store_domain: Store's .myshopify.com domain.
        niche: Niche ID (must match a file in config/niches/).

    Returns:
        YAML string ready to be written to config/tenants/<tenant_id>.yaml.
    """
    data: dict = {
        "tenant_id": tenant_id,
        "name": brand,
        "brand": brand,
        "niche": niche,
        "base_url": base_url,
        "shopify_store_domain": shopify_store_domain,
        "product_categories": {},
        "categories": [],
        "category_labels": {},
        "category_collections": {},
        "hreflang_locales": [
            {"hreflang": "fr-FR", "prefix": ""},
            {"hreflang": "fr", "prefix": ""},
        ],
        "competitors": [],
        "seo_rules": {
            "title_min_chars": 50,
            "title_max_chars": 65,
            "description_min_chars": 120,
            "description_max_chars": 155,
            "description_min_words": 150,
            "min_alt_text_length": 10,
        },
        "alert_thresholds": {
            "quick_win_min_impressions": 30,
            "low_ctr_min_impressions": 100,
            "low_ctr_max_pct": 1.0,
            "cannibalization_min_impressions": 10,
            "cannibalization_severity_high": 0.6,
            "cannibalization_severity_medium": 0.3,
            "clicks_warn": 500,
            "clicks_ok": 2000,
            "ctr_warn": 2.0,
            "ctr_ok": 4.0,
            "position_warn": 20.0,
            "position_ok": 10.0,
            "eeat_warn": 25.0,
            "eeat_ok": 45.0,
            "eeat_weak_threshold": 0.45,
            "eeat_action_threshold": 0.15,
        },
    }
    header = f"# Tenant config — {brand}\n# Generated by scripts.setup\n\n"
    return header + yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def update_env(tenant_id: str, env_path: Path | None = None) -> None:
    """Write or update TENANT_ID in .env without touching other variables.

    Args:
        tenant_id: Tenant to activate.
        env_path: Path to .env file (defaults to project root .env).
    """
    path = env_path or _ENV_PATH
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        found = False
        for line in lines:
            if line.startswith("TENANT_ID="):
                new_lines.append(f"TENANT_ID={tenant_id}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"TENANT_ID={tenant_id}")
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    else:
        path.write_text(f"TENANT_ID={tenant_id}\n", encoding="utf-8")


# ── Click commands ─────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """Universal SEO pipeline setup — configure tenants and check credentials."""


@cli.command("list")
def cmd_list() -> None:
    """List all configured tenants."""
    tenants = list_tenants()
    active = current_tenant_id()

    table = Table(title="Tenants configurés")
    table.add_column("", width=2)
    table.add_column("ID", style="cyan")
    table.add_column("Nom", style="bold")
    table.add_column("Domaine")
    table.add_column("Niche")

    for t in tenants:
        marker = "●" if t["tenant_id"] == active else " "
        table.add_row(marker, t["tenant_id"], t["name"], t["domain"], t["niche"])

    console.print(table)

    if active:
        console.print(f"\n  Actif (TENANT_ID dans .env) : [cyan]{active}[/cyan]")
    else:
        console.print(
            "\n  [yellow]⚠[/yellow] TENANT_ID non défini dans .env"
            " — lancer [cyan]python -m scripts.setup init[/cyan]"
        )


@cli.command("init")
def cmd_init() -> None:
    """Interactive wizard to create a new tenant config."""
    console.print("[bold cyan]► Création d'un nouveau tenant[/bold cyan]\n")

    # tenant_id
    while True:
        tenant_id = click.prompt("  ID du tenant (ex: maboutique-fr)")
        try:
            tenant_id = validate_tenant_id(tenant_id)
        except click.BadParameter as exc:
            console.print(f"  [red]✗[/red] {exc}")
            continue
        dest = _TENANTS_DIR / f"{tenant_id}.yaml"
        if dest.exists():
            console.print(f"  [yellow]⚠[/yellow] Le tenant [cyan]{tenant_id}[/cyan] existe déjà.")
            if not click.confirm("  Écraser ?", default=False):
                return
        break

    # brand
    brand = click.prompt("  Nom de la marque (ex: Acme Pets)")

    # base_url
    while True:
        raw_url = click.prompt("  URL du site (ex: https://www.maboutique.com)")
        try:
            base_url = validate_base_url(raw_url)
            break
        except click.BadParameter as exc:
            console.print(f"  [red]✗[/red] {exc}")

    # shopify_store_domain
    while True:
        raw_domain = click.prompt("  Domaine Shopify (ex: maboutique.myshopify.com)")
        try:
            shopify_domain = validate_shopify_domain(raw_domain)
            break
        except click.BadParameter as exc:
            console.print(f"  [red]✗[/red] {exc}")

    # niche
    niches = list_niches()
    niche_display = ", ".join(f"[cyan]{n}[/cyan]" for n in niches) if niches else "(aucune)"
    console.print(f"\n  Niches disponibles : {niche_display}")
    default_niche = niches[0] if niches else "generic"
    niche = click.prompt("  Niche", default=default_niche)

    # Write YAML
    content = generate_yaml(tenant_id, brand, base_url, shopify_domain, niche)
    _TENANTS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    console.print(f"\n  [green]✓[/green] Config → {dest}")

    # Update .env
    if click.confirm(f"\n  Définir TENANT_ID={tenant_id} dans .env ?", default=True):
        update_env(tenant_id)
        reset_config_cache()
        console.print(f"  [green]✓[/green] .env mis à jour → TENANT_ID={tenant_id}")

    console.print("\n  [dim]Prochaines étapes :[/dim]")
    console.print("  [dim]1. Ajouter SHOPIFY_ACCESS_TOKEN et SHOPIFY_STORE_DOMAIN dans .env[/dim]")
    console.print("  [dim]2. python -m scripts.audit.crawl_shopify  # snapshot produits[/dim]")
    console.print("  [dim]3. python -m scripts.setup check  # vérifier la config[/dim]")


@cli.command("check")
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def cmd_check(tenant: str | None) -> None:
    """Validate tenant config and check required .env secrets."""
    console.print("[bold cyan]► Vérification configuration tenant[/bold cyan]\n")

    try:
        cfg = get_config(tenant)
        console.print(
            f"  [green]✓[/green] Tenant chargé : [cyan]{cfg.tenant_id}[/cyan] ({cfg.domain})"
        )
    except FileNotFoundError as exc:
        console.print(f"  [red]✗[/red] {exc}")
        console.print("  → Lancer [cyan]python -m scripts.setup init[/cyan] pour créer un tenant")
        return

    table = Table(title="Secrets .env requis")
    table.add_column("Variable", style="cyan")
    table.add_column("Description")
    table.add_column("Statut", justify="center")

    all_ok = True
    for key, description in _REQUIRED_SECRETS:
        present = bool(os.getenv(key))
        status = "[green]✓[/green]" if present else "[red]✗ manquant[/red]"
        if not present:
            all_ok = False
        table.add_row(key, description, status)

    console.print(table)

    if all_ok:
        console.print("\n  [green]✓[/green] Configuration complète — prêt à lancer les scripts")
    else:
        console.print(
            "\n  [yellow]⚠[/yellow] Ajouter les variables manquantes dans [cyan].env[/cyan]"
        )

    # License status
    console.print()
    try:
        result = require_valid_license()
        if result is None:
            console.print(
                "  [dim]Licence :[/dim] [yellow]⚠[/yellow] LEONIE_API_KEY non définie"
                " — usage personnel (sans licence commerciale)"
            )
        else:
            console.print(
                f"  [dim]Licence :[/dim] [green]✓[/green]"
                f" tenant [cyan]{result['tenant_id']}[/cyan]"
                f", expire le [yellow]{result['expiry']}[/yellow]"
            )
    except LicenseError as e:
        console.print(f"  [dim]Licence :[/dim] [red]✗[/red] {e}")


if __name__ == "__main__":
    cli()
