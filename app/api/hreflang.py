"""Hreflang / international SEO — market configuration, tag preview, issue detection."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.shop_config_store import get_shop_config, set_shop_config
from app.tenant_config import find_tenant_by_shop_domain

router = APIRouter(prefix="/api", tags=["hreflang"])

_MARKETS_KEY = "hreflang_markets"

# BCP-47 locale pattern: fr, fr-FR, fr-BE, en-US …
_LOCALE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class HreflangMarket(BaseModel):
    locale: str  # BCP-47 e.g. "fr-FR"
    url_prefix: str  # e.g. "" (primary) or "/fr-be" or "/en-gb"
    primary: bool = False

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str) -> str:
        if not _LOCALE_RE.match(v):
            raise ValueError(f"Invalid BCP-47 locale: {v!r}. Expected format: fr, fr-FR, en-US")
        return v

    @field_validator("url_prefix")
    @classmethod
    def validate_prefix(cls, v: str) -> str:
        v = v.strip()
        if v and not v.startswith("/"):
            raise ValueError("url_prefix must start with '/' or be empty (primary market)")
        return v.rstrip("/")


class HreflangSettings(BaseModel):
    markets: list[HreflangMarket]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_markets(shop: str) -> list[dict]:
    raw = get_shop_config(shop, _MARKETS_KEY)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _save_markets(shop: str, markets: list[dict]) -> None:
    set_shop_config(shop, _MARKETS_KEY, json.dumps(markets))


def _base_url(shop: str) -> str:
    tenant = find_tenant_by_shop_domain(shop)
    if tenant and tenant.base_url:
        return tenant.base_url.rstrip("/")
    return f"https://{shop}".rstrip("/")


def _page_urls(base: str, prefix: str, snapshot: dict[str, Any]) -> list[dict[str, str]]:
    """Return canonical page descriptors for homepage, products, and collections."""
    pages: list[dict[str, str]] = [{"type": "home", "path": "/"}]
    for p in (snapshot.get("products") or [])[:10]:
        handle = (p.get("handle") or "").strip()
        if handle:
            pages.append({"type": "product", "path": f"/products/{handle}"})
    for c in (snapshot.get("collections") or [])[:5]:
        handle = (c.get("handle") or "").strip()
        if handle:
            pages.append({"type": "collection", "path": f"/collections/{handle}"})
    return pages


def _generate_tags(
    page_path: str,
    base_url: str,
    markets: list[dict],
) -> list[dict[str, str]]:
    """Generate hreflang link tags for one page path across all markets."""
    tags: list[dict[str, str]] = []
    primary_href: str | None = None

    for m in markets:
        prefix = (m.get("url_prefix") or "").rstrip("/")
        href = f"{base_url}{prefix}{page_path}"
        tags.append({"hreflang": m["locale"], "href": href})
        if m.get("primary"):
            primary_href = href

    if primary_href:
        tags.append({"hreflang": "x-default", "href": primary_href})

    return tags


def _detect_issues(markets: list[dict]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    if not markets:
        issues.append({"code": "no_markets", "severity": "info",
                        "message": "Aucun marché configuré. Hreflang non actif."})
        return issues

    primaries = [m for m in markets if m.get("primary")]
    if not primaries:
        issues.append({"code": "no_primary", "severity": "error",
                        "message": "Aucun marché principal défini. La balise x-default sera absente."})
    if len(primaries) > 1:
        issues.append({"code": "multiple_primary", "severity": "error",
                        "message": f"{len(primaries)} marchés marqués comme principal. Un seul doit l'être."})

    locales = [m["locale"] for m in markets]
    if len(locales) != len(set(locales)):
        issues.append({"code": "duplicate_locale", "severity": "error",
                        "message": "Locale dupliquée — chaque locale ne doit apparaître qu'une fois."})

    prefixes = [m.get("url_prefix") or "" for m in markets]
    non_primary_empty = [
        m["locale"] for m in markets
        if not m.get("primary") and not (m.get("url_prefix") or "").strip()
    ]
    if non_primary_empty:
        issues.append({"code": "empty_prefix", "severity": "warning",
                        "message": f"Marchés sans préfixe URL : {non_primary_empty}. "
                                    "Seul le marché principal peut avoir un préfixe vide."})

    if len(set(prefixes)) != len(prefixes):
        issues.append({"code": "duplicate_prefix", "severity": "error",
                        "message": "Préfixe URL dupliqué entre plusieurs marchés."})

    if len(markets) == 1:
        issues.append({"code": "single_market", "severity": "info",
                        "message": "Un seul marché — hreflang n'apporte pas de valeur avec une seule locale."})

    return issues


def _tags_to_html(tags: list[dict[str, str]]) -> str:
    return "\n".join(
        f'<link rel="alternate" hreflang="{t["hreflang"]}" href="{t["href"]}" />'
        for t in tags
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/hreflang/status")
async def get_hreflang_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return hreflang configuration status and issue count for a shop.

    Args:
        shop: Shopify shop domain.
    """
    markets = _load_markets(ctx.shop)
    issues = _detect_issues(markets)
    errors = [i for i in issues if i["severity"] == "error"]
    return {
        "shop": ctx.shop,
        "configured": len(markets) > 0,
        "markets_count": len(markets),
        "markets": markets,
        "issues_count": len(issues),
        "error_count": len(errors),
        "ready": len(markets) > 1 and not errors,
    }


@router.post("/shops/{shop}/hreflang/settings")
async def save_hreflang_settings(
    shop: str,
    body: HreflangSettings,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Persist hreflang market configuration for a shop.

    Args:
        shop: Shopify shop domain.
        body: List of markets with locale, url_prefix, and primary flag.
    """
    markets = [m.model_dump() for m in body.markets]
    _save_markets(ctx.shop, markets)
    issues = _detect_issues(markets)
    return {
        "shop": ctx.shop,
        "saved": True,
        "markets_count": len(markets),
        "issues": issues,
    }


@router.get("/shops/{shop}/hreflang/preview")
async def get_hreflang_preview(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    max_pages: int = 5,
) -> dict:
    """Generate hreflang tag previews for homepage, products and collections.

    Args:
        shop: Shopify shop domain.
        max_pages: Maximum number of pages to preview (default 5).
    """
    markets = _load_markets(ctx.shop)
    issues = _detect_issues(markets)

    if not markets:
        return {
            "shop": ctx.shop,
            "available": False,
            "message": "Configurez au moins un marché pour prévisualiser les balises hreflang.",
            "pages": [],
            "issues": issues,
        }

    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    base = _base_url(ctx.shop)
    page_descriptors = _page_urls(base, "", snapshot or {})[:max_pages]

    pages = []
    for desc in page_descriptors:
        tags = _generate_tags(desc["path"], base, markets)
        pages.append({
            "type": desc["type"],
            "path": desc["path"],
            "url": f"{base}{desc['path']}",
            "tags": tags,
            "html": _tags_to_html(tags),
        })

    return {
        "shop": ctx.shop,
        "available": True,
        "base_url": base,
        "markets_count": len(markets),
        "pages": pages,
        "issues": issues,
    }


@router.delete("/shops/{shop}/hreflang/settings")
async def delete_hreflang_settings(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Remove hreflang configuration for a shop.

    Args:
        shop: Shopify shop domain.
    """
    from app.shop_config_store import delete_shop_config  # noqa: PLC0415

    delete_shop_config(ctx.shop, _MARKETS_KEY)
    return {"shop": ctx.shop, "deleted": True}
