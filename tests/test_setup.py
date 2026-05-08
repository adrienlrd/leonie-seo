"""Tests for scripts.setup — tenant setup wizard."""

from __future__ import annotations

import click
import pytest
import yaml
from click.testing import CliRunner

from scripts._config import TenantConfig, reset_config_cache
from scripts.setup import (
    cli,
    generate_yaml,
    list_niches,
    list_tenants,
    update_env,
    validate_base_url,
    validate_shopify_domain,
    validate_tenant_id,
)


@pytest.fixture(autouse=True)
def clear_cache():
    reset_config_cache()
    yield
    reset_config_cache()


# ── validate_tenant_id ────────────────────────────────────────────────────


def test_validate_tenant_id_accepts_valid():
    assert validate_tenant_id("maboutique-fr") == "maboutique-fr"
    assert validate_tenant_id("shop123") == "shop123"
    assert validate_tenant_id("a_b_c") == "a_b_c"


def test_validate_tenant_id_rejects_spaces():
    with pytest.raises(click.BadParameter):
        validate_tenant_id("ma boutique")


def test_validate_tenant_id_rejects_uppercase():
    with pytest.raises(click.BadParameter):
        validate_tenant_id("MaBoutique")


def test_validate_tenant_id_rejects_leading_hyphen():
    with pytest.raises(click.BadParameter):
        validate_tenant_id("-maboutique")


# ── validate_base_url ─────────────────────────────────────────────────────


def test_validate_base_url_accepts_https():
    assert validate_base_url("https://www.maboutique.com") == "https://www.maboutique.com"


def test_validate_base_url_strips_trailing_slash():
    assert validate_base_url("https://www.maboutique.com/") == "https://www.maboutique.com"


def test_validate_base_url_rejects_http():
    with pytest.raises(click.BadParameter):
        validate_base_url("http://www.maboutique.com")


def test_validate_base_url_rejects_missing_scheme():
    with pytest.raises(click.BadParameter):
        validate_base_url("www.maboutique.com")


# ── validate_shopify_domain ───────────────────────────────────────────────


def test_validate_shopify_domain_accepts_valid():
    assert validate_shopify_domain("maboutique.myshopify.com") == "maboutique.myshopify.com"


def test_validate_shopify_domain_rejects_custom_domain():
    with pytest.raises(click.BadParameter):
        validate_shopify_domain("www.maboutique.com")


# ── generate_yaml ─────────────────────────────────────────────────────────


def test_generate_yaml_produces_valid_tenant_config():
    content = generate_yaml(
        tenant_id="testshop",
        brand="Test Shop",
        base_url="https://www.testshop.com",
        shopify_store_domain="testshop.myshopify.com",
        niche="pet_accessories_fr",
    )
    data = yaml.safe_load(content)
    cfg = TenantConfig.parse_obj(data)
    assert cfg.tenant_id == "testshop"
    assert cfg.brand == "Test Shop"
    assert cfg.base_url == "https://www.testshop.com"
    assert cfg.shopify_store_domain == "testshop.myshopify.com"
    assert cfg.niche == "pet_accessories_fr"


def test_generate_yaml_includes_homepage_in_pagespeed_urls():
    content = generate_yaml("t", "T", "https://www.t.com", "t.myshopify.com", "generic")
    data = yaml.safe_load(content)
    assert "https://www.t.com" in data["pagespeed_urls"]


def test_generate_yaml_default_seo_rules():
    content = generate_yaml("t", "T", "https://www.t.com", "t.myshopify.com", "generic")
    data = yaml.safe_load(content)
    assert data["seo_rules"]["title_min_chars"] == 50
    assert data["seo_rules"]["title_max_chars"] == 65


# ── update_env ────────────────────────────────────────────────────────────


def test_update_env_creates_file(tmp_path):
    env_file = tmp_path / ".env"
    update_env("newshop", env_path=env_file)
    assert "TENANT_ID=newshop" in env_file.read_text()


def test_update_env_updates_existing_line(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SHOPIFY_ACCESS_TOKEN=abc\nTENANT_ID=oldshop\n")
    update_env("newshop", env_path=env_file)
    content = env_file.read_text()
    assert "TENANT_ID=newshop" in content
    assert "TENANT_ID=oldshop" not in content
    assert "SHOPIFY_ACCESS_TOKEN=abc" in content


def test_update_env_appends_if_missing(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SHOPIFY_ACCESS_TOKEN=abc\n")
    update_env("newshop", env_path=env_file)
    content = env_file.read_text()
    assert "TENANT_ID=newshop" in content
    assert "SHOPIFY_ACCESS_TOKEN=abc" in content


# ── list_tenants / list_niches ────────────────────────────────────────────


def test_list_tenants_includes_leoniedelacroix():
    tenants = list_tenants()
    ids = [t["tenant_id"] for t in tenants]
    assert "leoniedelacroix" in ids


def test_list_tenants_returns_domain():
    tenants = list_tenants()
    ld = next(t for t in tenants if t["tenant_id"] == "leoniedelacroix")
    assert "leoniedelacroix.com" in ld["domain"]


def test_list_niches_includes_pet_accessories():
    niches = list_niches()
    assert "pet_accessories_fr" in niches


# ── CLI commands ──────────────────────────────────────────────────────────


def test_cmd_list_shows_leoniedelacroix():
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "leoniedelacroix" in result.output


def test_cmd_check_loads_default_tenant():
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--tenant", "leoniedelacroix"])
    assert result.exit_code == 0
    assert "leoniedelacroix" in result.output


def test_cmd_check_unknown_tenant_exits_cleanly():
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--tenant", "tenant-inexistant"])
    assert result.exit_code == 0
    assert "✗" in result.output or "No tenant" in result.output


def test_cmd_init_creates_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tenants_dir = tmp_path / "config" / "tenants"
    niches_dir = tmp_path / "config" / "niches"
    tenants_dir.mkdir(parents=True)
    niches_dir.mkdir(parents=True)
    (niches_dir / "pet_accessories_fr.yaml").write_text("niche_id: pet_accessories_fr\n")

    import scripts.setup as setup_mod

    monkeypatch.setattr(setup_mod, "_TENANTS_DIR", tenants_dir)
    monkeypatch.setattr(setup_mod, "_NICHES_DIR", niches_dir)
    monkeypatch.setattr(setup_mod, "_ENV_PATH", tmp_path / ".env")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["init"],
        input=(
            "testshop\n"  # tenant_id
            "Test Brand\n"  # brand
            "https://www.test.com\n"  # base_url
            "testshop.myshopify.com\n"  # shopify domain
            "pet_accessories_fr\n"  # niche
            "n\n"  # don't update .env
        ),
    )
    assert result.exit_code == 0, result.output
    assert (tenants_dir / "testshop.yaml").exists()
    data = yaml.safe_load((tenants_dir / "testshop.yaml").read_text())
    assert data["tenant_id"] == "testshop"
    assert data["brand"] == "Test Brand"
