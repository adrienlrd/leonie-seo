"""Content Actions orchestrator — unified 11-step LLM generation workflow."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.content_actions.audit import audit_result
from app.content_actions.schema import (
    ConstraintsCheck,
    ContentActionRequest,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    LLMMeta,
    QualityResult,
)

# ── Constants ─────────────────────────────────────────────────────────────────

_FACTUAL_CONTENT_TYPES = {
    ContentType.PRODUCT_DESCRIPTION,
    ContentType.COLLECTION_DESCRIPTION,
    ContentType.FAQ_BLOCK,
    ContentType.ANSWER_BLOCK,
    ContentType.BUYING_GUIDE,
}

_LLM_TIER_MAP: dict[ContentType, str] = {
    ContentType.META_TITLE: "low-cost",
    ContentType.META_DESCRIPTION: "low-cost",
    ContentType.ALT_TEXT: "low-cost",
    ContentType.META_MULTILINGUAL: "low-cost",
    ContentType.PRODUCT_DESCRIPTION: "medium",
    ContentType.COLLECTION_DESCRIPTION: "medium",
    ContentType.FAQ_BLOCK: "medium",
    ContentType.ANSWER_BLOCK: "medium",
    ContentType.BUYING_GUIDE: "medium",
    ContentType.JSONLD_FAQPAGE: "deterministic",
}

_PROMPT_MAP: dict[ContentType, str] = {
    ContentType.META_TITLE: "meta_title",
    ContentType.META_DESCRIPTION: "meta_description",
    ContentType.PRODUCT_DESCRIPTION: "product_description",
    ContentType.COLLECTION_DESCRIPTION: "collection_brief",
    ContentType.ALT_TEXT: "alt_text",
    ContentType.FAQ_BLOCK: "faq_product",
    ContentType.ANSWER_BLOCK: "answer_block",
    ContentType.BUYING_GUIDE: "buying_guide",
    ContentType.META_MULTILINGUAL: "meta_multilingual",
}

_CACHE_TTL_MAP: dict[ContentType, int] = {
    ContentType.META_TITLE: 90 * 24,
    ContentType.META_DESCRIPTION: 90 * 24,
    ContentType.ALT_TEXT: 90 * 24,
    ContentType.META_MULTILINGUAL: 90 * 24,
    ContentType.PRODUCT_DESCRIPTION: 30 * 24,
    ContentType.COLLECTION_DESCRIPTION: 30 * 24,
    ContentType.FAQ_BLOCK: 30 * 24,
    ContentType.ANSWER_BLOCK: 30 * 24,
    ContentType.BUYING_GUIDE: 30 * 24,
    ContentType.JSONLD_FAQPAGE: 0,
}

_MAX_RETRIES = 3

_TASK_NAME = "content_actions"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _stable_hash(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _niche_context_from_hypothesis(niche_hypothesis: dict[str, Any] | None) -> dict[str, Any]:
    if not niche_hypothesis:
        return {}
    sh = niche_hypothesis.get("shop_summary", {})
    return {
        "primary_niche": str(sh.get("primary_niche") or ""),
        "brand_voice": niche_hypothesis.get("brand_voice", {}),
        "marketing_angles": niche_hypothesis.get("marketing_angles", []),
        "customer_segments": niche_hypothesis.get("customer_segments", []),
        "forbidden_promises": niche_hypothesis.get("forbidden_promises", []),
        "conversational_intents": [
            {"intent": str(ci.get("intent") or ""), "example_queries": ci.get("example_queries", [])}
            for ci in niche_hypothesis.get("conversational_intents", [])[:5]
        ],
    }


def _llm_cache_lookup(
    shop: str,
    content_type: ContentType,
    prompt_version: str,
    content_hash: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    task_name = f"{_TASK_NAME}_{content_type.value}"
    try:
        with get_conn(path) as conn:
            row = conn.execute(
                """SELECT response_json FROM llm_cache
                   WHERE shop = ? AND task_name = ? AND prompt_version = ?
                   AND content_hash = ? AND expires_at > ?""",
                (shop, task_name, prompt_version, content_hash, now),
            ).fetchone()
        if not row:
            return None
        raw = row["response_json"] if isinstance(row, dict) else row[0]
        return json.loads(raw)
    except Exception:
        return None


def _llm_cache_store(
    shop: str,
    content_type: ContentType,
    prompt_version: str,
    content_hash: str,
    result: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> None:
    from datetime import timedelta  # noqa: PLC0415

    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    ttl_hours = _CACHE_TTL_MAP.get(content_type, 24 * 30)
    if ttl_hours == 0:
        return
    path = db_path if db_path is not None else DB_PATH
    task_name = f"{_TASK_NAME}_{content_type.value}"
    now = datetime.now(UTC)
    expires = (now + timedelta(hours=ttl_hours)).isoformat()
    try:
        with get_conn(path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO llm_cache
                   (shop, task_name, prompt_version, content_hash, response_json,
                    tokens_in, tokens_out, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (shop, task_name, prompt_version, content_hash,
                 json.dumps(result), 0, 0, now.isoformat(), expires),
            )
    except Exception:
        pass


def _persist_action(
    shop: str,
    result: ContentActionResult,
    *,
    db_path: Path | None = None,
) -> None:
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    try:
        with get_conn(path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO content_actions
                   (action_id, shop, content_type, resource_id, resource_handle,
                    result_json, status, retry_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.action_id,
                    shop,
                    result.content_type.value,
                    result.resource_id,
                    "",
                    result.model_dump_json(),
                    result.status.value,
                    0,
                    now,
                    now,
                ),
            )
    except Exception:
        pass


def _load_action(
    shop: str,
    action_id: str,
    *,
    db_path: Path | None = None,
) -> ContentActionResult | None:
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    try:
        with get_conn(path) as conn:
            row = conn.execute(
                "SELECT result_json FROM content_actions WHERE action_id = ? AND shop = ?",
                (action_id, shop),
            ).fetchone()
        if not row:
            return None
        raw = row["result_json"] if isinstance(row, dict) else row[0]
        return ContentActionResult.model_validate_json(raw)
    except Exception:
        return None


def _update_action_status(
    shop: str,
    action_id: str,
    status: ContentStatus,
    new_result: ContentActionResult | None = None,
    *,
    retry_count: int | None = None,
    db_path: Path | None = None,
) -> None:
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    try:
        with get_conn(path) as conn:
            if new_result is not None:
                conn.execute(
                    """UPDATE content_actions
                       SET status = ?, result_json = ?, retry_count = COALESCE(?, retry_count),
                           updated_at = ?
                       WHERE action_id = ? AND shop = ?""",
                    (status.value, new_result.model_dump_json(), retry_count, now, action_id, shop),
                )
            else:
                conn.execute(
                    """UPDATE content_actions
                       SET status = ?, retry_count = COALESCE(?, retry_count), updated_at = ?
                       WHERE action_id = ? AND shop = ?""",
                    (status.value, retry_count, now, action_id, shop),
                )
    except Exception:
        pass


# ── JSON-LD deterministic conversion ─────────────────────────────────────────


def _faq_to_jsonld(faq_structured: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated faq_block structured output to JSON-LD FAQPage."""
    items = faq_structured.get("items", [])
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item.get("answer", ""),
                },
            }
            for item in items
        ],
    }


