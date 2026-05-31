"""Deterministic llms.txt and llms-full.txt generator for Shopify catalogs.

This module formats an ``llms.txt`` index file and an ``llms-full.txt`` content
file that comply with the community spec at https://llmstxt.org/.

Design invariants (do not relax without explicit product approval):
- 100% deterministic from the Shopify snapshot + the merchant business profile.
  No LLM call happens here; the output is pure formatting of confirmed data.
- Only pages actually present in the snapshot are listed. Nothing is invented.
- If there is no listable content at all, an explicit error is raised instead of
  publishing an empty shell file.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.geo._shared import (
    POLICY_PATHS,
    absolute_url,
    collection_rows,
    product_description,
    product_rows,
    shop_domain,
    strip_html,
)
from app.snapshot.scope import filter_products_by_scope

SPEC_VERSION = "2024-09"
# The Online Store homepage collection — not a real category, excluded from listings.
_EXCLUDED_COLLECTION_HANDLES = {"frontpage"}
DEFAULT_FULL_BUDGET_BYTES = 500_000
_ONE_LINER_MAX_CHARS = 120
_SUMMARY_MAX_CHARS = 320
_FULL_BODY_MAX_CHARS = 4000


class LlmsTxtGenerationError(ValueError):
    """Raised when the snapshot lacks the minimum data to build llms.txt."""


def content_hash(text: str) -> str:
    """Return a stable sha256 hex digest for an llms.txt payload."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_RAW_CLOSE_RE = re.compile(r"\{%-?\s*endraw\s*-?%\}")


def wrap_liquid_raw(content: str) -> str:
    """Wrap text in a Liquid ``{% raw %}`` block for safe theme-template hosting.

    Shopify serves /llms.txt, /llms-full.txt and /agents.md from theme templates
    (``templates/*.liquid``), which are rendered as Liquid. Any ``{{`` or ``{%``
    coming from merchant product text would otherwise be evaluated. Wrapping the
    whole body in a raw block neutralises that; we first defuse any literal
    ``{% endraw %}`` in the content (any whitespace variant) so it cannot close
    the block early. That substring never appears in real product copy, so the
    rewrite is harmless in practice.
    """
    safe = _RAW_CLOSE_RE.sub("{% endraw_ %}", content)
    return "{% raw %}\n" + safe + "\n{% endraw %}"


def _resolve_shop_name(
    shop: str, snapshot: dict[str, Any], business_profile: dict[str, Any] | None
) -> str:
    if isinstance(business_profile, dict):
        brand = str(business_profile.get("brand_name") or "").strip()
        if brand:
            return brand
    shop_meta = snapshot.get("shop", {}) or {}
    name = str(shop_meta.get("name") or "").strip()
    if name:
        return name
    domain = shop_domain(shop, snapshot)
    if domain:
        return domain
    raise LlmsTxtGenerationError("Cannot resolve a shop name for llms.txt generation.")


def _one_liner(text: str, max_chars: int = _ONE_LINER_MAX_CHARS) -> str:
    cleaned = " ".join(strip_html(text).split())
    if not cleaned:
        return ""
    # Prefer the first sentence so the snippet reads naturally.
    for terminator in (". ", "! ", "? "):
        idx = cleaned.find(terminator)
        if 0 < idx <= max_chars:
            return cleaned[: idx + 1].strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    return f"{truncated}…"


def _collection_description(collection: dict[str, Any]) -> str:
    seo = collection.get("seo") or {}
    seo_desc = str(seo.get("description") or "").strip()
    if seo_desc:
        return _one_liner(seo_desc)
    body = collection.get("body_html") or collection.get("description") or collection.get("body")
    return _one_liner(str(body or ""))


def _summary_line(
    shop_name: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None,
    *,
    product_count: int,
    collection_count: int,
) -> str:
    if isinstance(business_profile, dict):
        niche = str(business_profile.get("niche_summary") or "").strip()
        if niche:
            cleaned = " ".join(strip_html(niche).split())
            if len(cleaned) <= _SUMMARY_MAX_CHARS:
                return cleaned
            return f"{cleaned[:_SUMMARY_MAX_CHARS].rsplit(' ', 1)[0].strip()}…"
    # Deterministic factual fallback built only from snapshot counts.
    parts = [f"{shop_name} is an online store"]
    if product_count:
        parts.append(f"with {product_count} product page{'s' if product_count != 1 else ''}")
    if collection_count:
        joiner = "across" if product_count else "with"
        parts.append(
            f"{joiner} {collection_count} collection{'s' if collection_count != 1 else ''}"
        )
    return " ".join(parts) + "."


