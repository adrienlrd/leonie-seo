"""Content Actions API — unified LLM content generation workflow."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.content_actions.runner import (
    _load_action,
    _update_action_status,
    retry_content_action,
    run_content_action,
)
from app.content_actions.schema import ContentActionRequest, ContentStatus
from app.niche.understanding import get_validated_niche_hypothesis

router = APIRouter(prefix="/api", tags=["content_actions"])


class RetryRequest(BaseModel):
    feedback: str | None = None


class ExportRequest(BaseModel):
    format: str = "json"


@router.post("/shops/{shop}/content-actions/run")
async def run_action(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ContentActionRequest,
    plan: str = Query(default="free", pattern="^(free|pro|agency)$"),
) -> dict[str, Any]:
    """Generate content for one resource using the unified workflow.

    Requires niche_hypothesis validated by merchant for factual content_types
    (product_description, faq_block, answer_block, buying_guide, collection_description).
    """
    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)

    try:
        result = run_content_action(
            body,
            ctx.shop,
            niche_hypothesis=niche_hypothesis,
            llm_router=None,
            plan=plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return result.model_dump()


@router.get("/shops/{shop}/content-actions/{action_id}")
async def get_action(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    action_id: str,
) -> dict[str, Any]:
    """Retrieve a content action by ID."""
    result = _load_action(ctx.shop, action_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Action {action_id!r} not found.")
    return result.model_dump()


@router.post("/shops/{shop}/content-actions/{action_id}/retry")
async def retry_action(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    action_id: str,
    body: RetryRequest,
    plan: str = Query(default="free", pattern="^(free|pro|agency)$"),
) -> dict[str, Any]:
    """Re-generate an action with optional merchant feedback (max 3 retries)."""
    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)

    try:
        result = retry_content_action(
            action_id,
            ctx.shop,
            feedback=body.feedback,
            niche_hypothesis=niche_hypothesis,
            plan=plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return result.model_dump()


@router.post("/shops/{shop}/content-actions/{action_id}/export")
async def export_action(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    action_id: str,
    body: ExportRequest,
) -> dict[str, Any]:
    """Export a content action draft as JSON/Markdown without applying to Shopify."""
    result = _load_action(ctx.shop, action_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Action {action_id!r} not found.")

    _update_action_status(ctx.shop, action_id, ContentStatus.EXPORTED)

    export_format = body.format.lower()
    if export_format == "markdown":
        md = (
            f"# {result.content_type.value} — {result.resource_id}\n\n"
            f"**Status:** {result.status.value}\n"
            f"**Generated:** {result.generated_at}\n\n"
            f"## Output\n\n{result.output.primary_text}\n\n"
            f"## Quality\n\n"
            f"- Score: {result.quality.score}/100 ({result.quality.label})\n"
            f"- Facts used: {len(result.facts_used)}\n"
            f"- Length OK: {result.constraints_check.length_ok}\n"
        )
        return {"format": "markdown", "content": md, "action_id": action_id}

    return {
        "format": "json",
        "action_id": action_id,
        "content_type": result.content_type.value,
        "output": result.output.model_dump(),
        "quality": result.quality.model_dump(),
        "status": ContentStatus.EXPORTED.value,
    }
