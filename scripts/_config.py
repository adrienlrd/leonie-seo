"""Tenant configuration loader — reads config/tenants/<tenant_id>.yaml."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_CONFIG_DIR = Path(__file__).parent.parent / "config" / "tenants"
_DEFAULT_TENANT = "leoniedelacroix"


class SeoRules(BaseModel):
    title_min_chars: int = 50
    title_max_chars: int = 65
    description_min_chars: int = 120
    description_max_chars: int = 155
    description_min_words: int = 150
    min_alt_text_length: int = 10


class AlertThresholds(BaseModel):
    cwv_mobile_min: float = 0.50
    cwv_lcp_max_ms: float = 4000.0
    cwv_cls_max: float = 0.25
    quick_win_min_impressions: int = 30
    low_ctr_min_impressions: int = 100
    low_ctr_max_pct: float = 1.0
    cannibalization_min_impressions: int = 10
    cannibalization_severity_high: float = 0.6
    cannibalization_severity_medium: float = 0.3
    clicks_warn: int = 500
    clicks_ok: int = 2000
    ctr_warn: float = 2.0
    ctr_ok: float = 4.0
    position_warn: float = 20.0
    position_ok: float = 10.0
    eeat_warn: float = 25.0
    eeat_ok: float = 45.0
    cwv_warn: float = 0.50
    cwv_ok: float = 0.70
    eeat_weak_threshold: float = 0.45
    eeat_action_threshold: float = 0.15


class HreflangLocale(BaseModel):
    hreflang: str
    prefix: str = ""


class TenantConfig(BaseModel):
    tenant_id: str
    name: str
    brand: str
    niche: str
    base_url: str
    shopify_store_domain: str
    product_categories: dict[str, str] = Field(default_factory=dict)
    categories: list[str] = Field(default_factory=list)
    category_labels: dict[str, str] = Field(default_factory=dict)
    category_collections: dict[str, str] = Field(default_factory=dict)
    hreflang_locales: list[HreflangLocale] = Field(default_factory=list)
    pagespeed_urls: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    seo_rules: SeoRules = Field(default_factory=SeoRules)
    alert_thresholds: AlertThresholds = Field(default_factory=AlertThresholds)

    @property
    def domain(self) -> str:
        """Bare domain without scheme (e.g. www.leoniedelacroix.com)."""
        return self.base_url.split("://", 1)[-1].rstrip("/")

    def hreflang_locales_as_tuples(self) -> list[tuple[str, str]]:
        """Return locales as (hreflang, prefix) tuples for backward compat."""
        return [(loc.hreflang, loc.prefix) for loc in self.hreflang_locales]

    def category_for_handle(self, handle: str) -> str:
        """Return category for a product handle, fallback to 'accessoires'."""
        return self.product_categories.get(handle, "accessoires")


def load_tenant(tenant_id: str) -> TenantConfig:
    """Load and validate a tenant config from YAML.

    Args:
        tenant_id: Tenant identifier matching a file in config/tenants/.

    Returns:
        Validated TenantConfig instance.

    Raises:
        FileNotFoundError: If no config file exists for tenant_id.
    """
    path = _CONFIG_DIR / f"{tenant_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No tenant config found at {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return TenantConfig.parse_obj(data)


@lru_cache(maxsize=8)
def get_config(tenant_id: str | None = None) -> TenantConfig:
    """Return the active tenant config (cached per tenant_id).

    Resolves in order: explicit argument → TENANT_ID env var → default.

    Args:
        tenant_id: Override tenant. If None, reads TENANT_ID env var.

    Returns:
        Cached TenantConfig for the resolved tenant.
    """
    resolved = tenant_id or os.getenv("TENANT_ID", _DEFAULT_TENANT)
    return load_tenant(resolved)


def reset_config_cache() -> None:
    """Clear the lru_cache — use in tests to reload config between calls."""
    get_config.cache_clear()
