"""Keyword-placement guardrail for generated blog articles.

Runs automatically right after section generation — purely advisory, mirrors
the score/label pattern already used in `app/content_actions/audit.py`. The
merchant sees a small checklist alongside the draft; nothing to configure or
fill in by hand.
"""

from __future__ import annotations

from typing import Any

from app.language import DEFAULT_LANGUAGE
from app.market_analysis.keyword_normalization import is_semantically_covered, strip_accents

_FIRST_WORDS_WINDOW = 100
_COVERAGE_THRESHOLD = 0.6
_MAX_DENSITY_PER_100_WORDS = 3.0

# Advisory messages shown next to the draft, so they follow the shop language.
# `{n}` is the lead-window size, `{count}`/`{words}` the density figures.
_ISSUES: dict[str, dict[str, str]] = {
    "fr": {
        "title": "Le mot-clé cible n'apparaît pas dans le titre.",
        "h2": "Le mot-clé cible n'apparaît dans aucun sous-titre (H2).",
        "lead": "Le mot-clé cible n'apparaît pas dans les {n} premiers mots.",
        "density": (
            "Le mot-clé cible revient trop souvent ({count}× pour {words} mots — "
            "risque de sur-optimisation)."
        ),
    },
    "en": {
        "title": "The target keyword is missing from the title.",
        "h2": "The target keyword appears in no subheading (H2).",
        "lead": "The target keyword is missing from the first {n} words.",
        "density": (
            "The target keyword repeats too often ({count}× across {words} words — "
            "risk of over-optimization)."
        ),
    },
    "de": {
        "title": "Das Ziel-Keyword fehlt im Titel.",
        "h2": "Das Ziel-Keyword kommt in keiner Zwischenüberschrift (H2) vor.",
        "lead": "Das Ziel-Keyword fehlt in den ersten {n} Wörtern.",
        "density": (
            "Das Ziel-Keyword wiederholt sich zu oft ({count}× bei {words} Wörtern – "
            "Gefahr der Überoptimierung)."
        ),
    },
    "es": {
        "title": "La palabra clave objetivo no aparece en el título.",
        "h2": "La palabra clave objetivo no aparece en ningún subtítulo (H2).",
        "lead": "La palabra clave objetivo no aparece en las primeras {n} palabras.",
        "density": (
            "La palabra clave objetivo se repite demasiado ({count}× en {words} palabras: "
            "riesgo de sobreoptimización)."
        ),
    },
}


def _issues_for(language: str) -> dict[str, str]:
    return _ISSUES.get(language, _ISSUES[DEFAULT_LANGUAGE])


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
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    """Check that ``target_keyword`` sits where search engines look first.

    Returns ``{ok, score, label, issues}``. Never blocks generation or
    publication — purely informative feedback shown alongside the draft.
    """
    keyword = (target_keyword or "").strip()
    if not keyword:
        return {"ok": True, "score": 100, "label": "excellent", "issues": []}

    issues: list[str] = []
    messages = _issues_for(language)
    section_dicts = [s for s in sections if isinstance(s, dict)]
    body_text = " ".join(
        f"{s.get('direct_answer', '')} {s.get('body', '')}" for s in section_dicts
    ).strip()
    full_text = " ".join(part for part in (title, intro, *h2_questions, body_text) if part)

    if not is_semantically_covered(keyword, title, threshold=_COVERAGE_THRESHOLD):
        issues.append(messages["title"])

    if h2_questions and not any(
        is_semantically_covered(keyword, h2, threshold=_COVERAGE_THRESHOLD) for h2 in h2_questions
    ):
        issues.append(messages["h2"])

    lead_parts = [intro]
    if section_dicts:
        lead_parts.append(str(section_dicts[0].get("direct_answer", "")))
        lead_parts.append(str(section_dicts[0].get("body", "")))
    lead_window = _first_words(" ".join(p for p in lead_parts if p), _FIRST_WORDS_WINDOW)
    if not is_semantically_covered(keyword, lead_window, threshold=_COVERAGE_THRESHOLD):
        issues.append(messages["lead"].replace("{n}", str(_FIRST_WORDS_WINDOW)))

    word_count = len(full_text.split())
    if word_count:
        occurrences = _occurrence_count(full_text, keyword)
        density = occurrences / word_count * 100
        if density > _MAX_DENSITY_PER_100_WORDS:
            issues.append(
                messages["density"]
                .replace("{count}", str(occurrences))
                .replace("{words}", str(word_count))
            )

    score = max(0, 100 - 25 * len(issues))
    return {"ok": not issues, "score": score, "label": _label_for(score), "issues": issues}
