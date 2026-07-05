"""Tests for scripts._config — tenant config loader.

The embedded app resolves shop identity generically from Shopify; the CLI still
supports explicit tenant YAML. These tests build a synthetic tenant on the fly
so they never depend on any real merchant config.
"""

import pytest

from scripts._config import (
    get_config,
    load_tenant,
    reset_config_cache,
)

_TENANT_YAML = """\
tenant_id: acme
name: "Acme Pets"
brand: "Acme Pets"
niche: pet_accessories_fr
base_url: "https://www.acme-pets.example"
shopify_store_domain: "acme-pets.myshopify.com"
locale: fr-FR
currency: EUR
ga4_property_id: "properties/123456789"
gsc_property: "sc-domain:acme-pets.example"
categories:
  - vetements_chien
  - fontaines
  - accessoires
  - jouets
  - couchages
product_categories:
  labreuvoir: fontaines
  le-pardessus-pour-chien: vetements_chien
hreflang_locales:
  - hreflang: fr-FR
    prefix: ""
  - hreflang: fr-BE
    prefix: "/fr-be"
  - hreflang: fr-CH
    prefix: "/fr-ch"
  - hreflang: fr-CA
    prefix: "/fr-ca"
"""


@pytest.fixture(autouse=True)
def tenant_dir(tmp_path, monkeypatch):
    """Point the loader at a synthetic tenant dir and clear caches around it."""
    tenants_dir = tmp_path / "tenants"
    tenants_dir.mkdir()
    (tenants_dir / "acme.yaml").write_text(_TENANT_YAML)
    monkeypatch.setattr("scripts._config._CONFIG_DIR", tenants_dir)
    reset_config_cache()
    yield tenants_dir
    reset_config_cache()


# ── load_tenant ────────────────────────────────────────────────────────────


def test_load_tenant_reads_fields():
    cfg = load_tenant("acme")
    assert cfg.tenant_id == "acme"
    assert cfg.brand == "Acme Pets"
    assert cfg.base_url == "https://www.acme-pets.example"


def test_load_tenant_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_tenant("nonexistent_tenant")


def test_load_tenant_has_categories():
    cfg = load_tenant("acme")
    assert "vetements_chien" in cfg.categories
    assert "fontaines" in cfg.categories
    assert len(cfg.categories) == 5


def test_load_tenant_has_product_categories():
    cfg = load_tenant("acme")
    assert cfg.product_categories["labreuvoir"] == "fontaines"
    assert cfg.product_categories["le-pardessus-pour-chien"] == "vetements_chien"


def test_load_tenant_has_hreflang_locales():
    cfg = load_tenant("acme")
    assert len(cfg.hreflang_locales) == 4
    hreflangs = [loc.hreflang for loc in cfg.hreflang_locales]
    assert "fr-FR" in hreflangs
    assert "fr-BE" in hreflangs


# ── Multi-tenant analytics + locale ──────────────────────────────────────


def test_load_tenant_has_locale_and_currency():
    cfg = load_tenant("acme")
    assert cfg.locale == "fr-FR"
    assert cfg.currency == "EUR"


def test_load_tenant_has_ga4_property_id():
    cfg = load_tenant("acme")
    assert cfg.ga4_property_id == "properties/123456789"


def test_load_tenant_has_gsc_property():
    cfg = load_tenant("acme")
    assert cfg.gsc_property == "sc-domain:acme-pets.example"


def test_tenant_config_locale_defaults_when_omitted(tenant_dir):
    """Backward compat: a tenant YAML without locale/currency/ga4 still loads."""
    minimal_yaml = """\
tenant_id: minimal
name: "Minimal"
brand: "Minimal"
niche: pet_accessories_fr
base_url: "https://minimal.example.com"
shopify_store_domain: "minimal.myshopify.com"
"""
    (tenant_dir / "minimal.yaml").write_text(minimal_yaml)
    reset_config_cache()

    cfg = load_tenant("minimal")
    assert cfg.locale == "fr-FR"  # default
    assert cfg.currency == "EUR"  # default
    assert cfg.ga4_property_id is None
    assert cfg.gsc_property is None


def test_load_tenant_seo_rules():
    cfg = load_tenant("acme")
    assert cfg.seo_rules.title_min_chars == 50
    assert cfg.seo_rules.title_max_chars == 65
    assert cfg.seo_rules.description_min_chars == 120


def test_load_tenant_alert_thresholds():
    cfg = load_tenant("acme")
    assert cfg.alert_thresholds.quick_win_min_impressions == 30
    assert cfg.alert_thresholds.eeat_weak_threshold == 0.45


# ── TenantConfig helpers ───────────────────────────────────────────────────


def test_domain_property_strips_scheme():
    cfg = load_tenant("acme")
    assert cfg.domain == "www.acme-pets.example"
    assert "https://" not in cfg.domain


def test_category_for_handle_known():
    cfg = load_tenant("acme")
    assert cfg.category_for_handle("labreuvoir") == "fontaines"
    assert cfg.category_for_handle("griffoir-dimitrios") == "accessoires"


def test_category_for_handle_unknown_fallback():
    cfg = load_tenant("acme")
    assert cfg.category_for_handle("unknown-product") == "accessoires"


def test_hreflang_locales_as_tuples():
    cfg = load_tenant("acme")
    tuples = cfg.hreflang_locales_as_tuples()
    assert isinstance(tuples[0], tuple)
    assert tuples[0][0] == "fr-FR"
    be = next(t for t in tuples if t[0] == "fr-BE")
    assert be[1] == "/fr-be"


# ── get_config ─────────────────────────────────────────────────────────────


def test_get_config_requires_tenant(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    with pytest.raises(RuntimeError, match="No tenant specified"):
        get_config()


def test_get_config_explicit_tenant():
    cfg = get_config("acme")
    assert cfg.tenant_id == "acme"


def test_get_config_cached():
    cfg1 = get_config("acme")
    cfg2 = get_config("acme")
    assert cfg1 is cfg2


def test_get_config_env_var(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "acme")
    cfg = get_config()
    assert cfg.tenant_id == "acme"
