"""Generic per-shop identity resolution.

Single source of truth for a shop's public storefront host/URL. The host is the
real Shopify primary domain (custom domain when configured, otherwise the
``*.myshopify.com`` domain). It is resolved generically from the shop itself —
never from hardcoded tenant/env configuration — so every feature works for any
merchant.

Resolution order:
1. ``shop_config`` cache (``storefront_host``), persisted at snapshot time.
2. The latest snapshot's ``shop.primaryDomain`` (file snapshot carries the shop
   object; the DB snapshot does not).
3. Fallback to the ``*.myshopify.com`` auth domain.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.shop_config_store import get_shop_config, set_shop_config

_STOREFRONT_HOST_KEY = "storefront_host"
_PROJECT_ROOT = Path(__file__).parents[1]
_RAW_DIR = _PROJECT_ROOT / "data" / "raw"
_GENERIC_HOST_TOKENS = {"shop", "store", "boutique", "myshopify", "www"}


def _clean_host(value: str) -> str:
    """Strip scheme and trailing slash from a domain-ish value."""
    return value.strip().replace("https://", "").replace("http://", "").strip("/")


def _host_from_shop_object(shop_meta: dict) -> str | None:
    primary = shop_meta.get("primaryDomain") or {}
    candidate = (
        primary.get("host")
        or primary.get("url")
        or shop_meta.get("myshopifyDomain")
        or shop_meta.get("domain")
    )
    host = _clean_host(str(candidate or ""))
    return host or None


def persist_storefront_host(shop: str, shop_meta: dict) -> None:
    """Cache the shop's primary domain host from a fresh snapshot's shop object."""
    host = _host_from_shop_object(shop_meta)
    if host:
        set_shop_config(shop, _STOREFRONT_HOST_KEY, host)


def storefront_host(shop: str) -> str:
    """Return the shop's public storefront host (no scheme, no trailing slash)."""
    cached = get_shop_config(shop, _STOREFRONT_HOST_KEY)
    if cached:
        return _clean_host(cached)

    host = _host_from_snapshot(shop)
    if host:
        set_shop_config(shop, _STOREFRONT_HOST_KEY, host)
        return host

    return _clean_host(shop)


def storefront_base_url(shop: str) -> str:
    """Return the shop's public storefront base URL (``https://host``, no trailing slash)."""
    return f"https://{storefront_host(shop)}"


def brand_terms(shop: str) -> frozenset[str]:
    """Derive brand tokens from the shop's own domain, generically (no hardcoding).

    Used to treat brand queries as navigational. ``mystore.myshopify.com`` →
    ``{"mystore"}`` ; ``www.jolie-boutique.com`` → ``{"jolie"}``.
    """
    host = storefront_host(shop).removeprefix("www.")
    label = host.split(".")[0]
    words = re.split(r"[^a-z0-9]+", label.lower())
    return frozenset(w for w in words if len(w) >= 3 and w not in _GENERIC_HOST_TOKENS)


def _host_from_snapshot(shop: str) -> str | None:
    from app.api.snapshot_store import load_snapshot_from_file_or_db  # noqa: PLC0415

    snapshot_path = _RAW_DIR / shop / "shopify_snapshot.json"
    data = load_snapshot_from_file_or_db(shop, snapshot_path)
    if not data:
        return None
    return _host_from_shop_object(data.get("shop") or {})
