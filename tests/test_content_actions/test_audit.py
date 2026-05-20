"""Tests for the audit guardrails module."""

from __future__ import annotations

from app.content_actions.audit import (
    _check_do_not_say,
    _check_forbidden_promises,
    _length_ok,
    audit_result,
)
from app.content_actions.schema import (
    ConfirmedFact,
    ContentActionRequest,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    MissingFact,
    NicheContext,
    ResourceInput,
)


def _make_result(
    ct: ContentType = ContentType.META_TITLE,
    text: str = "Harnais chien nylon réglable — confort et sécurité",
) -> ContentActionResult:
    return ContentActionResult(
        action_id="test-id",
        content_type=ct,
        resource_id="gid://shopify/Product/1",
        generated_at="2026-05-20T12:00:00+00:00",
        output=ContentOutput(primary_text=text),
    )


def _make_request(
    ct: ContentType = ContentType.META_TITLE,
    forbidden_promises: list[str] | None = None,
    do_not_say: list[str] | None = None,
    missing_sensitive: bool = False,
    confirmed_facts: list | None = None,
) -> ContentActionRequest:
    niche = NicheContext(
        primary_niche="petfood",
        forbidden_promises=forbidden_promises or [],
        brand_voice={"do_not_say": do_not_say or []},
    )
    missing = [MissingFact(key="materials", severity="sensitive")] if missing_sensitive else []
    facts = confirmed_facts or []
    return ContentActionRequest(
        content_type=ct,
        resource=ResourceInput(id="gid://shopify/Product/1", title="Harnais nylon"),
        niche_context=niche,
        missing_facts=missing,
        confirmed_facts=facts,
    )


# ── _length_ok ────────────────────────────────────────────────────────────────


def test_length_ok_meta_title_valid():
    assert _length_ok("Harnais chien nylon réglable confort 50c", ContentType.META_TITLE) is True


def test_length_ok_meta_title_too_short():
    assert _length_ok("Court", ContentType.META_TITLE) is False


def test_length_ok_meta_title_too_long():
    assert _length_ok("A" * 65, ContentType.META_TITLE) is False


def test_length_ok_meta_description_valid():
    text = "Découvrez le harnais nylon pour chien, réglable et lavable. Confort et sécurité pour vos balades en extérieur. Livraison rapide."
    assert len(text) >= 120
    assert _length_ok(text, ContentType.META_DESCRIPTION) is True


def test_length_ok_alt_text_word_count():
    # 8-12 words required
    assert _length_ok("harnais chien nylon réglable vu de face usage quotidien", ContentType.ALT_TEXT) is True


def test_length_ok_alt_text_too_short():
    assert _length_ok("harnais chien", ContentType.ALT_TEXT) is False


# ── forbidden promises ────────────────────────────────────────────────────────


def test_check_forbidden_promises_detects_violation():
    violations = _check_forbidden_promises(
        "Ce harnais guérit les douleurs articulaires.",
        ["guérit", "thérapeutique"],
    )
    assert "guérit" in violations


def test_check_forbidden_promises_no_violation():
    violations = _check_forbidden_promises(
        "Harnais réglable pour chien, confortable et solide.",
        ["guérit", "thérapeutique"],
    )
    assert violations == []


# ── do not say ────────────────────────────────────────────────────────────────


def test_check_do_not_say_detects():
    violations = _check_do_not_say("Un produit révolutionnaire et incroyable.", ["révolutionnaire"])
    assert "révolutionnaire" in violations


def test_check_do_not_say_case_insensitive():
    violations = _check_do_not_say("Un produit RÉVOLUTIONNAIRE.", ["révolutionnaire"])
    assert "révolutionnaire" in violations


# ── audit_result ──────────────────────────────────────────────────────────────


def test_audit_result_forbidden_promise_triggers_needs_review():
    result = _make_result(
        text="Ce produit guérit les douleurs articulaires de votre chien naturellement."
    )
    request = _make_request(forbidden_promises=["guérit"])
    audited = audit_result(result, request)
    assert audited.status == ContentStatus.NEEDS_REVIEW
    assert "guérit" in audited.constraints_check.forbidden_promise_violations


def test_audit_result_do_not_say_triggers_needs_review():
    result = _make_result(
        ct=ContentType.META_DESCRIPTION,
        text="Un produit révolutionnaire pour votre chien, commandez maintenant et livraison offerte rapidement.",
    )
    request = _make_request(ct=ContentType.META_DESCRIPTION, do_not_say=["révolutionnaire"])
    audited = audit_result(result, request)
    assert audited.status == ContentStatus.NEEDS_REVIEW
    assert "révolutionnaire" in audited.constraints_check.do_not_say_violations


def test_audit_result_sensitive_missing_fact_triggers_needs_review():
    result = _make_result()
    request = _make_request(missing_sensitive=True)
    audited = audit_result(result, request)
    assert audited.status == ContentStatus.NEEDS_REVIEW


def test_audit_result_clean_content_stays_draft():
    text = "Harnais chien nylon réglable, confortable et solide pour vos balades quotidiennes."
    result = _make_result(ct=ContentType.META_DESCRIPTION, text=text * 2)
    request = _make_request(ct=ContentType.META_DESCRIPTION)
    audited = audit_result(result, request)
    assert audited.constraints_check.forbidden_promise_violations == []
    assert audited.constraints_check.do_not_say_violations == []


def test_audit_result_quality_score_range():
    result = _make_result()
    request = _make_request(confirmed_facts=[ConfirmedFact(key="nylon", value="nylon")])
    audited = audit_result(result, request)
    assert 0 <= audited.quality.score <= 100


def test_audit_result_quality_label_mapping():
    result = _make_result()
    request = _make_request()
    audited = audit_result(result, request)
    assert audited.quality.label in {"excellent", "bon", "à_compléter", "incomplet"}
