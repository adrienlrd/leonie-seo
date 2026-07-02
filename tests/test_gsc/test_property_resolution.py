"""Generic, per-shop GSC property resolution from verified sites (no hardcoded config)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.gsc import client


def _service_with_sites(entries: list[dict]) -> MagicMock:
    service = MagicMock()
    service.sites().list().execute.return_value = {"siteEntry": entries}
    return service


def test_prefers_domain_property() -> None:
    service = _service_with_sites(
        [
            {"siteUrl": "https://www.boutique.com/", "permissionLevel": "siteOwner"},
            {"siteUrl": "sc-domain:boutique.com", "permissionLevel": "siteOwner"},
        ]
    )
    with patch.object(client, "storefront_host", return_value="www.boutique.com"), patch.object(
        client, "set_shop_config"
    ) as set_cfg:
        assert client.resolve_gsc_property("s.myshopify.com", service=service) == "sc-domain:boutique.com"
        set_cfg.assert_called_once_with("s.myshopify.com", "gsc_property", "sc-domain:boutique.com")


def test_falls_back_to_url_prefix_property() -> None:
    service = _service_with_sites(
        [{"siteUrl": "https://www.boutique.com/", "permissionLevel": "siteOwner"}]
    )
    with patch.object(client, "storefront_host", return_value="boutique.com"), patch.object(
        client, "set_shop_config"
    ):
        assert (
            client.resolve_gsc_property("s.myshopify.com", service=service)
            == "https://www.boutique.com/"
        )


def test_skips_unverified_sites() -> None:
    service = _service_with_sites(
        [{"siteUrl": "sc-domain:boutique.com", "permissionLevel": "siteUnverifiedUser"}]
    )
    with patch.object(client, "storefront_host", return_value="boutique.com"), patch.object(
        client, "set_shop_config"
    ) as set_cfg:
        assert client.resolve_gsc_property("s.myshopify.com", service=service) is None
        set_cfg.assert_not_called()


def test_default_site_url_uses_cache_first() -> None:
    with patch.object(client, "get_shop_config", return_value="sc-domain:cached.com"):
        assert client.default_site_url("s.myshopify.com") == "sc-domain:cached.com"


def test_default_site_url_fallback_to_domain_property() -> None:
    with patch.object(client, "get_shop_config", return_value=None), patch.object(
        client, "resolve_gsc_property", return_value=None
    ), patch.object(client, "storefront_host", return_value="boutique.com"):
        assert client.default_site_url("s.myshopify.com") == "sc-domain:boutique.com"
