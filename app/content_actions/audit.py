"""Audit guardrails for Content Actions — runs after LLM generation, before persistence."""

from __future__ import annotations

from app.content_actions.schema import (
    ContentActionRequest,
    ContentActionResult,
    ContentStatus,
    ContentType,
)

# ── Length constraints per content_type ──────────────────────────────────────

_LENGTH_LIMITS: dict[ContentType, tuple[int | None, int | None]] = {
    ContentType.META_TITLE: (30, 60),
    ContentType.META_DESCRIPTION: (120, 160),
    ContentType.ALT_TEXT: (None, 80),
    ContentType.PRODUCT_DESCRIPTION: (600, 4000),
    ContentType.COLLECTION_DESCRIPTION: (400, 4000),
    ContentType.ANSWER_BLOCK: (100, 300),
}

_ALT_TEXT_MIN_WORDS = 5
_ALT_TEXT_MAX_WORDS = 12

_BUYING_GUIDE_MIN_SECTIONS = 3
_BUYING_GUIDE_MAX_SECTIONS = 6

# Simple French word list for language detection heuristic
_FR_MARKERS = {
    "le", "la", "les", "de", "du", "des", "et", "est", "une", "un",
    "pour", "avec", "dans", "sur", "par", "ce", "se", "en", "au",
}

_QUALITY_LABEL_MAP = {
    (0, 45): "incomplet",
    (45, 65): "à_compléter",
    (65, 85): "bon",
    (85, 101): "excellent",
}


def _length_ok(text: str, content_type: ContentType) -> bool:
    limits = _LENGTH_LIMITS.get(content_type)
    if limits is None:
        return True
    min_len, max_len = limits
    length = len(text)
    if min_len is not None and length < min_len:
        return False
    if max_len is not None and length > max_len:
        return False
    if content_type == ContentType.ALT_TEXT:
        words = len(text.split())
        return _ALT_TEXT_MIN_WORDS <= words <= _ALT_TEXT_MAX_WORDS
    return True


def _buying_guide_sections_ok(structured: dict | None) -> bool:
    if not structured:
        return False
    sections = structured.get("sections", [])
    return _BUYING_GUIDE_MIN_SECTIONS <= len(sections) <= _BUYING_GUIDE_MAX_SECTIONS


def _detect_language(text: str) -> str:
    """Simple heuristic — count French marker words."""
    words = {w.lower().strip(".,;:!?") for w in text.split()}
    fr_count = len(words & _FR_MARKERS)
    return "fr" if fr_count >= 3 else "other"


def _check_forbidden_promises(text: str, forbidden_promises: list[str]) -> list[str]:
    violations: list[str] = []
    text_lower = text.lower()
    for fp in forbidden_promises:
        if fp.lower() in text_lower:
            violations.append(fp)
    return violations


def _check_do_not_say(text: str, do_not_say: list[str]) -> list[str]:
    violations: list[str] = []
    text_lower = text.lower()
    for word in do_not_say:
        if word.lower() in text_lower:
            violations.append(word)
    return violations


def _compute_quality_score(
    result: ContentActionResult,
    request: ContentActionRequest,
) -> int:
    """Quality score 0-100 based on facts coverage, query coverage, constraints, brand voice."""
    available_facts = len(request.confirmed_facts)
    used_facts = len(result.facts_used)
    facts_ratio = (used_facts / available_facts) if available_facts > 0 else 0.0

    top_queries = [q.get("query", "").lower() for q in request.gsc_signals.top_queries[:5]]
    text_lower = result.output.primary_text.lower()
    covered = sum(1 for q in top_queries if any(word in text_lower for word in q.split()))
    query_ratio = (covered / len(top_queries)) if top_queries else 1.0

    constraints_ok = (
        result.constraints_check.length_ok
        and result.constraints_check.language_ok
        and not result.constraints_check.forbidden_promise_violations
        and not result.constraints_check.do_not_say_violations
    )
    constraints_score = 1.0 if constraints_ok else 0.5

    do_not_say = request.niche_context.brand_voice.get("do_not_say", [])
    voice_ok = not _check_do_not_say(result.output.primary_text, do_not_say)
    voice_score = 1.0 if voice_ok else 0.5

    raw = (
        0.40 * facts_ratio
        + 0.30 * query_ratio
        + 0.20 * constraints_score
        + 0.10 * voice_score
    )
    return min(100, round(raw * 100))


def _quality_label(score: int) -> str:
    for (lo, hi), label in _QUALITY_LABEL_MAP.items():
        if lo <= score < hi:
            return label
    return "incomplet"


def audit_result(
    result: ContentActionResult,
    request: ContentActionRequest,
) -> ContentActionResult:
    """Run all guardrail checks and update status/constraints_check/quality in-place.

    Args:
        result: ContentActionResult with output already set.
        request: Original ContentActionRequest.

    Returns:
        Updated ContentActionResult with audit fields populated.
    """
    text = result.output.primary_text
    ct = result.content_type
    forbidden = request.niche_context.forbidden_promises
    do_not_say = request.niche_context.brand_voice.get("do_not_say", [])
    locale = request.constraints.locale

    # Length check
    if ct == ContentType.BUYING_GUIDE:
        length_ok = _buying_guide_sections_ok(result.output.structured)
    else:
        length_ok = _length_ok(text, ct)

    # Forbidden promises
    fp_violations = _check_forbidden_promises(text, forbidden)

    # Do not say
    dns_violations = _check_do_not_say(text, do_not_say)

    # Language check (skip for multilingual — contains mixed content)
    if ct == ContentType.META_MULTILINGUAL:
        language_ok = True
    else:
        detected = _detect_language(text)
        language_ok = locale == "en" or detected == "fr"

    result.constraints_check.length_ok = length_ok
    result.constraints_check.language_ok = language_ok
    result.constraints_check.forbidden_promise_violations = fp_violations
    result.constraints_check.do_not_say_violations = dns_violations

    # Quality score
    score = _compute_quality_score(result, request)
    result.quality.score = score
    result.quality.label = _quality_label(score)

    # Missing sensitive facts trigger needs_review
    has_sensitive_missing = any(
        mf.severity == "sensitive" for mf in request.missing_facts
    )

    # Status
    needs_review = (
        fp_violations
        or dns_violations
        or not length_ok
        or not language_ok
        or score < 45
        or has_sensitive_missing
    )
    if result.status == ContentStatus.DRAFT and needs_review:
        result.status = ContentStatus.NEEDS_REVIEW

    return result
