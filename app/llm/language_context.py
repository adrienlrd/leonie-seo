"""Per-language prompt fragments injected into every content-generating prompt.

Strategy: prompt INSTRUCTIONS stay in French (they are for the model), the
OUTPUT language and target market are parameterized — the model writes all
merchant-facing content in the shop's language for the shop's market.
"""

from __future__ import annotations

from app.language import DEFAULT_LANGUAGE, get_market

_OUTPUT_LANGUAGE_NAMES = {
    "fr": "français",
    "en": "anglais",
    "de": "allemand",
    "es": "espagnol",
}


def output_instruction(language: str) -> str:
    """One sentence forcing ALL generated content into the target language."""
    name = _OUTPUT_LANGUAGE_NAMES.get(language, _OUTPUT_LANGUAGE_NAMES[DEFAULT_LANGUAGE])
    return (
        f"IMPORTANT : rédige TOUT le contenu proposé (titres, descriptions, FAQ, "
        f"mots-clés, articles) en {name}, la langue de la boutique et de ses clients."
    )


def market_line(language: str) -> str:
    """One sentence anchoring keywords/trends to the target market."""
    market = get_market(language)
    return (
        f"Marché cible : {market.country_label}. Les mots-clés et requêtes doivent "
        f"refléter ce que les acheteurs de ce marché tapent réellement dans Google, "
        f"dans leur langue ({market.language_label})."
    )


def language_context(language: str) -> str:
    """Full block (output + market) appended to system/user prompts."""
    return f"{output_instruction(language)}\n{market_line(language)}"


def grounding_market(language: str) -> tuple[str, str]:
    """(country_label, language_label) for the Gemini grounding prompts."""
    market = get_market(language)
    return market.country_label, market.language_label
