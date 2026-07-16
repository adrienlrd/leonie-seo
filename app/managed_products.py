"""Merchant-selected "managed products" — the plan-capped list of products
the app works on, replacing the historical take-all-active-products behavior.

Persisted in `shop_config` under `managed_product_ids` (JSON list of Shopify
product GIDs). `None` (never configured) is distinct from `[]`: legacy shops
inherit their last analysis's products as the initial selection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.billing.quotas import product_cap
from app.shop_config_store import get_shop_config, set_shop_config
from app.snapshot.scope import filter_products_by_scope

logger = logging.getLogger(__name__)

_CONFIG_KEY = "managed_product_ids"


class ManagedProductsCapExceeded(Exception):
    """Raised when a selection exceeds the shop plan's product cap."""

    def __init__(self, requested: int, cap: int) -> None:
        self.requested = requested
        self.cap = cap
        super().__init__(f"Selection of {requested} products exceeds plan cap of {cap}")


def get_managed_product_ids(shop: str) -> list[str] | None:
    """Return the selected product IDs, or None if never configured."""
    raw = get_shop_config(shop, _CONFIG_KEY)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("managed_products: invalid JSON stored for %s, ignoring", shop)
        return None
    if not isinstance(parsed, list):
        return None
    return [str(pid) for pid in parsed if pid]


def set_managed_product_ids(shop: str, product_ids: list[str], *, db_path: Path | None = None) -> None:
    """Persist the selection, enforcing the shop plan's product cap."""
    deduped = list(dict.fromkeys(str(pid).strip() for pid in product_ids if pid and str(pid).strip()))
    cap = product_cap(shop, db_path)
    if len(deduped) > cap:
        raise ManagedProductsCapExceeded(len(deduped), cap)
    set_shop_config(shop, _CONFIG_KEY, json.dumps(deduped))


def filter_managed_products(
    shop: str,
    products: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Restrict a snapshot product list to the shop's managed selection.

    - Selection configured → keep only selected IDs (snapshot order), capped.
    - Never configured → migration fallback: inherit the products present in
      the last persisted analysis (persisted as the initial selection so the
      inheritance happens once), else the historical active-scope head-slice.
    """
    cap = product_cap(shop, db_path)
    selected = get_managed_product_ids(shop)

    if selected is None:
        inherited = _ids_from_latest_analysis(shop, db_path=db_path)
        if inherited:
            selected = inherited[:cap]
            try:
                set_managed_product_ids(shop, selected, db_path=db_path)
                logger.info(
                    "managed_products: %s inherited %d products from its last analysis",
                    shop,
                    len(selected),
                )
            except ManagedProductsCapExceeded:  # pragma: no cover — sliced to cap above
                pass
        else:
            return filter_products_by_scope(products, "active")[:cap]

    selected_set = set(selected)
    return [p for p in products if str(p.get("id", "")) in selected_set][:cap]


def filter_snapshot_products(
    shop: str,
    snapshot: dict[str, Any] | None,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Shallow-copy a snapshot with its products restricted to the managed selection.

    The single hook used by every read-only surface (audit, dashboard, GEO,
    llms.txt, blog, crawl) so the whole app only ever sees the merchant's
    selected products. Collections/pages/articles are left untouched.
    """
    if not snapshot:
        return snapshot
    filtered = dict(snapshot)
    filtered["products"] = filter_managed_products(
        shop, snapshot.get("products") or [], db_path=db_path
    )
    return filtered


def _ids_from_latest_analysis(shop: str, *, db_path: Path | None = None) -> list[str]:
    from app.market_analysis.jobs import load_latest_result  # noqa: PLC0415

    result = load_latest_result(shop, db_path=db_path)
    if not result:
        return []
    return [
        str(p.get("product_id") or "")
        for p in result.get("products") or []
        if isinstance(p, dict) and p.get("product_id")
    ]
