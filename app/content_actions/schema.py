"""Pydantic models for the unified Content Actions workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ContentType(StrEnum):
    META_TITLE = "meta_title"
    META_DESCRIPTION = "meta_description"
    PRODUCT_DESCRIPTION = "product_description"
    COLLECTION_DESCRIPTION = "collection_description"
    ALT_TEXT = "alt_text"
    FAQ_BLOCK = "faq_block"
    ANSWER_BLOCK = "answer_block"
    BUYING_GUIDE = "buying_guide"
    JSONLD_FAQPAGE = "jsonld_faqpage"
    META_MULTILINGUAL = "meta_multilingual"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"
    APPLIED = "applied"
    REVERTED = "reverted"


# ── Input models ──────────────────────────────────────────────────────────────


class ResourceInput(BaseModel):
    type: str = "product"
    id: str
    handle: str = ""
    title: str = ""
    current_seo: dict[str, str | None] = Field(default_factory=dict)
    current_description_html: str | None = None
    primary_image_alt_text: str | None = None


class ConfirmedFact(BaseModel):
    key: str
    value: Any
    source: str = "shopify"


class MissingFact(BaseModel):
    key: str
    severity: str = "standard"


class GscSignals(BaseModel):
    top_queries: list[dict[str, Any]] = Field(default_factory=list)
    intent_distribution: dict[str, float] = Field(default_factory=dict)


class Ga4Signals(BaseModel):
    sessions_30d: int | None = None
    conversions_30d: int | None = None
    avg_order_value: float | None = None
    estimate_basis: str = "fallback"


class NicheContext(BaseModel):
    primary_niche: str = ""
    brand_voice: dict[str, Any] = Field(default_factory=dict)
    marketing_angles: list[str] = Field(default_factory=list)
    customer_segments: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_promises: list[str] = Field(default_factory=list)
    conversational_intents: list[dict[str, Any]] = Field(default_factory=list)


class Constraints(BaseModel):
    max_length: int | None = None
    min_length: int | None = None
    locale: str = "fr"
    tone_override: str | None = None


class PreviousContent(BaseModel):
    version: str | None = None
    content: str | None = None
    feedback: str | None = None


class ContentActionRequest(BaseModel):
    content_type: ContentType
    resource: ResourceInput
    confirmed_facts: list[ConfirmedFact] = Field(default_factory=list)
    missing_facts: list[MissingFact] = Field(default_factory=list)
    gsc_signals: GscSignals = Field(default_factory=GscSignals)
    ga4_signals: Ga4Signals = Field(default_factory=Ga4Signals)
    niche_context: NicheContext = Field(default_factory=NicheContext)
    constraints: Constraints = Field(default_factory=Constraints)
    previous_content: PreviousContent = Field(default_factory=PreviousContent)


# ── Output models ─────────────────────────────────────────────────────────────


class ContentOutput(BaseModel):
    primary_text: str
    structured: dict[str, Any] | None = None


class ConstraintsCheck(BaseModel):
    length_ok: bool = True
    language_ok: bool = True
    forbidden_promise_violations: list[str] = Field(default_factory=list)
    do_not_say_violations: list[str] = Field(default_factory=list)


class QualityResult(BaseModel):
    score: int = 0
    label: str = "incomplet"


class LLMMeta(BaseModel):
    tier: str = "low-cost"
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False


class ContentActionResult(BaseModel):
    action_id: str
    content_type: ContentType
    resource_id: str
    generated_at: str

    output: ContentOutput
    facts_used: list[ConfirmedFact] = Field(default_factory=list)
    claims_unverified: list[dict[str, str]] = Field(default_factory=list)
    queries_targeted: list[str] = Field(default_factory=list)
    intents_targeted: list[str] = Field(default_factory=list)

    constraints_check: ConstraintsCheck = Field(default_factory=ConstraintsCheck)
    quality: QualityResult = Field(default_factory=QualityResult)
    status: ContentStatus = ContentStatus.DRAFT
    llm_meta: LLMMeta = Field(default_factory=LLMMeta)
