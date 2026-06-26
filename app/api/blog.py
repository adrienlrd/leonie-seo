"""Blog editor API: section generation + Shopify draft publication.

Stateless endpoints driven by the frontend editor, so the merchant can mix Auto
(regenerate a section) and Manual (edit + save) flows without server-side state.
"""

from __future__ import annotations

import html
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.apply.shopify_writer import ShopifyWriteError
from app.blog.clusters import build_blog_idea_clusters
from app.blog.internal_links import (
    build_source_product_link,
    render_internal_links_html,
    select_blog_internal_links,
    suggest_cluster_links,
    suggest_links_for_article,
)
from app.blog.markdown import render_inline_markdown, render_markdown
from app.blog.quality import check_keyword_placement
from app.blog.schema import (
    build_article_jsonld,
    build_faqpage_jsonld,
    build_howto_jsonld,
    render_jsonld_blocks,
)
from app.blog.section_generator import generate_all_sections, generate_section
from app.blog.seo_score import score_blog_readiness
from app.blog.shopify_articles import BlogPublisher
from app.blog.store import delete_draft, get_draft, list_drafts, save_draft
from app.geo.auto_tracking import record_applied_change
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
    image_url: str = ""
    image_alt: str = ""


class BlogInternalLink(BaseModel):
    target_url: str
    anchor: str
    target_title: str = ""
    reason: str = ""


class BlogFaqItem(BaseModel):
    q: str = ""
    a: str = ""


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
    product_id: str | None = None
    blog_title: str = ""
    auto_generate: bool = True
    blog_idea_index: int | None = None


class DraftUpdateRequest(BaseModel):
    blog_title: str | None = None
    intro: str | None = None
    summary: str | None = None
    meta_description: str | None = None
    sections: list[BlogSection] | None = None
    internal_links: list[BlogInternalLink] | None = None
    faq: list[BlogFaqItem] | None = None
    tags: list[str] | None = None
    author_type: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    author_bio: str | None = None
    image_url: str | None = None
    image_alt: str | None = None
    image_style: str | None = None
    show_toc: bool | None = None
    numbered_steps: bool | None = None
    cta_enabled: bool | None = None
    cta_label: str | None = None
    cta_url: str | None = None
    cta_description: str | None = None
    cta_position: str | None = None


class LinkSuggestionsRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    exclude_urls: list[str] = Field(default_factory=list)


class IdeaClusterItem(BaseModel):
    key: str
    target_keyword: str = ""
    outline: list[str] = Field(default_factory=list)


class IdeaClustersRequest(BaseModel):
    items: list[IdeaClusterItem] = Field(default_factory=list)


def _apply_keyword_check(draft: dict[str, Any]) -> None:
    """Run the keyword-placement guardrail and attach its result to the draft in-place.

    Advisory only — never blocks generation or persistence. Skipped silently
    when the draft has no ``target_keyword`` (e.g. blank drafts created from a
    free-form title).
    """
    keyword = str(draft.get("target_keyword") or "").strip()
    if not keyword:
        draft.pop("keyword_check", None)
        return
    draft["keyword_check"] = check_keyword_placement(
        title=str(draft.get("blog_title") or ""),
        intro=str(draft.get("intro") or ""),
        h2_questions=[str(q) for q in (draft.get("outline") or [])],
        sections=[s for s in (draft.get("sections") or []) if isinstance(s, dict)],
        target_keyword=keyword,
    )


def _apply_seo_score(draft: dict[str, Any]) -> None:
    """Compute the blog GEO/SEO readiness score and attach it to the draft in-place.

    Advisory only — mirrors the product readiness score so the editor renders the
    same badge + per-pillar breakdown. Recomputed on every save.
    """
    result = score_blog_readiness(draft)
    draft["geo_score"] = result["readiness_score"]
    draft["geo_score_components"] = result["components"]
    draft["word_count"] = result["word_count"]


def _default_blog_image_alt(title: str, keyword: str) -> str:
    """Deterministic cover-image alt text: article title plus its target keyword.

    Same convention as ``market_analysis._default_image_alt`` (title + a
    value-adding keyword, capped at Shopify's ~125-char practical limit) —
    template-based, no LLM call needed.
    """
    base = title.strip()
    kw = keyword.strip()
    if kw and kw.lower() not in base.lower():
        base = f"{base} – {kw}"
    return base[:125].rstrip()


