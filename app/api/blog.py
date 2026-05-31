"""Blog editor API: section generation + Shopify draft publication.

Stateless endpoints driven by the frontend editor, so the merchant can mix Auto
(regenerate a section) and Manual (edit + save) flows without server-side state.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.apply.shopify_writer import ShopifyWriteError
from app.blog.internal_links import render_internal_links_html, select_blog_internal_links
from app.blog.schema import build_article_jsonld, build_faqpage_jsonld, render_jsonld_blocks
from app.blog.section_generator import generate_all_sections, generate_section
from app.blog.shopify_articles import BlogPublisher
from app.blog.store import delete_draft, get_draft, list_drafts, save_draft
from app.market_analysis.jobs import load_latest_result

router = APIRouter(prefix="/api", tags=["blog"])


class ConfirmedFact(BaseModel):
    key: str
    value: str = ""


class SectionRequest(BaseModel):
    h2_question: str
    blog_title: str
    product_title: str
    product_summary: str = ""
    target_customer: str = ""
    brand_voice: str = ""
    confirmed_facts: list[ConfirmedFact] = Field(default_factory=list)


class GenerateAllRequest(BaseModel):
    blog_title: str
    h2_questions: list[str]
    product_title: str
    product_summary: str = ""
    target_customer: str = ""
    brand_voice: str = ""
    confirmed_facts: list[ConfirmedFact] = Field(default_factory=list)


class BlogSection(BaseModel):
    h2: str
    direct_answer: str
    body: str


class BlogInternalLink(BaseModel):
    target_url: str
    anchor: str
    target_title: str = ""
    reason: str = ""


class PublishDraftRequest(BaseModel):
    blog_id: str
    title: str
    intro: str = ""
    summary: str = ""
    sections: list[BlogSection]
    internal_links: list[BlogInternalLink] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    author_type: str = "Organization"  # or "Person"
    author_name: str = ""
    author_url: str | None = None
    image_url: str | None = None
    publisher_name: str = ""
    publisher_logo_url: str | None = None


class DraftCreateRequest(BaseModel):
    product_id: str
    auto_generate: bool = True
    blog_idea_index: int | None = None


class DraftUpdateRequest(BaseModel):
    blog_title: str | None = None
    intro: str | None = None
    summary: str | None = None
    sections: list[BlogSection] | None = None
    internal_links: list[BlogInternalLink] | None = None
    tags: list[str] | None = None
    author_type: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    image_url: str | None = None


def _draft_from_product(
    shop: str,
    product_id: str,
    *,
    blog_idea_index: int | None = None,
) -> dict[str, Any]:
    """Pre-populate a draft from the latest market analysis result for ``product_id``."""
    latest = load_latest_result(shop) or {}
    product = next(
        (p for p in (latest.get("products") or []) if p.get("product_id") == product_id),
        None,
    )
    if not product:
        raise HTTPException(
            status_code=404, detail="Product not found in the latest market analysis"
        )
    pack = product.get("content_test_pack") or {}
    blog_ideas = [
        item for item in (pack.get("proposed_blog_ideas") or []) if isinstance(item, dict)
    ]
    selected_idea: dict[str, Any] = {}
    if blog_idea_index is not None and 0 <= blog_idea_index < len(blog_ideas):
        selected_idea = blog_ideas[blog_idea_index]
    blog_title = selected_idea.get("title") or pack.get("proposed_blog_title", "")
    intro = selected_idea.get("intro") or pack.get("proposed_blog_intro", "")
    outline = selected_idea.get("outline") or pack.get("proposed_blog_outline") or []

    return {
        "product_id": product_id,
        "product_title": product.get("product_title", ""),
        "product_summary": product.get("product_summary", ""),
        "target_customer": product.get("target_customer", ""),
        "blog_title": blog_title,
        "intro": intro,
        "summary": (intro or "")[:200],
        "outline": list(outline or []),
        "sections": [],
        "internal_links": select_blog_internal_links(
            pack.get("recommended_internal_links")
            or product.get("recommended_internal_links")
            or []
        ),
        "confirmed_facts": pack.get("confirmed_facts") or [],
        "tags": [],
        "author_type": "Organization",
        "author_name": "",
    }


@router.get("/shops/{shop}/blog/drafts")
def list_blog_drafts(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict[str, Any]:
    return {"shop": ctx.shop, "drafts": list_drafts(ctx.shop)}


@router.get("/shops/{shop}/blog/drafts/{draft_id}")
def get_blog_draft(
    draft_id: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    draft = get_draft(ctx.shop, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post("/shops/{shop}/blog/drafts", status_code=201)
def create_blog_draft(
    body: DraftCreateRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Create a draft from a product. Generates all sections synchronously by default."""
    draft = _draft_from_product(ctx.shop, body.product_id, blog_idea_index=body.blog_idea_index)
    if body.auto_generate and draft["outline"]:
        draft["sections"] = generate_all_sections(
            blog_title=draft["blog_title"],
            h2_questions=draft["outline"],
            product_title=draft["product_title"],
            product_summary=draft["product_summary"],
            confirmed_facts=draft["confirmed_facts"],
            target_customer=draft["target_customer"],
            shop=ctx.shop,
        )
    saved = save_draft(ctx.shop, draft)
    return saved