def _active_products(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only products that are live on the storefront (ACTIVE + published).

    Drafts, archived and unpublished products (including test duplicates that the
    merchant has unpublished) are excluded, so the AI files mirror what shoppers
    and crawlers actually see — and self-heal when a product is archived.
    """
    return filter_products_by_scope(snapshot.get("products", []), "active")


def _listable_collections(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return catalog collections, excluding the homepage (`frontpage`)."""
    return [
        collection
        for collection in snapshot.get("collections", [])
        if str(collection.get("handle") or "").strip() not in _EXCLUDED_COLLECTION_HANDLES
    ]


def _optional_pages(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    policy_handles = {path.rsplit("/", 1)[-1] for path, _ in POLICY_PATHS}
    for page in snapshot.get("pages", []):
        title = str(page.get("title") or "").strip()
        handle = str(page.get("handle") or "").strip()
        if not title or not handle or handle in policy_handles:
            continue
        rows.append(
            {
                "title": title,
                "path": f"/pages/{handle}",
                "summary": _one_liner(str(page.get("body") or "")),
            }
        )
    rows.sort(key=lambda item: item["title"])
    return rows


def build_llms_txt(
    shop: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None = None,
    *,
    top_products: int = 50,
    top_collections: int = 30,
) -> str:
    """Build a spec-compliant ``llms.txt`` index file.

    Args:
        shop: Shop domain (used as a domain fallback only).
        snapshot: Shopify snapshot (products, collections, pages, shop metadata).
        business_profile: Optional persisted business profile for name + summary.
        top_products: Maximum number of product links to list.
        top_collections: Maximum number of collection links to list.

    Returns:
        The full ``llms.txt`` content as a string.

    Raises:
        LlmsTxtGenerationError: If the snapshot has no listable page.
    """
    domain = shop_domain(shop, snapshot)
    shop_name = _resolve_shop_name(shop, snapshot, business_profile)
    included_products, _ = product_rows(_active_products(snapshot))
    included_collections, _ = collection_rows(_listable_collections(snapshot))
    optional_pages = _optional_pages(snapshot)

    included_products = included_products[:top_products]
    included_collections = included_collections[:top_collections]

    if not included_products and not included_collections and not optional_pages:
        raise LlmsTxtGenerationError(
            "Snapshot contains no product, collection, or page that can be listed in llms.txt."
        )

    product_by_handle = {
        str(p.get("handle") or "").strip(): p for p in _active_products(snapshot)
    }

    summary = _summary_line(
        shop_name,
        snapshot,
        business_profile,
        product_count=len(included_products),
        collection_count=len(included_collections),
    )

    lines = [f"# {shop_name}", "", f"> {summary}", ""]

    lines.append("## Policies")
    for path, title in POLICY_PATHS:
        lines.append(f"- [{title}]({absolute_url(domain, path)})")
    lines.append("")

    if included_collections:
        lines.append("## Collections")
        for row in included_collections:
            desc = _collection_description(
                next(
                    (
                        c
                        for c in _listable_collections(snapshot)
                        if f"/collections/{str(c.get('handle') or '').strip()}" == row["path"]
                    ),
                    {},
                )
            )
            suffix = f": {desc}" if desc else ""
            lines.append(f"- [{row['title']}]({absolute_url(domain, row['path'])}){suffix}")
        lines.append("")

    if included_products:
        lines.append("## Products")
        for row in included_products:
            handle = row["path"].rsplit("/", 1)[-1]
            desc = _one_liner(product_description(product_by_handle.get(handle, {})))
            suffix = f": {desc}" if desc else ""
            lines.append(f"- [{row['title']}]({absolute_url(domain, row['path'])}){suffix}")
        lines.append("")

    if optional_pages:
        lines.append("## Optional")
        for page in optional_pages:
            suffix = f": {page['summary']}" if page["summary"] else ""
            lines.append(f"- [{page['title']}]({absolute_url(domain, page['path'])}){suffix}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _full_sections(
    domain: str,
    snapshot: dict[str, Any],
) -> list[tuple[str, str]]:
    """Return (heading, body) markdown blocks for every listable page."""
    sections: list[tuple[str, str]] = []
    included_products, _ = product_rows(_active_products(snapshot))
    included_collections, _ = collection_rows(_listable_collections(snapshot))
    product_by_handle = {
        str(p.get("handle") or "").strip(): p for p in _active_products(snapshot)
    }

    for row in included_products:
        handle = row["path"].rsplit("/", 1)[-1]
        body = product_description(product_by_handle.get(handle, {}))[:_FULL_BODY_MAX_CHARS]
        heading = f"## {row['title']}\n{absolute_url(domain, row['path'])}"
        sections.append((heading, body))

    for row in included_collections:
        body = _collection_description(
            next(
                (
                    c
                    for c in _listable_collections(snapshot)
                    if f"/collections/{str(c.get('handle') or '').strip()}" == row["path"]
                ),
                {},
            )
        )
        heading = f"## {row['title']}\n{absolute_url(domain, row['path'])}"
        sections.append((heading, body))

    for page in _optional_pages(snapshot):
        body = strip_html(
            next(
                (
                    p.get("body")
                    for p in snapshot.get("pages", [])
                    if f"/pages/{str(p.get('handle') or '').strip()}" == page["path"]
                ),
                "",
            )
            or ""
        )[:_FULL_BODY_MAX_CHARS]
        heading = f"## {page['title']}\n{absolute_url(domain, page['path'])}"
        sections.append((heading, body))

    return sections


def _render_full(
    shop_name: str,
    summary: str,
    sections: list[tuple[str, str]],
    *,
    budget_bytes: int,
) -> tuple[str, int]:
    """Render llms-full.txt within a byte budget. Returns (text, omitted_count)."""
    header = f"# {shop_name}\n\n> {summary}\n"
    blocks: list[str] = []
    running = len(header.encode("utf-8"))
    omitted = 0
    for heading, body in sections:
        block = f"\n{heading}\n\n{body}\n".rstrip() + "\n"
        size = len(block.encode("utf-8"))
        if running + size > budget_bytes and blocks:
            omitted += 1
            continue
        blocks.append(block)
        running += size
    text = header + "".join(blocks)
    return text.rstrip() + "\n", omitted


def build_llms_full_txt(
    shop: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None = None,
    *,
    budget_bytes: int = DEFAULT_FULL_BUDGET_BYTES,
) -> str:
    """Build a spec-compliant ``llms-full.txt`` file within a byte budget.

    Raises:
        LlmsTxtGenerationError: If the snapshot has no listable page.
    """
    text, _ = _build_full_with_omitted(shop, snapshot, business_profile, budget_bytes=budget_bytes)
    return text


def _build_full_with_omitted(
    shop: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None,
    *,
    budget_bytes: int,
) -> tuple[str, int]:
    domain = shop_domain(shop, snapshot)
    shop_name = _resolve_shop_name(shop, snapshot, business_profile)
    sections = _full_sections(domain, snapshot)
    if not sections:
        raise LlmsTxtGenerationError(
            "Snapshot contains no product, collection, or page content for llms-full.txt."
        )
    included_products, _ = product_rows(_active_products(snapshot))
    included_collections, _ = collection_rows(_listable_collections(snapshot))
    summary = _summary_line(
        shop_name,
        snapshot,
        business_profile,
        product_count=len(included_products),
        collection_count=len(included_collections),
    )
    return _render_full(shop_name, summary, sections, budget_bytes=budget_bytes)


def build_agents_md(
    shop: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None = None,
) -> str:
    """Build the ``agents.md`` discovery file.

    Shopify treats ``/agents.md`` as the canonical AI-agent discovery file and
    as the fallback for ``/llms.txt`` / ``/llms-full.txt``. v1 mirrors the
    llms.txt index (same deterministic, spec-style markdown); it can diverge into
    an agents-specific format later without touching callers.

    Raises:
        LlmsTxtGenerationError: If the snapshot has no listable page.
    """
    return build_llms_txt(shop, snapshot, business_profile)


def build_llms_payload(
    shop: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None = None,
    *,
    budget_bytes: int = DEFAULT_FULL_BUDGET_BYTES,
) -> dict[str, Any]:
    """Build the three files plus summary metadata and warnings for the API layer."""
    llms_txt = build_llms_txt(shop, snapshot, business_profile)
    agents_md = build_agents_md(shop, snapshot, business_profile)
    llms_full_txt, omitted = _build_full_with_omitted(
        shop, snapshot, business_profile, budget_bytes=budget_bytes
    )
    included_products, _ = product_rows(_active_products(snapshot))
    included_collections, _ = collection_rows(_listable_collections(snapshot))
    optional_pages = _optional_pages(snapshot)

    warnings: list[str] = []
    if not included_products:
        warnings.append("No product page is ready enough to list in llms.txt.")
    if not included_collections:
        warnings.append("No collection could be listed from the current snapshot.")
    if omitted:
        warnings.append(
            f"{omitted} page(s) were omitted from llms-full.txt to stay within the size budget."
        )

    return {
        "spec_version": SPEC_VERSION,
        "domain": shop_domain(shop, snapshot),
        "llms_txt": llms_txt,
        "llms_full_txt": llms_full_txt,
        "agents_md": agents_md,
        "content_hash": content_hash(llms_txt),
        "full_content_hash": content_hash(llms_full_txt),
        "agents_content_hash": content_hash(agents_md),
        "summary": {
            "product_pages": len(included_products),
            "collection_pages": len(included_collections),
            "optional_pages": len(optional_pages),
            "policy_pages": len(POLICY_PATHS),
            "full_bytes": len(llms_full_txt.encode("utf-8")),
            "omitted_full_pages": omitted,
            "dry_run": True,
        },
        "warnings": warnings,
    }
