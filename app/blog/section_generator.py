"""Per-H2 blog section generator, grounded on confirmed product facts.

Each section is produced as { direct_answer (40-60 words), body (150-300 words),
claims_used }. The direct answer is the LLM-citable chunk that ChatGPT/Gemini
quote when the H2 question is asked. The body backs it up. ``claims_used`` ties
every factual claim to a confirmed Shopify fact key — no invention.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm import LLMError, get_router

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Tu es un rédacteur SEO + GEO pour boutiques Shopify. "
    "Réponds toujours en JSON valide et rien d'autre. "
    "N'invente jamais un fait : si une affirmation n'a pas de preuve dans les FAITS "
    "PRODUIT CONFIRMÉS, retire-la."
)

_OUTPUT_KEYS = ("direct_answer", "body", "claims_used")


def _format_facts(confirmed_facts: list[dict[str, Any]] | None) -> str:
    if not confirmed_facts:
        return "  - (aucun fait confirmé)"
    lines: list[str] = []
    for fact in confirmed_facts:
        if not isinstance(fact, dict):
            continue
        key = fact.get("key")
        if not key:
            continue
        value = str(fact.get("value", ""))[:200]
        lines.append(f"  - {key}: {value}")
    return "\n".join(lines) or "  - (aucun fait confirmé)"


def _build_prompt(
    *,
    blog_title: str,
    h2_question: str,
    product_title: str,
    product_summary: str,
    confirmed_facts: list[dict[str, Any]] | None,
    target_customer: str,
    brand_voice: str,
) -> str:
    voice = f"TON DE MARQUE: {brand_voice}\n" if brand_voice else ""
    return (
        f"TITRE BLOG: {blog_title}\n"
        f"H2 SECTION: {h2_question}\n"
        f"PRODUIT: {product_title}\n"
        f"RÉSUMÉ PRODUIT: {product_summary}\n"
        f"CLIENT CIBLE: {target_customer}\n"
        f"{voice}"
        "FAITS PRODUIT CONFIRMÉS (seule source autorisée pour les affirmations) :\n"
        f"{_format_facts(confirmed_facts)}\n\n"
        "RÈGLES STRICTES :\n"
        "1. direct_answer : 40-60 mots, répond DIRECTEMENT au H2 dès la première phrase. "
        "Format extractible (préférable pour les featured snippets et les citations LLM).\n"
        "2. body : 150-300 mots. Paragraphes de 2-3 phrases max. Liste à puces (3-5 items) "
        "quand c'est pertinent. Vocabulaire stable, pas de répétition du mot-clé principal.\n"
        "3. claims_used : liste d'objets {claim, fact_keys}. Chaque affirmation factuelle "
        "vérifiable DOIT pointer vers une ou plusieurs clés présentes dans les FAITS CONFIRMÉS. "
        "Si une affirmation n'a pas de preuve, retire-la du texte.\n"
        "4. Si la question H2 ne peut pas être répondue avec les faits, écris une "
        "direct_answer générique factuelle (sans promesse) et un body court.\n\n"
        "Réponds en JSON valide avec EXACTEMENT ces clés : direct_answer, body, claims_used."
    )


def generate_section(
    *,
    blog_title: str,
    h2_question: str,
    product_title: str,
    product_summary: str,
    confirmed_facts: list[dict[str, Any]] | None,
    target_customer: str = "",
    brand_voice: str = "",
    shop: str | None = None,
) -> dict[str, Any]:
    """Generate one blog section. Falls back to empty fields on any LLM/parse failure."""
    fallback: dict[str, Any] = {"direct_answer": "", "body": "", "claims_used": []}
    try:
        router = get_router(shop=shop)
    except LLMError:
        return fallback

    prompt = _build_prompt(
        blog_title=blog_title,
        h2_question=h2_question,
        product_title=product_title,
        product_summary=product_summary,
        confirmed_facts=confirmed_facts,
        target_customer=target_customer,
        brand_voice=brand_voice,
    )

    try:
        completion = router.complete(
            prompt,
            system=_SYSTEM,
            max_tokens=2048,
            temperature=0.0,
            json_mode=True,
        )
        parsed = json.loads(completion.text.strip())
        if not isinstance(parsed, dict):
            return fallback
        return {
            "direct_answer": str(parsed.get("direct_answer", "") or ""),
            "body": str(parsed.get("body", "") or ""),
            "claims_used": [c for c in (parsed.get("claims_used") or []) if isinstance(c, dict)],
        }
    except (json.JSONDecodeError, LLMError) as exc:
        logger.warning("Blog section generation failed for %r: %s", h2_question, exc)
    except Exception as exc:  # pragma: no cover — last-resort safety
        logger.warning("Unexpected error generating section %r: %s", h2_question, exc)
    return fallback


def generate_all_sections(
    *,
    blog_title: str,
    h2_questions: list[str],
    product_title: str,
    product_summary: str,
    confirmed_facts: list[dict[str, Any]] | None,
    target_customer: str = "",
    brand_voice: str = "",
    shop: str | None = None,
) -> list[dict[str, Any]]:
    """Generate every section sequentially. One missing section never blocks the rest."""
    sections: list[dict[str, Any]] = []
    for question in h2_questions:
        if not isinstance(question, str) or not question.strip():
            continue
        section = generate_section(
            blog_title=blog_title,
            h2_question=question.strip(),
            product_title=product_title,
            product_summary=product_summary,
            confirmed_facts=confirmed_facts,
            target_customer=target_customer,
            brand_voice=brand_voice,
            shop=shop,
        )
        section["h2"] = question.strip()
        sections.append(section)
    return sections
