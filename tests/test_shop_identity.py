"""Generic storefront host/URL resolution from the shop, not hardcoded config."""

from __future__ import annotations

from unittest.mock import patch

from app import shop_identity


def test_host_from_shop_config_cache() -> None:
    with patch.object(shop_identity, "get_shop_config", return_value="boutique.com"):
        assert shop_identity.storefront_host("s.myshopify.com") == "boutique.com"
        assert shop_identity.storefront_base_url("s.myshopify.com") == "https://boutique.com"


def test_host_from_snapshot_when_cache_empty() -> None:
    snapshot = {"shop": {"primaryDomain": {"host": "boutique.com"}}}
    with patch.object(shop_identity, "get_shop_config", return_value=None), patch.object(
        shop_identity, "set_shop_config"
    ) as set_cfg, patch(
        "app.api.snapshot_store.load_snapshot_from_file_or_db", return_value=snapshot
    ):
        assert shop_identity.storefront_host("s.myshopify.com") == "boutique.com"
        set_cfg.assert_called_once_with("s.myshopify.com", "storefront_host", "boutique.com")


def test_fallback_to_myshopify_domain() -> None:
    with patch.object(shop_identity, "get_shop_config", return_value=None), patch.object(
        shop_identity, "set_shop_config"
    ), patch("app.api.snapshot_store.load_snapshot_from_file_or_db", return_value=None):
        assert shop_identity.storefront_host("s.myshopify.com") == "s.myshopify.com"


def test_brand_terms_derived_from_domain() -> None:
    with patch.object(shop_identity, "storefront_host", return_value="www.jolie-boutique.com"):
        assert shop_identity.brand_terms("s.myshopify.com") == frozenset({"jolie"})
    with patch.object(shop_identity, "storefront_host", return_value="acmepets.myshopify.com"):
        assert shop_identity.brand_terms("s.myshopify.com") == frozenset({"acmepets"})


def test_persist_storefront_host_extracts_primary_domain() -> None:
    with patch.object(shop_identity, "set_shop_config") as set_cfg:
        shop_identity.persist_storefront_host(
            "s.myshopify.com", {"primaryDomain": {"host": "boutique.com"}}
        )
        set_cfg.assert_called_once_with("s.myshopify.com", "storefront_host", "boutique.com")
