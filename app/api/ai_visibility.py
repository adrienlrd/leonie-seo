"""AI Visibility status endpoint — V1 stub, branch enabled in V2."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ShopContext, get_shop_context

router = APIRouter(prefix="/api", tags=["ai_visibility"])


@router.get("/shops/{shop}/ai-visibility/status")
async def ai_visibility_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the AI Visibility feature status for a shop.

    In V1, AI Visibility (ChatGPT/Perplexity/Gemini mention tracking) is
    not implemented. This endpoint returns a stable stub so the frontend
    can render a disabled encart without hard-coding the flag.

    Returns:
        Dict with enabled flag and future version info.
    """
    return {
        "shop": ctx.shop,
        "enabled": False,
        "available_in": "v2",
        "axis": "ai_visibility",
        "message_fr": (
            "Suivi de la visibilité dans les moteurs IA (ChatGPT, Perplexity, Gemini) "
            "disponible dans une version future."
        ),
        "message_en": (
            "AI engine visibility tracking (ChatGPT, Perplexity, Gemini) "
            "will be available in a future version."
        ),
    }
