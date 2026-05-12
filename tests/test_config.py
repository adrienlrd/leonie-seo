"""Tests for scripts._config — tenant config loader."""

import pytest

from scripts._config import (
    get_config,
    load_tenant,
    reset_config_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    reset_config_cache()
    yield
    reset_config_cache()


# ── load_tenant ────────────────────────────────────────────────────────────


def test_load_tenant_leoniedelacroix():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.tenant_id == "leoniedelacroix"
    assert cfg.brand == "Léonie Delacroix"
    assert cfg.base_url == "https://www.leoniedelacroix.com"


def test_load_tenant_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_tenant("nonexistent_tenant")


def test_load_tenant_has_categories():
    cfg = load_tenant("leoniedelacroix")
    assert "vetements_chien" in cfg.categories
    assert "fontaines" in cfg.categories
    assert len(cfg.categories) == 5


def test_load_tenant_has_product_categories():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.product_categories["labreuvoir"] == "fontaines"
    assert cfg.product_categories["le-pardessus-pour-chien"] == "vetements_chien"


def test_load_tenant_has_hreflang_locales():
    cfg = load_tenant("leoniedelacroix")
    assert len(cfg.hreflang_locales) == 4
    hreflangs = [loc.hreflang for loc in cfg.hreflang_locales]
    assert "fr-FR" in hreflangs
    assert "fr-BE" in hreflangs


def test_load_tenant_has_pagespeed_urls():
    cfg = load_tenant("leoniedelacroix")
    assert len(cfg.pagespeed_urls) >= 3
    assert any("leoniedelacroix.com" in u for u in cfg.pagespeed_urls)


# ── Multi-tenant analytics + locale (added 2026-05-12) ───────────────────


def test_load_tenant_has_locale_and_currency():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.locale == "fr-FR"
    assert cfg.currency == "EUR"


def test_load_tenant_has_ga4_property_id():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.ga4_property_id == "properties/459014688"


def test_load_tenant_has_gsc_property():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.gsc_property == "sc-domain:leoniedelacroix.com"


def test_tenant_config_locale_defaults_when_omitted(tmp_path, monkeypatch):
    """Backward compat: a tenant YAML without locale/currency/ga4 still loads."""
    tenants_dir = tmp_path / "tenants"
    tenants_dir.mkdir()
    minimal_yaml = """\
tenant_id: minimal
name: "Minimal"
brand: "Minimal"
niche: pet_accessories_fr
base_url: "https://minimal.example.com"
shopify_store_domain: "minimal.myshopify.com"
"""
    (tenants_dir / "minimal.yaml").write_text(minimal_yaml)
    monkeypatch.setattr("scripts._config._CONFIG_DIR", tenants_dir)
    reset_config_cache()

    cfg = load_tenant("minimal")
    assert cfg.locale == "fr-FR"  # default
    assert cfg.currency == "EUR"  # default
    assert cfg.ga4_property_id is None
    assert cfg.gsc_property is None


def test_load_tenant_seo_rules():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.seo_rules.title_min_chars == 50
    assert cfg.seo_rules.title_max_chars == 65
    assert cfg.seo_rules.description_min_chars == 120


def test_load_tenant_alert_thresholds():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.alert_thresholds.cwv_mobile_min == 0.50
    assert cfg.alert_thresholds.eeat_weak_threshold == 0.45


# ── TenantConfig helpers ───────────────────────────────────────────────────


def test_domain_property_strips_scheme():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.domain == "www.leoniedelacroix.com"
    assert "https://" not in cfg.domain


def test_category_for_handle_known():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.category_for_handle("labreuvoir") == "fontaines"
    assert cfg.category_for_handle("griffoir-dimitrios") == "accessoires"


def test_category_for_handle_unknown_fallback():
    cfg = load_tenant("leoniedelacroix")
    assert cfg.category_for_handle("unknown-product") == "accessoires"


def test_hreflang_locales_as_tuples():
    cfg = load_tenant("leoniedelacroix")
    tuples = cfg.hreflang_locales_as_tuples()
    assert isinstance(tuples[0], tuple)
    assert tuples[0][0] == "fr-FR"
    be = next(t for t in tuples if t[0] == "fr-BE")
    assert be[1] == "/fr-be"


# ── get_config ─────────────────────────────────────────────────────────────


def test_get_config_defaults_to_leoniedelacroix(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    cfg = get_config()
    assert cfg.tenant_id == "leoniedelacroix"


def test_get_config_explicit_tenant():
    cfg = get_config("leoniedelacroix")
    assert cfg.tenant_id == "leoniedelacroix"


def test_get_config_cached():
    cfg1 = get_config("leoniedelacroix")
    cfg2 = get_config("leoniedelacroix")
    assert cfg1 is cfg2


def test_get_config_env_var(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "leoniedelacroix")
    cfg = get_config()
    assert cfg.tenant_id == "leoniedelacroix"
