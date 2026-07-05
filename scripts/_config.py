"""Tenant and niche configuration loaders."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_CONFIG_DIR = Path(__file__).parent.parent / "config" / "tenants"
_NICHES_DIR = Path(__file__).parent.parent / "config" / "niches"


class SeoRules(BaseModel):
    title_min_chars: int = 50
    title_max_chars: int = 65
    description_min_chars: int = 120
    description_max_chars: int = 155
    description_min_words: int = 150
    min_alt_text_length: int = 10


class AlertThresholds(BaseModel):
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
    # Per-tenant analytics + locale (added 2026-05-12 — multi-tenant readiness)
    locale: str = "fr-FR"
    currency: str = "EUR"
    ga4_property_id: str | None = None  # e.g. "properties/459014688"
    gsc_property: str | None = None  # e.g. "sc-domain:example.com"
    product_categories: dict[str, str] = Field(default_factory=dict)
    categories: list[str] = Field(default_factory=list)
    category_labels: dict[str, str] = Field(default_factory=dict)
    category_collections: dict[str, str] = Field(default_factory=dict)
    hreflang_locales: list[HreflangLocale] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    seo_rules: SeoRules = Field(default_factory=SeoRules)
    alert_thresholds: AlertThresholds = Field(default_factory=AlertThresholds)

    @property
    def domain(self) -> str:
        """Bare domain without scheme (e.g. www.example.com)."""
        return self.base_url.split("://", 1)[-1].rstrip("/")

    def hreflang_locales_as_tuples(self) -> list[tuple[str, str]]:
        """Return locales as (hreflang, prefix) tuples for backward compat."""
        return [(loc.hreflang, loc.prefix) for loc in self.hreflang_locales]

    def category_for_handle(self, handle: str) -> str:
        """Return category for a product handle, fallback to 'accessoires'."""
        return self.product_categories.get(handle, "accessoires")


# ── Niche models ──────────────────────────────────────────────────────────


class NicheSignals(BaseModel):
    premium: list[str] = Field(default_factory=list)
    eeat: list[str] = Field(default_factory=list)
    longtail: list[str] = Field(default_factory=list)
    category: dict[str, list[str]] = Field(default_factory=dict)


class NicheEeatDimensions(BaseModel):
    experience: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
    authority: list[str] = Field(default_factory=list)
    trust: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "experience": 0.20,
            "expertise": 0.30,
            "authority": 0.25,
            "trust": 0.25,
        }
    )


class NicheBlogTemplate(BaseModel):
    h2s: list[str] = Field(default_factory=list)
    intent: str = ""
    target_length: str = "800–1 000 mots"
    eeat_angle: str = ""


class NicheConfig(BaseModel):
    niche_id: str
    label: str
    language: str = "fr"
    market: str = "FR"
    maturity: str = "production"
    scope_note: str = ""
    signals: NicheSignals = Field(default_factory=NicheSignals)
    eeat_dimensions: NicheEeatDimensions = Field(default_factory=NicheEeatDimensions)
    faq_templates: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    blog_templates: dict[str, NicheBlogTemplate] = Field(default_factory=dict)


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
    return TenantConfig.model_validate(data)


@lru_cache(maxsize=8)
def get_config(tenant_id: str | None = None) -> TenantConfig:
    """Return the active tenant config (cached per tenant_id).

    Resolves in order: explicit argument → TENANT_ID env var. No default tenant:
    the CLI must be pointed at a tenant explicitly (the embedded app never uses
    this — it resolves shop identity generically from Shopify).

    Args:
        tenant_id: Override tenant. If None, reads TENANT_ID env var.

    Returns:
        Cached TenantConfig for the resolved tenant.

    Raises:
        RuntimeError: If neither an argument nor TENANT_ID is provided.
    """
    resolved = tenant_id or os.getenv("TENANT_ID")
    if not resolved:
        raise RuntimeError("No tenant specified: pass a tenant_id or set TENANT_ID.")
    return load_tenant(resolved)


@lru_cache(maxsize=8)
def load_niche(niche_id: str) -> NicheConfig:
    """Load and validate a niche config from YAML.

    Args:
        niche_id: Niche identifier matching a file in config/niches/.

    Returns:
        Validated NicheConfig instance.

    Raises:
        FileNotFoundError: If no config file exists for niche_id.
    """
    path = _NICHES_DIR / f"{niche_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No niche config found at {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return NicheConfig.model_validate(data)


def reset_config_cache() -> None:
    """Clear tenant and niche lru_caches — use in tests to reload between calls."""
    get_config.cache_clear()
    load_niche.cache_clear()