def _apply_image_alt(draft: dict[str, Any]) -> None:
    """Auto-fill the cover image's alt text the first time an image is set.

    Advisory only — pre-fills a sensible default so the merchant never faces a
    blank alt-text field, but never overwrites text the merchant already typed
    (the field stays editable in the draft, like the rest of generated content).
    Cleared if the image is removed.
    """
    image_url = str(draft.get("image_url") or "").strip()
    if not image_url:
        draft.pop("image_alt", None)
        return
    if str(draft.get("image_alt") or "").strip():
        return
    draft["image_alt"] = _default_blog_image_alt(
        str(draft.get("blog_title") or ""),
        str(draft.get("target_keyword") or ""),
    )


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
    fallback_keyword = next(
        (
            str(kw.get("query") or "").strip()
            for kw in (product.get("seo_keywords") or [])
            if isinstance(kw, dict) and kw.get("query")
        ),
        "",
    )
    target_keyword = str(selected_idea.get("target_keyword") or "").strip() or fallback_keyword
    source_product_link = build_source_product_link(product, selected_idea)
    raw_internal_links = [
        link
        for link in [
            source_product_link,
            *(
                pack.get("recommended_internal_links")
                or product.get("recommended_internal_links")
                or []
            ),
        ]
        if link
    ]
    product_title_str = str(product.get("product_title") or "").strip()
    cta_url = str((source_product_link or {}).get("target_url") or "")

    faq = [
        {"q": str(item.get("q") or item.get("question") or ""), "a": str(item.get("a") or item.get("answer") or "")}
        for item in (pack.get("proposed_faq") or [])
        if isinstance(item, dict) and (item.get("q") or item.get("question"))
    ]
    return {
        "product_id": product_id,
        "product_title": product.get("product_title", ""),
        "product_summary": product.get("product_summary", ""),
        "target_customer": product.get("target_customer", ""),
        "blog_title": blog_title,
        "target_keyword": target_keyword,
        "intro": intro,
        "summary": (intro or "")[:200],
        "meta_description": (intro or "")[:155],
        "outline": list(outline or []),
        "sections": [],
        "internal_links": select_blog_internal_links(raw_internal_links),
        "faq": faq,
        "confirmed_facts": pack.get("confirmed_facts") or [],
        "tags": [],
        "author_type": "Organization",
        "author_name": "",
        "author_bio": "",
        "cta_enabled": bool(cta_url),
        "cta_label": f"Découvrir {product_title_str}" if product_title_str else "Voir le produit",
        "cta_url": cta_url,
        "cta_description": "",
        "cta_position": "end",
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
    """Create a draft. Supply product_id to pre-populate from market analysis, or blog_title alone for a blank draft."""
    if body.product_id:
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
            _apply_keyword_check(draft)
    else:
        draft = {
            "product_title": "",
            "blog_title": body.blog_title,
            "intro": "",
            "summary": "",
            "sections": [],
            "internal_links": [],
            "outline": [],
            "tags": [],
            "author_type": "Organization",
            "author_name": "",
        }
    _apply_seo_score(draft)
    saved = save_draft(ctx.shop, draft)
    return saved


@router.get("/shops/{shop}/blog/drafts/{draft_id}/linkable-articles")
def list_linkable_articles(
    draft_id: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return other drafts that can be linked from the given draft."""
    all_drafts = list_drafts(ctx.shop)
    linkable = [
        {
            "id": d["id"],
            "blog_title": d.get("blog_title", ""),
            "shopify_article_handle": d.get("shopify_article_handle"),
            "status": d.get("status", "draft"),
            "tags": d.get("tags", []),
        }
        for d in all_drafts
        if d.get("id") != draft_id and d.get("blog_title")
    ]
    published = [d for d in linkable if d["status"] == "published_to_shopify"]
    unpublished = [d for d in linkable if d["status"] != "published_to_shopify"]
    return {"articles": published + unpublished}


@router.post("/shops/{shop}/blog/drafts/{draft_id}/link-suggestions")
def get_link_suggestions(
    draft_id: str,
    body: LinkSuggestionsRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return dynamic link suggestions for a draft based on provided keywords.

    Matches keywords against products (via primary keyword), collections, and
    other drafts. Uses the latest market analysis for product/collection data.
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    products = (load_latest_result(ctx.shop) or {}).get("products") or snapshot.get("products") or []
    collections = snapshot.get("collections") or []
    other_drafts = [d for d in list_drafts(ctx.shop) if d.get("id") != draft_id]
    exclude_urls = set(body.exclude_urls)

    current_draft = get_draft(ctx.shop, draft_id) or {}
    cluster_links = suggest_cluster_links(
        current_keyword=str(current_draft.get("target_keyword") or ""),
        current_outline=list(current_draft.get("outline") or []),
        other_drafts=other_drafts,
        exclude_urls=exclude_urls,
    )
    suggestions = suggest_links_for_article(
        keywords=body.keywords,
        products=products,
        collections=collections,
        other_drafts=other_drafts,
        exclude_urls=exclude_urls | {link["target_url"] for link in cluster_links},
    )
    return {"suggestions": select_blog_internal_links(cluster_links + suggestions)}


@router.post("/shops/{shop}/blog/idea-clusters")
def get_idea_clusters(
    body: IdeaClustersRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Group submitted blog ideas/drafts into topic clusters with a suggested pillar.

    Pure grouping over the items the client already has (ideas from the latest
    market analysis, or existing drafts) — no extra LLM or Shopify calls.
    """
    clusters = build_blog_idea_clusters([item.model_dump() for item in body.items])
    return {"clusters": clusters}


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
    if "faq" in patch and patch["faq"] is not None:
        patch["faq"] = [
            item.model_dump() if hasattr(item, "model_dump") else item for item in patch["faq"]
        ]
    draft.update(patch)
    if {"blog_title", "intro", "sections"} & set(patch):
        _apply_keyword_check(draft)
    if "image_url" in patch:
        _apply_image_alt(draft)
    _apply_seo_score(draft)
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
    _apply_keyword_check(draft)
    _apply_seo_score(draft)
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


def _section_image_html(section: BlogSection) -> str:
    url = (section.image_url or "").strip()
    if not url:
        return ""
    alt = (section.image_alt or section.h2 or "").strip()
    return f'<img src="{url}" alt="{alt}" style="max-width:100%;border-radius:8px;margin:12px 0;" />'


def _assemble_body_html(
    intro: str,
    sections: list[BlogSection],
    internal_links: list[BlogInternalLink | dict[str, Any]] | None = None,
    *,
    numbered_steps: bool = False,
) -> str:
    parts: list[str] = []
    if intro.strip():
        parts.append(f"<p>{render_inline_markdown(intro.strip())}</p>")
    step_no = 0
    for idx, section in enumerate(sections):
        h2 = (section.h2 or "").strip()
        direct = (section.direct_answer or "").strip()
        body = (section.body or "").strip()
        if not h2:
            continue
        # id anchor lets the table of contents jump-link to each section.
        if numbered_steps:
            step_no += 1
            parts.append(f'<h2 id="section-{idx}">{step_no}. {h2}</h2>')
        else:
            parts.append(f'<h2 id="section-{idx}">{h2}</h2>')
        if direct:
            parts.append(f"<p><strong>{render_inline_markdown(direct)}</strong></p>")
        img = _section_image_html(section)
        if img:
            parts.append(img)
        if body:
            # LLM bodies arrive as Markdown (bold, bullet lists) → render to HTML so
            # readers never see literal **Confort** or "- " bullets.
            parts.append(render_markdown(body))
    link_dicts = [
        link.model_dump() if hasattr(link, "model_dump") else dict(link)
        for link in (internal_links or [])
    ]
    links_html = render_internal_links_html(link_dicts)
    if links_html:
        parts.append(links_html)
    return "\n".join(parts)


def _cta_html(label: str, url: str, description: str) -> str:
    """Styled conversion call-to-action linking the article back to its product."""
    label = (label or "").strip()
    url = (url or "").strip()
    if not label or not url:
        return ""
    desc = (description or "").strip()
    desc_html = (
        f'<p style="margin:0 0 12px;color:#374151;">{render_inline_markdown(desc)}</p>' if desc else ""
    )
    return (
        '<div class="leonie-cta" style="margin:32px 0;padding:24px;border-radius:12px;'
        'background:#F4F6F8;border:1px solid #E1E3E5;text-align:center;">'
        + desc_html
        + f'<a href="{html.escape(url, quote=True)}" style="display:inline-block;padding:12px 28px;border-radius:8px;'
        'background:#202223;color:#fff;text-decoration:none;font-weight:600;">'
        + render_inline_markdown(label)
        + "</a></div>"
    )


def _reading_time_minutes(word_count: int) -> int:
    """Average adult reading speed ≈ 200 words/min; floor at 1 minute."""
    return max(1, round(word_count / 200))


def _reading_time_html(word_count: int) -> str:
    minutes = _reading_time_minutes(word_count)
    return f'<p class="reading-time"><em>⏱ {minutes} min de lecture</em></p>'


def _toc_html(sections: list[BlogSection]) -> str:
    items = [
        f'<li><a href="#section-{idx}">{section.h2.strip()}</a></li>'
        for idx, section in enumerate(sections)
        if (section.h2 or "").strip()
    ]
    if not items:
        return ""
    return (
        '<nav class="table-of-contents"><strong>Sommaire</strong><ol>'
        + "".join(items)
        + "</ol></nav>"
    )


def _faq_html(faq: list[dict[str, Any]]) -> str:
    rows = [
        f'<div class="faq-item"><h3>{render_inline_markdown(q)}</h3><p>{render_inline_markdown(a)}</p></div>'
        for item in (faq or [])
        if (q := str(item.get("q") or "").strip()) and (a := str(item.get("a") or "").strip())
    ]
    if not rows:
        return ""
    return '<section class="faq"><h2>Questions fréquentes</h2>' + "".join(rows) + "</section>"


def _author_bio_html(author_name: str, author_bio: str) -> str:
    bio = (author_bio or "").strip()
    if not bio:
        return ""
    name_html = f"<strong>{render_inline_markdown(author_name.strip())}</strong><br/>" if author_name.strip() else ""
    return (
        '<aside class="author-bio"><h2>À propos de l\'auteur</h2><p>'
        + name_html
        + render_inline_markdown(bio)
        + "</p></aside>"
    )


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
    draft_faq = [f for f in (draft.get("faq") or []) if isinstance(f, dict)]
    meta_description = str(draft.get("meta_description") or "").strip()
    numbered_steps = bool(draft.get("numbered_steps"))
    content_html = _assemble_body_html(
        draft.get("intro", ""),
        sections,
        draft.get("internal_links") or [],
        numbered_steps=numbered_steps,
    )
    cta_block = (
        _cta_html(draft.get("cta_label", ""), draft.get("cta_url", ""), draft.get("cta_description", ""))
        if draft.get("cta_enabled")
        else ""
    )
    # A mid-article CTA is injected between content and FAQ; an end CTA sits after
    # the author bio (closest to where the reader finishes). Default: end.
    cta_mid = cta_block if draft.get("cta_position") == "mid" else ""
    cta_end = cta_block if draft.get("cta_position") != "mid" else ""
    # Reading time + (optional) table of contents lead the article; FAQ and
    # author bio close it — all SEO/GEO signals that travel into the published HTML.
    html = (
        _reading_time_html(int(draft.get("word_count") or 0))
        + ("\n" + _toc_html(sections) if draft.get("show_toc") else "")
        + "\n"
        + content_html
        + "\n"
        + cta_mid
        + "\n"
        + _faq_html(draft_faq)
        + "\n"
        + _author_bio_html(draft.get("author_name", ""), draft.get("author_bio", ""))
        + "\n"
        + cta_end
    )
    canonical_url = f"https://{ctx.shop}/blogs/blog/{draft.get('blog_title', '')}"
    article_ld = build_article_jsonld(
        headline=draft.get("blog_title", ""),
        description=meta_description or draft.get("summary") or draft.get("intro", "")[:200],
        url=canonical_url,
        author_type=draft.get("author_type", "Organization"),
        author_name=draft.get("author_name", ""),
        author_url=draft.get("author_url"),
        author_bio=draft.get("author_bio", ""),
        publisher_name=body.publisher_name or draft.get("author_name", "") or ctx.shop,
        publisher_logo_url=body.publisher_logo_url,
        image_url=draft.get("image_url"),
    )
    faq_pairs = _build_faq_pairs(sections) + [
        {"question": str(f.get("q") or ""), "answer": str(f.get("a") or "")} for f in draft_faq
    ]
    faq_ld = build_faqpage_jsonld(faq_pairs)
    # Step-by-step guides also emit HowTo so Google/AI can parse the procedure.
    howto_ld = build_howto_jsonld(
        name=draft.get("blog_title", ""),
        description=meta_description or draft.get("intro", "")[:200],
        sections=[{"name": s.h2, "text": s.direct_answer or s.body} for s in sections],
    ) if numbered_steps else None
    body_html = html + "\n" + render_jsonld_blocks(article_ld, faq_ld, howto_ld)

    try:
        publisher = BlogPublisher(ctx.shop, ctx.access_token)
        blog_id = body.blog_id or publisher.ensure_default_blog()
        created = publisher.create_draft_article(
            blog_id=blog_id,
            title=draft.get("blog_title", ""),
            body_html=body_html,
            summary=meta_description or draft.get("summary", ""),
            tags=draft.get("tags") or [],
            author_name=draft.get("author_name", ""),
            image_url=draft.get("image_url"),
            image_alt=draft.get("image_alt"),
            meta_description=meta_description,
        )
    except ShopifyWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    draft["status"] = "published_to_shopify"
    draft["shopify_article_id"] = created.get("id")
    draft["shopify_article_handle"] = created.get("handle")
    draft["shopify_blog_id"] = blog_id
    saved = save_draft(ctx.shop, draft)
    record_applied_change(
        shop=ctx.shop,
        resource_type="blog_post",
        resource_id=str(created.get("id") or draft_id),
        resource_title=str(draft.get("blog_title") or ""),
        resource_handle=str(created.get("handle") or ""),
        action_type="blog_publish",
        field="blog_post",
        old_value=None,
        new_value=draft.get("blog_title"),
    )
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