# ── Prompt variable builders ──────────────────────────────────────────────────


def _build_prompt_vars(
    request: ContentActionRequest,
    niche_ctx: dict[str, Any],
) -> dict[str, Any]:
    resource = request.resource
    facts = request.confirmed_facts
    top_queries = request.gsc_signals.top_queries[:5]
    primary_keyword = top_queries[0].get("query", resource.title) if top_queries else resource.title
    secondary_keywords = [q.get("query", "") for q in top_queries[1:4]]

    materials_facts = [f.value for f in facts if f.key in {"materials", "matières", "dimensions", "certifications"}]

    brand_voice = niche_ctx.get("brand_voice", {})
    do_not_say = brand_voice.get("do_not_say", [])
    forbidden_promises = niche_ctx.get("forbidden_promises", [])

    return {
        "product_title": resource.title,
        "resource_title": resource.title,
        "category": resource.type,
        "primary_niche": niche_ctx.get("primary_niche", "e-commerce"),
        "brand_voice_tone": brand_voice.get("tone", "professionnel"),
        "brand_voice_register": brand_voice.get("register", "standard"),
        "marketing_angles": niche_ctx.get("marketing_angles", []),
        "primary_keyword": primary_keyword,
        "secondary_keywords": secondary_keywords,
        "confirmed_facts": [{"key": f.key, "value": f.value} for f in facts[:10]],
        "materials": materials_facts,
        "current_description": resource.current_description_html or "",
        "current_seo_title": (resource.current_seo or {}).get("title", ""),
        "current_seo_description": (resource.current_seo or {}).get("description", ""),
        "do_not_say": do_not_say,
        "forbidden_promises": forbidden_promises,
        "customer_segments": niche_ctx.get("customer_segments", []),
        "conversational_intents": niche_ctx.get("conversational_intents", []),
        # meta_multilingual specific
        "locale": request.constraints.locale,
        "locale_name": "English" if request.constraints.locale == "en" else "French",
        "brand": niche_ctx.get("primary_niche", ""),
        "product_type": resource.type,
        "image_context": resource.primary_image_alt_text or "",
        "meta_title": (resource.current_seo or {}).get("title", resource.title),
        # collection_brief specific
        "cluster_name": resource.title,
        "product_count": 1,
        "top_keywords": [primary_keyword] + secondary_keywords,
        # feedback
        "previous_content": request.previous_content.content or "",
        "feedback": request.previous_content.feedback or "",
    }


