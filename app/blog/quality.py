"""Keyword-placement guardrail for generated blog articles.

Runs automatically right after section generation — purely advisory, mirrors
the score/label pattern already used in `app/content_actions/audit.py`. The
merchant sees a small checklist alongside the draft; nothing to configure or
fill in by hand.
"""

from __future__ import annotations

from typing import Any

from app.market_analysis.keyword_normalization import is_semantically_covered, strip_accents

_FIRST_WORDS_WINDOW = 100
_COVERAGE_THRESHOLD = 0.6
_MAX_DENSITY_PER_100_WORDS = 3.0

_LABEL_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (85, "excellent"),
    (65, "bon"),
    (45, "à_compléter"),
    (0, "incomplet"),
)


def _label_for(score: int) -> str:
    for floor, label in _LABEL_THRESHOLDS:
        if score >= floor:
            return label
    return "incomplet"


def _first_words(text: str, count: int) -> str:
    return " ".join(text.split()[:count])


def _occurrence_count(text: str, keyword: str) -> int:
    """Accent-insensitive substring count — mirrors `_check_do_not_say`."""
    needle = strip_accents(keyword.lower()).strip()
    if not needle or not text:
        return 0
    return strip_accents(text.lower()).count(needle)


def check_keyword_placement(
    *,
    title: str,
    intro: str,
    h2_questions: list[str],
    sections: list[dict[str, Any]],
    target_keyword: str,
) -> dict[str, Any]:
    """Check that ``target_keyword`` sits where search engines look first.

    Returns ``{ok, score, label, issues}``. Never blocks generation or
    publication — purely informative feedback shown alongside the draft.
    """
    keyword = (target_keyword or "").strip()
    if not keyword:
        return {"ok": True, "score": 100, "label": "excellent", "issues": []}

    issues: list[str] = []
    section_dicts = [s for s in sections if isinstance(s, dict)]
    body_text = " ".join(
        f"{s.get('direct_answer', '')} {s.get('body', '')}" for s in section_dicts
    ).strip()
    full_text = " ".join(part for part in (title, intro, *h2_questions, body_text) if part)

    if not is_semantically_covered(keyword, title, threshold=_COVERAGE_THRESHOLD):
        issues.append("Le mot-clé cible n'apparaît pas dans le titre.")

    if h2_questions and not any(
        is_semantically_covered(keyword, h2, threshold=_COVERAGE_THRESHOLD) for h2 in h2_questions
    ):
        issues.append("Le mot-clé cible n'apparaît dans aucun sous-titre (H2).")

    lead_parts = [intro]
    if section_dicts:
        lead_parts.append(str(section_dicts[0].get("direct_answer", "")))
        lead_parts.append(str(section_dicts[0].get("body", "")))
    lead_window = _first_words(" ".join(p for p in lead_parts if p), _FIRST_WORDS_WINDOW)
    if not is_semantically_covered(keyword, lead_window, threshold=_COVERAGE_THRESHOLD):
        issues.append(
            f"Le mot-clé cible n'apparaît pas dans les {_FIRST_WORDS_WINDOW} premiers mots."
        )

    word_count = len(full_text.split())
    if word_count:
        occurrences = _occurrence_count(full_text, keyword)
        density = occurrences / word_count * 100
        if density > _MAX_DENSITY_PER_100_WORDS:
            issues.append(
                f"Le mot-clé cible revient trop souvent ({occurrences}× pour {word_count} "
                "mots — risque de sur-optimisation)."
            )

    score = max(0, 100 - 25 * len(issues))
    return {"ok": not issues, "score": score, "label": _label_for(score), "issues": issues}
