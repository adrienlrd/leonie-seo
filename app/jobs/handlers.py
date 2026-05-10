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
    # Phase 7 will import and call the real audit pipeline here.
    return {"status": "queued", "shop": shop, "message": "audit pipeline not yet wired (Phase 7)"}
