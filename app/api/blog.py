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
from app.blog.schema import build_article_jsonld, build_faqpage_jsonld, render_jsonld_blocks
from app.blog.section_generator import generate_all_sections, generate_section
from app.blog.shopify_articles import BlogPublisher

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


class PublishDraftRequest(BaseModel):
    blog_id: str
    title: str
    intro: str = ""
    summary: str = ""
    sections: list[BlogSection]
    tags: list[str] = Field(default_factory=list)
    author_type: str = "Organization"  # or "Person"
    author_name: str = ""
    author_url: str | None = None
    image_url: str | None = None
    publisher_name: str = ""
    publisher_logo_url: str | None = None


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


def _assemble_body_html(intro: str, sections: list[BlogSection]) -> str:
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
    return "\n".join(parts)


def _build_faq_pairs(sections: list[BlogSection]) -> list[dict[str, str]]:
    """Use the direct answer as the FAQPage answer — that's the LLM-citable chunk."""
    return [
        {"question": s.h2.strip(), "answer": s.direct_answer.strip()}
        for s in sections
        if s.h2.strip() and s.direct_answer.strip()
    ]


@router.post("/shops/{shop}/blog/publish-draft")
def publish_draft(
    body: PublishDraftRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Assemble the article (HTML + Article + FAQPage JSON-LD) and create it as a draft."""
    html = _assemble_body_html(body.intro, body.sections)
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
