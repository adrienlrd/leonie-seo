"""Diff engine and anti-hallucination validators for LLM meta suggestions.

Quality gate checks (lot 4 wave 2):
- Length within target band (title 50-60, desc 140-160 chars)
- Title overlap: generated title must share ≥1 significant token (>3 chars)
  with the source product title — protects against the LLM inventing an
  unrelated product or rewriting the brand into nonsense
- Brand presence: when a brand is provided, it must appear in the title or
  description — protects against the LLM omitting the merchant name
- Suspicious-claim heuristic: flags inventory/pricing claims that the LLM
  shouldn't fabricate ("livraison gratuite", "100% remboursable", etc.)
- Empty-generation guard: empty / whitespace-only outputs always fail
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# SEO length targets (characters)
_TITLE_MIN = 50
_TITLE_MAX = 60
_DESC_MIN = 140
_DESC_MAX = 160

# Words shorter than this are considered stop-tokens for overlap detection
# (matches "le", "la", "de", "pour", "with", "and"...).
_MIN_OVERLAP_TOKEN_LENGTH = 4

# Heuristic patterns for claims the LLM shouldn't fabricate. These are not
# exhaustive — they cover the most common hallucination shapes observed in
# initial generations (free shipping, refund/return, certifications).
_SUSPICIOUS_CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("free_shipping", re.compile(r"\b(livraison\s+gratuite|free\s+shipping)\b", re.IGNORECASE)),
    ("money_back", re.compile(r"\b(100%\s+rembours|money\s*back|satisfait\s+ou\s+remboursé)\b", re.IGNORECASE)),
    ("vet_endorsement", re.compile(r"\b(approuvé\s+par\s+(?:des\s+)?vétérinaires?|vet[\s-]approved)\b", re.IGNORECASE)),
    ("best_in_class", re.compile(r"\b(numéro\s+1|n°?\s*1|#1|best[\s-]?in[\s-]?class)\b", re.IGNORECASE)),
)


def _significant_tokens(text: str) -> set[str]:
    """Return the lowercase set of word tokens ≥ _MIN_OVERLAP_TOKEN_LENGTH chars."""
    return {
        t
        for t in re.findall(r"[\wàâäéèêëîïôöùûüç-]+", text.lower())
        if len(t) >= _MIN_OVERLAP_TOKEN_LENGTH
    }


def _has_token_overlap(generated: str, baseline: str) -> bool:
    """True iff at least one significant token from baseline appears in generated."""
    base_tokens = _significant_tokens(baseline)
    gen_tokens = _significant_tokens(generated)
    return bool(base_tokens & gen_tokens)


def _brand_present(text: str, brand: str) -> bool:
    """Case-insensitive check that at least one brand token is in `text`."""
    brand_tokens = _significant_tokens(brand)
    if not brand_tokens:
        return False
    # Use a quick substring check (covers tokens shorter than min length too).
    lower = text.lower()
    return any(t in lower for t in brand_tokens) or brand.lower() in lower


def _suspicious_claims(text: str) -> list[str]:
    """Return the names of suspicious-claim patterns that matched `text`."""
    return [name for name, pattern in _SUSPICIOUS_CLAIM_PATTERNS if pattern.search(text)]


@dataclass
class DiffResult:
    suggestion_id: int
    product_id: str
    product_title: str
    generated_title: str
    generated_description: str
    # Baseline used for comparison (product_title by default — no explicit SEO meta stored yet)
    baseline_title: str
    baseline_description: str
    # Change flags
    title_changed: bool
    desc_changed: bool
    # Length validation
    title_length: int
    desc_length: int
    title_length_ok: bool
    desc_length_ok: bool
    # Anti-hallucination validators (lot 4 wave 2)
    title_keyword_ok: bool = True  # at least one shared significant token
    brand_present_in_title_or_desc: bool | None = None  # None when no brand passed
    suspicious_claims: list[str] = field(default_factory=list)
    # Overall pass/fail for auto-approve gate
    passes_quality_check: bool = False

    @property
    def summary(self) -> str:
        issues = []
        if not self.title_length_ok:
            issues.append(f"title {self.title_length} chars (target {_TITLE_MIN}-{_TITLE_MAX})")
        if not self.desc_length_ok:
            issues.append(f"desc {self.desc_length} chars (target {_DESC_MIN}-{_DESC_MAX})")
        if not self.title_keyword_ok:
            issues.append("title shares no significant token with product")
        if self.brand_present_in_title_or_desc is False:
            issues.append("brand missing from title and description")
        if self.suspicious_claims:
            issues.append("suspicious claims: " + ", ".join(self.suspicious_claims))
        return "; ".join(issues) if issues else "ok"


def compute_diff(suggestion: dict, *, brand: str | None = None) -> DiffResult:
    """Compute a DiffResult from a meta_suggestions row.

    The baseline for comparison is the current product_title stored at generation
    time. The description baseline is empty (no prior SEO desc stored in this row).

    Args:
        suggestion: A row dict from meta_suggestions.
        brand: Merchant brand string. When provided, presence is checked in
               title+description and contributes to passes_quality_check.

    Returns:
        DiffResult with length, keyword-overlap, brand-presence and
        suspicious-claim validators.
    """
    gen_title = suggestion.get("generated_title") or ""
    gen_desc = suggestion.get("generated_description") or ""
    baseline_title = suggestion.get("product_title") or ""
    baseline_desc = ""  # not stored — would require a live Shopify fetch

    title_len = len(gen_title)
    desc_len = len(gen_desc)
    title_ok = _TITLE_MIN <= title_len <= _TITLE_MAX
    desc_ok = _DESC_MIN <= desc_len <= _DESC_MAX

    # Anti-hallucination checks
    title_keyword_ok = _has_token_overlap(gen_title, baseline_title) if baseline_title else True
    brand_present: bool | None
    if brand:
        brand_present = _brand_present(gen_title, brand) or _brand_present(gen_desc, brand)
    else:
        brand_present = None
    suspicious = _suspicious_claims(gen_title) + _suspicious_claims(gen_desc)

    passes = (
        title_ok
        and desc_ok
        and bool(gen_title.strip())
        and title_keyword_ok
        and not suspicious
        and (brand_present is not False)  # None or True passes; False fails
    )

    return DiffResult(
        suggestion_id=suggestion["id"],
        product_id=suggestion.get("product_id", ""),
        product_title=baseline_title,
        generated_title=gen_title,
        generated_description=gen_desc,
        baseline_title=baseline_title,
        baseline_description=baseline_desc,
        title_changed=gen_title.lower() != baseline_title.lower(),
        desc_changed=bool(gen_desc),
        title_length=title_len,
        desc_length=desc_len,
        title_length_ok=title_ok,
        desc_length_ok=desc_ok,
        title_keyword_ok=title_keyword_ok,
        brand_present_in_title_or_desc=brand_present,
        suspicious_claims=suspicious,
        passes_quality_check=passes,
    )


def diff_suggestions(
    suggestions: list[dict], *, brand: str | None = None
) -> list[DiffResult]:
    """Compute diffs for a list of suggestion rows.

    Args:
        suggestions: Rows from meta_suggestions (status=pending).
        brand: Merchant brand string, forwarded to every compute_diff call.

    Returns:
        One DiffResult per suggestion.
    """
    return [compute_diff(s, brand=brand) for s in suggestions]
