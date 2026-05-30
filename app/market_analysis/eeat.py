"""Detect E-E-A-T credibility signals (Experience, Expertise, Authority, Trust).

Petfood FR focus: certifications (Ecocert, AB, GOTS, FSC…), French origin,
warranty, and merchant-side credentials read from the business profile.
Used by Pass 2 to prioritise verifiable trust cues over generic marketing
language, and by GEO blocks to surface authority signals to LLM extractors.
"""

from __future__ import annotations

import re
from typing import Any

_NON_WORD_RE = re.compile(r"[^a-z0-9é]+")

# Lowercase patterns and their canonical labels. Petfood-relevant FR/EU
# certifications first; extend cautiously to avoid false positives.
_CERTIFICATION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("ecocert", "Ecocert"),
    ("ab certifié", "Agriculture Biologique (AB)"),
    ("agriculture biologique", "Agriculture Biologique (AB)"),
    (" ab ", "Agriculture Biologique (AB)"),
    ("gots", "GOTS"),
    ("fsc", "FSC"),
    ("oeko-tex", "OEKO-TEX"),
    ("oeko tex", "OEKO-TEX"),
    ("nf ", "Norme NF"),
    ("ce certifié", "Marquage CE"),
    ("iso 9001", "ISO 9001"),
    ("label rouge", "Label Rouge"),
    ("origine france garantie", "Origine France Garantie"),
    ("entreprise du patrimoine vivant", "Entreprise du Patrimoine Vivant"),
)

_ORIGIN_PATTERNS = (
    "fabriqué en france",
    "fabrique en france",
    "made in france",
    "origine france",
    "produit en france",
    "fabriqué en europe",
    "made in eu",
)


def detect_signals(
    *,
    confirmed_facts: list[dict[str, Any]],
    business_profile: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return E-E-A-T signals detected in confirmed facts + business profile.

    Each signal carries `kind`, `label`, `source`, and `confidence`. Only
    facts marked `confirmed` contribute — unconfirmed claims never count as
    authority signals.
    """
    signals: list[dict[str, Any]] = []

    facts_by_key: dict[str, dict[str, Any]] = {}
    for fact in confirmed_facts or []:
        if not isinstance(fact, dict):
            continue
        if str(fact.get("confidence") or "") != "confirmed":
            continue
        key = str(fact.get("key") or "")
        if key:
            facts_by_key[key] = fact

    certifications_fact = facts_by_key.get("certifications")
    if certifications_fact:
        for label in _extract_certifications(_value_text(certifications_fact)):
            signals.append(
                {
                    "kind": "certification",
                    "label": label,
                    "source": str(certifications_fact.get("source") or "unknown"),
                    "confidence": "confirmed",
                }
            )

    origins_fact = facts_by_key.get("origins")
    if origins_fact:
        text = _value_text(origins_fact).lower()
        if any(pattern in text for pattern in _ORIGIN_PATTERNS) or text:
            signals.append(
                {
                    "kind": "origin",
                    "label": _value_text(origins_fact),
                    "source": str(origins_fact.get("source") or "unknown"),
                    "confidence": "confirmed",
                }
            )

    warranty_fact = facts_by_key.get("warranty")
    if warranty_fact and _value_text(warranty_fact):
        signals.append(
            {
                "kind": "warranty",
                "label": _value_text(warranty_fact),
                "source": str(warranty_fact.get("source") or "unknown"),
                "confidence": "confirmed",
            }
        )

    profile = business_profile or {}
    founded_year = profile.get("founded_year")
    if isinstance(founded_year, int) and 1900 <= founded_year <= 2100:
        signals.append(
            {
                "kind": "merchant_experience",
                "label": f"Activité depuis {founded_year}",
                "source": "business_profile",
                "confidence": "confirmed",
            }
        )
    expertise = profile.get("primary_expertise")
    if isinstance(expertise, str) and expertise.strip():
        signals.append(
            {
                "kind": "expertise_authority",
                "label": expertise.strip(),
                "source": "business_profile",
                "confidence": "confirmed",
            }
        )

    return signals


def format_prompt_block(signals: list[dict[str, Any]]) -> str:
    """Format signals into a prompt section so the LLM uses them in copy."""
    if not signals:
        return ""
    lines: list[str] = ["=== SIGNAUX E-E-A-T (à utiliser en priorité pour la crédibilité) ==="]
    for signal in signals:
        kind = signal.get("kind", "?")
        label = signal.get("label", "")
        source = signal.get("source", "?")
        lines.append(f"  - [{kind}] {label} (source: {source})")
    return "\n".join(lines)


def _value_text(fact: dict[str, Any]) -> str:
    value = fact.get("value")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return ""


def _extract_certifications(text: str) -> list[str]:
    if not text:
        return []
    normalized = " " + _NON_WORD_RE.sub(" ", text.lower()).strip() + " "
    seen: list[str] = []
    for pattern, label in _CERTIFICATION_PATTERNS:
        norm_pattern = " " + _NON_WORD_RE.sub(" ", pattern.lower()).strip() + " "
        if norm_pattern in normalized and label not in seen:
            seen.append(label)
    return seen