@router.put("/shops/{shop}/blog/drafts/{draft_id}")
def update_blog_draft(
    draft_id: str,
    body: DraftUpdateRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    draft = get_draft(ctx.shop, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    patch = body.model_dump(exclude_unset=True)
    if "sections" in patch and patch["sections"] is not None:
        patch["sections"] = [
            s.model_dump() if hasattr(s, "model_dump") else s for s in patch["sections"]
        ]
    if "internal_links" in patch and patch["internal_links"] is not None:
        patch["internal_links"] = [
            link.model_dump() if hasattr(link, "model_dump") else link
            for link in patch["internal_links"]
        ]
    draft.update(patch)
    return save_draft(ctx.shop, draft)


@router.delete("/shops/{shop}/blog/drafts/{draft_id}")
def delete_blog_draft(
    draft_id: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    if not delete_draft(ctx.shop, draft_id):
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"shop": ctx.shop, "deleted": draft_id}


@router.post("/shops/{shop}/blog/drafts/{draft_id}/regenerate-section")
def regenerate_draft_section(
    draft_id: str,
    body: SectionRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Regenerate one section of an existing draft and persist the result."""
    draft = get_draft(ctx.shop, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    section = generate_section(
        blog_title=body.blog_title,
        h2_question=body.h2_question,
        product_title=body.product_title,
        product_summary=body.product_summary,
        confirmed_facts=[f.model_dump() for f in body.confirmed_facts],
        target_customer=body.target_customer,
        brand_voice=body.brand_voice,
        shop=ctx.shop,
    )
    section["h2"] = body.h2_question
    existing = [dict(s) for s in (draft.get("sections") or [])]
    replaced = False
    for idx, s in enumerate(existing):
        if s.get("h2") == body.h2_question:
            existing[idx] = section
            replaced = True
            break
    if not replaced:
        existing.append(section)
    draft["sections"] = existing
    return save_draft(ctx.shop, draft)


@router.get("/shops/{shop}/blog/blogs")
def list_blogs(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict[str, Any]:
    """Return the merchant's blogs so the editor can pick a destination."""
    try:
        blogs = BlogPublisher(ctx.shop, ctx.access_token).list_blogs()
    except ShopifyWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"shop": ctx.shop, "blogs": blogs}


@router.post("/shops/{shop}/blog/section")
def regenerate_section(
    body: SectionRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Generate (or regenerate) one blog section."""
    section = generate_section(
        blog_title=body.blog_title,
        h2_question=body.h2_question,
        product_title=body.product_title,
        product_summary=body.product_summary,
        confirmed_facts=[f.model_dump() for f in body.confirmed_facts],
        target_customer=body.target_customer,
        brand_voice=body.brand_voice,
        shop=ctx.shop,
    )
    section["h2"] = body.h2_question
    return section


@router.post("/shops/{shop}/blog/generate-all")
def generate_all(
    body: GenerateAllRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Generate every section for the given outline. Skips empty questions."""
    sections = generate_all_sections(
        blog_title=body.blog_title,
        h2_questions=body.h2_questions,
        product_title=body.product_title,
        product_summary=body.product_summary,
        confirmed_facts=[f.model_dump() for f in body.confirmed_facts],
        target_customer=body.target_customer,
        brand_voice=body.brand_voice,
        shop=ctx.shop,
    )
    return {"blog_title": body.blog_title, "sections": sections}


def _assemble_body_html(
    intro: str,
    sections: list[BlogSection],
    internal_links: list[BlogInternalLink | dict[str, Any]] | None = None,
) -> str:
    parts: list[str] = []
    if intro.strip():
        parts.append(f"<p>{intro.strip()}</p>")
    for section in sections:
        h2 = (section.h2 or "").strip()
        direct = (section.direct_answer or "").strip()
        body = (section.body or "").strip()
        if not h2:
            continue
        parts.append(f"<h2>{h2}</h2>")
        if direct:
            parts.append(f"<p><strong>{direct}</strong></p>")
        if body:
            parts.append(f"<div>{body}</div>")
    link_dicts = [
        link.model_dump() if hasattr(link, "model_dump") else dict(link)
        for link in (internal_links or [])
    ]
    links_html = render_internal_links_html(link_dicts)
    if links_html:
        parts.append(links_html)
    return "\n".join(parts)


def _build_faq_pairs(sections: list[BlogSection]) -> list[dict[str, str]]:
    """Use the direct answer as the FAQPage answer — that's the LLM-citable chunk."""
    return [
        {"question": s.h2.strip(), "answer": s.direct_answer.strip()}
        for s in sections
        if s.h2.strip() and s.direct_answer.strip()
    ]


class DraftPublishRequest(BaseModel):
    blog_id: str = ""  # empty → backend auto-creates a default blog if none exists
    publisher_name: str = ""
    publisher_logo_url: str | None = None


@router.post("/shops/{shop}/blog/drafts/{draft_id}/publish")
def publish_blog_draft(
    draft_id: str,
    body: DraftPublishRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Push a saved draft to Shopify as an unpublished article. Updates the draft status."""
    draft = get_draft(ctx.shop, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    sections = [BlogSection(**s) for s in (draft.get("sections") or []) if isinstance(s, dict)]
    html = _assemble_body_html(
        draft.get("intro", ""),
        sections,
        draft.get("internal_links") or [],
    )
    canonical_url = f"https://{ctx.shop}/blogs/blog/{draft.get('blog_title', '')}"
    article_ld = build_article_jsonld(
        headline=draft.get("blog_title", ""),
        description=draft.get("summary") or draft.get("intro", "")[:200],
        url=canonical_url,
        author_type=draft.get("author_type", "Organization"),
        author_name=draft.get("author_name", ""),
        author_url=draft.get("author_url"),
        publisher_name=body.publisher_name or draft.get("author_name", "") or ctx.shop,
        publisher_logo_url=body.publisher_logo_url,
        image_url=draft.get("image_url"),
    )
    faq_ld = build_faqpage_jsonld(_build_faq_pairs(sections))
    body_html = html + "\n" + render_jsonld_blocks(article_ld, faq_ld)

    try:
        publisher = BlogPublisher(ctx.shop, ctx.access_token)
        blog_id = body.blog_id or publisher.ensure_default_blog()
        created = publisher.create_draft_article(
            blog_id=blog_id,
            title=draft.get("blog_title", ""),
            body_html=body_html,
            summary=draft.get("summary", ""),
            tags=draft.get("tags") or [],
            author_name=draft.get("author_name", ""),
            image_url=draft.get("image_url"),
        )
    except ShopifyWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    draft["status"] = "published_to_shopify"
    draft["shopify_article_id"] = created.get("id")
    draft["shopify_article_handle"] = created.get("handle")
    draft["shopify_blog_id"] = blog_id
    saved = save_draft(ctx.shop, draft)
    return {"draft": saved, "article": created}


@router.post("/shops/{shop}/blog/publish-draft")
def publish_draft(
    body: PublishDraftRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Assemble the article (HTML + Article + FAQPage JSON-LD) and create it as a draft."""
    html = _assemble_body_html(body.intro, body.sections, body.internal_links)
    # Mount the article on the merchant's storefront URL so JSON-LD ``mainEntityOfPage``
    # points at the eventual public URL — Shopify substitutes the real handle on save.
    canonical_url = f"https://{ctx.shop}/blogs/blog/{body.title}"
    article_ld = build_article_jsonld(
        headline=body.title,
        description=body.summary or body.intro[:200],
        url=canonical_url,
        author_type=body.author_type,
        author_name=body.author_name,
        author_url=body.author_url,
        publisher_name=body.publisher_name or body.author_name,
        publisher_logo_url=body.publisher_logo_url,
        image_url=body.image_url,
    )
    faq_ld = build_faqpage_jsonld(_build_faq_pairs(body.sections))
    body_html = html + "\n" + render_jsonld_blocks(article_ld, faq_ld)

    try:
        created = BlogPublisher(ctx.shop, ctx.access_token).create_draft_article(
            blog_id=body.blog_id,
            title=body.title,
            body_html=body_html,
            summary=body.summary,
            tags=body.tags,
            author_name=body.author_name,
            image_url=body.image_url,
        )
    except ShopifyWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"shop": ctx.shop, "article": created}
