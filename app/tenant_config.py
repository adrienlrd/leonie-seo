"""Minimal tenant configuration lookup for the application layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).parents[1]
_TENANTS_DIR = _PROJECT_ROOT / "config" / "tenants"


@dataclass(frozen=True)
class TenantSummary:
    """Subset of tenant config needed by application-layer services."""

    tenant_id: str
    brand: str
    shopify_store_domain: str


def _read_tenant(path: Path) -> TenantSummary | None:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    domain = str(data.get("shopify_store_domain", "")).strip()
    brand = str(data.get("brand", "")).strip()
    tenant_id = str(data.get("tenant_id", path.stem)).strip()
    if not domain or not brand:
        return None
    return TenantSummary(
        tenant_id=tenant_id,
        brand=brand,
        shopify_store_domain=domain,
    )


def find_tenant_by_shop_domain(shop: str | None) -> TenantSummary | None:
    """Return tenant metadata for a Shopify shop domain.

    Args:
        shop: Shopify shop domain.

    Returns:
        TenantSummary when a matching tenant YAML exists, otherwise None.
    """
    if not shop:
        return None
    for path in sorted(_TENANTS_DIR.glob("*.yaml")):
        tenant = _read_tenant(path)
        if tenant and tenant.shopify_store_domain == shop:
            return tenant
    return None