# ── LLM call ──────────────────────────────────────────────────────────────────


def _call_llm(
    request: ContentActionRequest,
    niche_ctx: dict[str, Any],
    llm_router: Any,
    shop: str,
    *,
    db_path: Path | None = None,
) -> tuple[str, LLMMeta]:
    from app.llm.prompts import load_prompt  # noqa: PLC0415
    from app.llm.provider import LLMError  # noqa: PLC0415

    ct = request.content_type
    prompt_name = _PROMPT_MAP[ct]

    try:
        prompt_template = load_prompt(prompt_name)
    except Exception as exc:
        raise ValueError(f"Prompt '{prompt_name}' not found: {exc}") from exc

    vars_dict = _build_prompt_vars(request, niche_ctx)
    content_hash = _stable_hash({
        "resource_id": request.resource.id,
        "content_type": ct.value,
        "niche_version": niche_ctx.get("primary_niche", ""),
        "prompt_version": prompt_template.version,
        "facts_count": len(request.confirmed_facts),
        "feedback": request.previous_content.feedback or "",
    })

    cached = _llm_cache_lookup(shop, ct, prompt_template.version, content_hash, db_path=db_path)
    if cached is not None:
        return str(cached.get("text", "")), LLMMeta(
            tier=_LLM_TIER_MAP.get(ct, "low-cost"),
            prompt_version=prompt_template.version,
            cache_hit=True,
        )

    try:
        rendered = prompt_template.render_user(**vars_dict)
    except Exception as exc:
        raise ValueError(f"Prompt render failed: {exc}") from exc

    try:
        completion = llm_router.complete(
            rendered,
            system=prompt_template.system,
            max_tokens=prompt_template.max_tokens,
            temperature=prompt_template.temperature,
        )
    except LLMError as exc:
        raise ValueError(f"LLM call failed: {exc}") from exc

    text = completion.text.strip()
    meta = LLMMeta(
        tier=_LLM_TIER_MAP.get(ct, "low-cost"),
        provider=completion.provider,
        model=completion.model,
        prompt_version=prompt_template.version,
        tokens_in=getattr(completion, "tokens_in", 0) or 0,
        tokens_out=getattr(completion, "tokens_out", 0) or 0,
        cost_usd=getattr(completion, "cost_usd", 0.0) or 0.0,
        cache_hit=False,
    )

    _llm_cache_store(shop, ct, prompt_template.version, content_hash, {"text": text}, db_path=db_path)

    return text, meta


