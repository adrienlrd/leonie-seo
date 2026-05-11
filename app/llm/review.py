"""Diff engine for LLM-generated meta suggestions vs current Shopify data."""

from __future__ import annotations

from dataclasses import dataclass

# SEO length targets (characters)
_TITLE_MIN = 50
_TITLE_MAX = 60
_DESC_MIN = 140
_DESC_MAX = 160


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
    # Overall pass/fail for auto-approve gate
    passes_quality_check: bool

    @property
    def summary(self) -> str:
        issues = []
        if not self.title_length_ok:
            issues.append(f"title {self.title_length} chars (target {_TITLE_MIN}-{_TITLE_MAX})")
        if not self.desc_length_ok:
            issues.append(f"desc {self.desc_length} chars (target {_DESC_MIN}-{_DESC_MAX})")
        return "; ".join(issues) if issues else "ok"


def compute_diff(suggestion: dict) -> DiffResult:
    """Compute a DiffResult from a meta_suggestions row.

    The baseline for comparison is the current product_title stored at generation
    time. The description baseline is empty (no prior SEO desc stored in this row).

    Args:
        suggestion: A row dict from meta_suggestions.

    Returns:
        DiffResult with change flags and length validation.
    """
    gen_title = suggestion.get("generated_title") or ""
    gen_desc = suggestion.get("generated_description") or ""
    baseline_title = suggestion.get("product_title") or ""
    baseline_desc = ""  # not stored — would require a live Shopify fetch

    title_len = len(gen_title)
    desc_len = len(gen_desc)
    title_ok = _TITLE_MIN <= title_len <= _TITLE_MAX
    desc_ok = _DESC_MIN <= desc_len <= _DESC_MAX

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
        passes_quality_check=title_ok and desc_ok and bool(gen_title),
    )


def diff_suggestions(suggestions: list[dict]) -> list[DiffResult]:
    """Compute diffs for a list of suggestion rows.

    Args:
        suggestions: Rows from meta_suggestions (status=pending).

    Returns:
        One DiffResult per suggestion.
    """
    return [compute_diff(s) for s in suggestions]
