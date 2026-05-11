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
    """Run a full SEO audit for a shop (stub — full pipeline wired in Phase 7).

    Expected payload keys:
        shop (str): Shopify shop domain
        tenant_id (str, optional): config tenant alias
    """
    return {"status": "queued", "shop": shop, "message": "audit pipeline not yet wired (Phase 7)"}


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

    products = payload.get("products", [])
    job_id = payload.get("job_id", "unknown")
    max_workers = int(payload.get("max_workers", 10))

    if not products:
        return {"generated": 0, "errors": 0, "message": "no products provided"}

    # Run synchronous batch in a thread so we don't block the event loop.
    loop = asyncio.get_event_loop()
    router = get_router()
    results = await loop.run_in_executor(
        None, lambda: generate_meta_for_products(products, router, max_workers=max_workers)
    )

    if shop:
        save_results(results, shop=shop, job_id=job_id)

    ok = sum(1 for r in results if r.success)
    errors = len(results) - ok
    return {"generated": ok, "errors": errors, "total": len(results)}