# ── Output parsing ────────────────────────────────────────────────────────────


def _parse_faq_output(text: str) -> ContentOutput:
    """Parse LLM output for faq_block — expect JSON array of Q/A."""
    try:
        raw = text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
        parsed = json.loads(raw)
        items = parsed if isinstance(parsed, list) else parsed.get("items", [])
        structured_items = [
            {
                "question": str(item.get("question", item.get("q", ""))),
                "answer": str(item.get("answer", item.get("a", ""))),
                "facts_used": item.get("facts_used", []),
            }
            for item in items
            if isinstance(item, dict)
        ]
        primary_text = "\n\n".join(
            f"Q: {it['question']}\nA: {it['answer']}" for it in structured_items
        )
        return ContentOutput(
            primary_text=primary_text,
            structured={"items": structured_items},
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return ContentOutput(primary_text=text, structured={"items": []})


def _parse_buying_guide_output(text: str) -> ContentOutput:
    """Parse LLM output for buying_guide — expect JSON with sections."""
    try:
        raw = text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
        parsed = json.loads(raw)
        sections = parsed.get("sections", [])
        structured = {
            "title": parsed.get("title", ""),
            "sections": [
                {
                    "heading": str(s.get("heading", "")),
                    "content": str(s.get("content", "")),
                    "source": str(s.get("source", "llm")),
                }
                for s in sections
            ],
        }
        primary_text = "\n\n".join(
            f"## {s['heading']}\n{s['content']}" for s in structured["sections"]
        )
        return ContentOutput(primary_text=primary_text, structured=structured)
    except (json.JSONDecodeError, KeyError, TypeError):
        return ContentOutput(primary_text=text, structured={"title": "", "sections": []})


def _parse_multilingual_output(text: str) -> ContentOutput:
    """Parse TITLE:/DESCRIPTION: blocks into structured dict."""
    lines = text.splitlines()
    fr_title = fr_desc = en_title = en_desc = ""
    current_locale = "fr"
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("TITLE:"):
            val = stripped[6:].strip()
            if current_locale == "fr":
                fr_title = val
            else:
                en_title = val
        elif stripped.upper().startswith("DESCRIPTION:"):
            val = stripped[12:].strip()
            if current_locale == "fr":
                fr_desc = val
                current_locale = "en"
            else:
                en_desc = val
    structured: dict[str, Any] = {}
    if fr_title or fr_desc:
        structured["fr"] = {"title": fr_title, "description": fr_desc}
    if en_title or en_desc:
        structured["en"] = {"title": en_title, "description": en_desc}
    summary = " | ".join(f"{k}: {v.get('title', '')}" for k, v in structured.items())
    return ContentOutput(primary_text=summary or text, structured=structured if structured else None)


def _parse_output(text: str, content_type: ContentType) -> ContentOutput:
    if content_type == ContentType.FAQ_BLOCK:
        return _parse_faq_output(text)
    if content_type == ContentType.BUYING_GUIDE:
        return _parse_buying_guide_output(text)
    if content_type == ContentType.META_MULTILINGUAL:
        return _parse_multilingual_output(text)
    return ContentOutput(primary_text=text, structured=None)


# ── Main orchestrator ─────────────────────────────────────────────────────────


def run_content_action(
    request: ContentActionRequest,
    shop: str,
    *,
    niche_hypothesis: dict[str, Any] | None = None,
    llm_router: Any | None = None,
    plan: str = "free",
    db_path: Path | None = None,
) -> ContentActionResult:
    """Run the unified content action workflow (steps 1-9).

    Steps 10 (Shopify apply) and 11 (Impact Tracker) are handled by Safe Apply.

    Args:
        request: Full ContentActionRequest bundle.
        shop: Shop identifier for budget/cache.
        niche_hypothesis: Validated niche hypothesis dict or None.
        llm_router: Injected LLM router (built from get_router if None).
        plan: Merchant plan tier.
        db_path: Override DB path (tests only).

    Returns:
        ContentActionResult with status draft|needs_review.

    Raises:
        ValueError: If niche_hypothesis is required but not validated.
        ValueError: If retry count exceeds _MAX_RETRIES for existing action.
    """
    from app.observability.metrics import check_budget  # noqa: PLC0415

    now = datetime.now(UTC)
    ct = request.content_type
    action_id = str(uuid.uuid4())

    # Step 1: Validate niche for factual content
    if ct in _FACTUAL_CONTENT_TYPES:
        status_val = (niche_hypothesis or {}).get("status", "")
        if status_val != "validated_by_merchant":
            raise ValueError(
                f"content_type={ct.value!r} requires a merchant-validated niche hypothesis. "
                f"Current status: {status_val!r}. Validate your niche profile first."
            )

    # Build niche context
    niche_ctx = _niche_context_from_hypothesis(niche_hypothesis)
    # Merge with request's niche_context if already provided
    if request.niche_context.primary_niche:
        niche_ctx = request.niche_context.model_dump()

    # Step 2: jsonld_faqpage is deterministic — no LLM
    if ct == ContentType.JSONLD_FAQPAGE:
        prev = request.previous_content
        if not prev.content:
            raise ValueError(
                "jsonld_faqpage requires a previously accepted faq_block in previous_content.content."
            )
        try:
            faq_data = json.loads(prev.content)
            jsonld = _faq_to_jsonld(faq_data if isinstance(faq_data, dict) else {"items": []})
        except (json.JSONDecodeError, TypeError):
            jsonld = _faq_to_jsonld({"items": []})

        serialized = json.dumps(jsonld, ensure_ascii=False, indent=2)
        output = ContentOutput(primary_text=serialized, structured=jsonld)
        result = ContentActionResult(
            action_id=action_id,
            content_type=ct,
            resource_id=request.resource.id,
            generated_at=now.isoformat(),
            output=output,
            facts_used=list(request.confirmed_facts),
            status=ContentStatus.DRAFT,
            llm_meta=LLMMeta(tier="deterministic"),
        )
        result = audit_result(result, request)
        _persist_action(shop, result, db_path=db_path)
        return result

    # Step 3: Budget check
    budget_usd = {"free": 2.0, "pro": 15.0, "agency": 75.0}.get(plan, 2.0)
    try:
        budget_check = check_budget(shop, budget_usd, db_path=db_path)
        if budget_check["over_budget"]:
            raise ValueError(f"Monthly LLM budget exceeded for plan={plan!r}.")
    except ValueError:
        raise
    except Exception:
        pass

    # Step 4: Get LLM router
    if llm_router is None:
        try:
            from app.llm import get_router  # noqa: PLC0415

            llm_router = get_router(shop=shop)
        except Exception as exc:
            raise ValueError(f"LLM router unavailable: {exc}") from exc

    # Step 5-6: Call LLM (with cache check inside)
    raw_text, llm_meta = _call_llm(request, niche_ctx, llm_router, shop, db_path=db_path)

    # Step 7: Parse output
    output = _parse_output(raw_text, ct)

    # Step 8: Build facts_used from confirmed_facts present in text
    text_lower = output.primary_text.lower()
    facts_used = [
        f for f in request.confirmed_facts
        if str(f.value).lower() in text_lower or f.key in text_lower
    ]

    # Step 9: Claims unverified — identify affirmations not backed by confirmed facts
    claims_unverified: list[dict[str, str]] = []
    for mf in request.missing_facts:
        if mf.severity == "sensitive":
            claims_unverified.append({
                "claim": f"Missing fact: {mf.key}",
                "category": "factual",
            })

    queries_targeted = [
        q.get("query", "") for q in request.gsc_signals.top_queries[:5] if q.get("query")
    ]
    intents_targeted = list({
        k for k, v in request.gsc_signals.intent_distribution.items() if v > 0.2
    })

    result = ContentActionResult(
        action_id=action_id,
        content_type=ct,
        resource_id=request.resource.id,
        generated_at=now.isoformat(),
        output=output,
        facts_used=facts_used,
        claims_unverified=claims_unverified,
        queries_targeted=queries_targeted,
        intents_targeted=intents_targeted,
        constraints_check=ConstraintsCheck(),
        quality=QualityResult(),
        status=ContentStatus.DRAFT,
        llm_meta=llm_meta,
    )

    # Audit guardrails
    result = audit_result(result, request)

    # Persist
    _persist_action(shop, result, db_path=db_path)

    return result


def retry_content_action(
    existing_action_id: str,
    shop: str,
    feedback: str | None = None,
    *,
    niche_hypothesis: dict[str, Any] | None = None,
    llm_router: Any | None = None,
    plan: str = "free",
    db_path: Path | None = None,
) -> ContentActionResult:
    """Re-generate content for an existing action with optional feedback.

    Args:
        existing_action_id: ID of the action to retry.
        shop: Shop identifier.
        feedback: Merchant feedback text for the retry.
        niche_hypothesis: Validated niche hypothesis.
        llm_router: Injected LLM router.
        plan: Merchant plan.
        db_path: Override DB path (tests only).

    Returns:
        New ContentActionResult with incremented retry count.

    Raises:
        ValueError: If action not found, or retry count ≥ _MAX_RETRIES.
    """
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    try:
        with get_conn(path) as conn:
            row = conn.execute(
                "SELECT result_json, retry_count FROM content_actions WHERE action_id = ? AND shop = ?",
                (existing_action_id, shop),
            ).fetchone()
    except Exception as exc:
        raise ValueError(f"Could not load action {existing_action_id}: {exc}") from exc

    if not row:
        raise ValueError(f"Action {existing_action_id!r} not found for shop {shop!r}.")

    retry_count = int(row["retry_count"] if isinstance(row, dict) else row[1])
    if retry_count >= _MAX_RETRIES:
        raise ValueError(
            f"Maximum {_MAX_RETRIES} retries reached for action {existing_action_id!r}. "
            f"Please edit the content manually."
        )

    previous_result = ContentActionResult.model_validate_json(
        row["result_json"] if isinstance(row, dict) else row[0]
    )

    prev_content = previous_result.output.primary_text
    request_dict = {
        "content_type": previous_result.content_type.value,
        "resource": {
            "id": previous_result.resource_id,
            "type": "product",
            "title": "",
        },
        "previous_content": {
            "version": previous_result.llm_meta.prompt_version,
            "content": prev_content,
            "feedback": feedback or "",
        },
    }
    request = ContentActionRequest.model_validate(request_dict)

    new_result = run_content_action(
        request,
        shop,
        niche_hypothesis=niche_hypothesis,
        llm_router=llm_router,
        plan=plan,
        db_path=db_path,
    )

    new_retry_count = retry_count + 1
    _update_action_status(
        shop,
        existing_action_id,
        ContentStatus.REJECTED,
        db_path=db_path,
    )
    _update_action_status(
        shop,
        new_result.action_id,
        new_result.status,
        new_result,
        retry_count=new_retry_count,
        db_path=db_path,
    )

    return new_result
