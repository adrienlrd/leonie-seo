"""Onboarding completion state — the single source of truth for the app guard.

Every `app.*` route in the Remix app is gated on this endpoint: while onboarding
is incomplete, the layout redirects to the onboarding screen. The rule used to
live in two places that disagreed (the dashboard checked the business profile
alone, the onboarding screen also required a market analysis), which is exactly
what makes a route guard bounce between two pages.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.api.deps import ShopContext, get_shop_context
from app.business_profile.jobs import load_business_profile
from app.market_analysis.jobs import load_latest_result
from app.shop_config_store import get_shop_config, set_shop_config

router = APIRouter(prefix="/api", tags=["onboarding"])

_STEP_KEY = "onboarding_step"
FIRST_STEP = 1
LAST_STEP = 6


def _persisted_step(shop: str) -> int:
    raw = get_shop_config(shop, _STEP_KEY)
    if raw is None:
        return FIRST_STEP
    try:
        step = int(raw)
    except ValueError:
        return FIRST_STEP
    return min(max(step, FIRST_STEP), LAST_STEP)


def _derived_step(profile: dict | None) -> int:
    """Lowest step the shop can possibly be on, from business data alone.

    Steps 4-6 leave no business trace that distinguishes "skipped Google" from
    "not there yet", which is why the reached step is also persisted.
    """
    if not profile:
        return 1
    if profile.get("status") != "validated":
        return 2
    return 3


def onboarding_state(shop: str) -> dict:
    """Return `{complete, step}` for a shop."""
    profile = load_business_profile(shop)
    analysis = load_latest_result(shop)
    complete = profile is not None and profile.get("status") == "validated" and analysis is not None
    return {
        "complete": complete,
        "step": max(_derived_step(profile), _persisted_step(shop)),
    }


@router.get("/shops/{shop}/onboarding/status")
async def get_onboarding_status(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Whether onboarding is done, and which step to resume on."""
    return onboarding_state(ctx.shop)


@router.put("/shops/{shop}/onboarding/step")
async def put_onboarding_step(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    step: Annotated[int, Body(embed=True)],
) -> dict:
    """Record the furthest step reached. Never moves backwards."""
    bounded = min(max(step, FIRST_STEP), LAST_STEP)
    reached = max(bounded, _persisted_step(ctx.shop))
    set_shop_config(ctx.shop, _STEP_KEY, str(reached))
    return {"step": reached}
