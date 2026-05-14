"""Job handler registry.

Register a handler with the @register("queue_name") decorator.
Handlers are async callables: async (payload: dict, shop: str | None) -> dict.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

_HANDLERS: dict[str, Callable[[dict, str | None], Awaitable[dict]]] = {}

HandlerFn = Callable[[dict, str | None], Awaitable[dict]]


def register(queue: str) -> Callable[[HandlerFn], HandlerFn]:
    """Decorator that registers a handler for a named queue."""

    def decorator(fn: HandlerFn) -> HandlerFn:
        _HANDLERS[queue] = fn
        return fn

    return decorator


def get_handler(queue: str) -> HandlerFn | None:
    """Return the handler for a queue, or None if not registered."""
    return _HANDLERS.get(queue)


def registered_queues() -> list[str]:
    """Return the names of all registered queues."""
    return list(_HANDLERS.keys())


# ── Built-in handlers ─────────────────────────────────────────────────────────


@register("seo_audit")
async def handle_seo_audit(payload: dict, shop: str | None) -> dict:
    """Run a read-only Shopify catalog crawl for a shop.

    Expected payload keys:
        shop (str): Shopify shop domain
        access_token (str): Shopify Admin API token from the embedded app session
    """
    import asyncio

    from app.jobs.audit_snapshot import crawl_shopify_catalog_for_job

    if not shop:
        raise ValueError("shop is required for seo_audit")

    access_token = str(payload.get("access_token") or "")
    if not access_token:
        from app.oauth.token_store import get_token

        record = get_token(shop)
        access_token = str(record.get("access_token", "")) if record else ""
    if not access_token:
        raise ValueError("access_token is required for seo_audit")

    return await asyncio.to_thread(crawl_shopify_catalog_for_job, shop, access_token)


@register("meta_generation")
async def handle_meta_generation(payload: dict, shop: str | None) -> dict:
    """Generate meta titles + descriptions for Shopify products via LLM.

    Expected payload keys:
        products (list[dict]): Shopify product dicts (id, title, product_type, body_html).
        job_id (str): Parent job ID for tracing back to meta_suggestions rows.
        max_workers (int, optional): Thread pool size (default 10).
    """
    import asyncio

    from app.llm import get_router
    from app.llm.batch import generate_meta_for_products
    from app.llm.meta_store import save_results
    from app.tenant_config import find_tenant_by_shop_domain

    products = payload.get("products", [])
    job_id = payload.get("job_id", "unknown")
    max_workers = int(payload.get("max_workers", 10))

    if not products:
        return {"generated": 0, "errors": 0, "message": "no products provided"}

    # Resolve merchant brand from tenant config (fallback: per-product vendor)
    tenant = find_tenant_by_shop_domain(shop) if shop else None
    brand = tenant.brand if tenant else None

    # Run synchronous batch in a thread so we don't block the event loop.
    router = get_router(shop=shop)
    results = await asyncio.to_thread(
        generate_meta_for_products,
        products,
        router,
        brand=brand,
        max_workers=max_workers,
    )

    if shop:
        save_results(results, shop=shop, job_id=job_id)

    ok = sum(1 for r in results if r.success)
    errors = len(results) - ok
    return {"generated": ok, "errors": errors, "total": len(results)}


@register("bulk_apply")
async def handle_bulk_apply(payload: dict, shop: str | None) -> dict:
    """Apply approved meta suggestions to Shopify for a shop.

    Expected payload keys:
        dry_run (bool): If True, simulate without writing to Shopify (default True).
        max_per_run (int): Maximum suggestions per run (default 50).
        delay (float): Seconds between mutations (default 0.5).
    """
    from dataclasses import asdict

    from app.apply.bulk_orchestrator import apply_approved_meta

    dry_run = bool(payload.get("dry_run", True))
    max_per_run = int(payload.get("max_per_run", 50))
    delay = float(payload.get("delay", 0.5))

    if not shop:
        return {"error": "shop is required for bulk_apply"}

    report = apply_approved_meta(shop, dry_run=dry_run, max_per_run=max_per_run, delay=delay)
    return asdict(report)
