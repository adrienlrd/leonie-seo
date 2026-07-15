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

from app.billing.subscription_store import get_plan_for_shop
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
    keywords: str = "",
    grounded: bool = False,
) -> str:
    voice = f"TON DE MARQUE: {brand_voice}\n" if brand_voice else ""
    kw = (
        f"MOTS-CLÉS À INTÉGRER NATURELLEMENT (sans bourrage, priorité au 1er): {keywords}\n"
        if keywords.strip()
        else ""
    )
    # Grounded calls (Gemini + Google Search) don't expose separate grounding
    # metadata alongside a forced-JSON response (verified live: groundingMetadata
    # is absent from the API response in that combination) — so sources must be
    # requested directly in the JSON schema instead of read from a side channel.
    sources_rule = (
        "7. sources : liste d'objets {url, title}. Pour toute affirmation appuyée par "
        "une recherche web réelle et récente, cite son URL et son titre exacts. "
        "N'invente JAMAIS une URL : si tu n'as pas de source web vérifiable, liste vide.\n"
        if grounded
        else ""
    )
    keys_list = "direct_answer, body, claims_used" + (", sources" if grounded else "")
    return (
        f"TITRE BLOG: {blog_title}\n"
        f"H2 SECTION: {h2_question}\n"
        f"PRODUIT: {product_title}\n"
        f"RÉSUMÉ PRODUIT: {product_summary}\n"
        f"CLIENT CIBLE: {target_customer}\n"
        f"{voice}"
        f"{kw}"
        "FAITS PRODUIT CONFIRMÉS (seule source autorisée pour les affirmations) :\n"
        f"{_format_facts(confirmed_facts)}\n\n"
        "RÈGLES STRICTES :\n"
        "1. direct_answer : 40-60 mots, répond DIRECTEMENT au H2 dès la première phrase. "
        "Format extractible (préférable pour les featured snippets et les citations LLM).\n"
        "2. body : 320-480 mots, détaillé et complet. Plusieurs paragraphes de 2-3 phrases "
        "max, plus une liste à puces (3-5 items) quand c'est pertinent. Développe le contexte, "
        "des exemples concrets et des conseils pratiques. Vocabulaire stable, pas de répétition "
        "du mot-clé principal.\n"
        "3. claims_used : liste d'objets {claim, fact_keys}. Chaque affirmation factuelle "
        "vérifiable DOIT pointer vers une ou plusieurs clés présentes dans les FAITS CONFIRMÉS. "
        "Si une affirmation n'a pas de preuve, retire-la du texte.\n"
        "4. Si la question H2 ne peut pas être répondue avec les faits, écris une "
        "direct_answer générique factuelle (sans promesse) et un body court.\n"
        "5. Texte brut uniquement : jamais de markdown (pas de **gras**, _italique_, # titres). "
        "Tirets `-` autorisés pour les listes à puces, c'est tout.\n"
        "6. Ne présente jamais le produit sous un angle négatif : pas de rubrique "
        "« inconvénients »/« points faibles »/« pourquoi hésiter », pas de prix mentionné "
        "comme un défaut. Si un point d'attention factuel doit être nuancé (ex : entretien "
        "spécifique), formule-le de façon constructive, sans jamais dévaloriser le produit "
        "ni risquer de freiner la vente.\n\n"
        f"{sources_rule}"
        f"Réponds en JSON valide avec EXACTEMENT ces clés : {keys_list}."
    )


def _merge_citations(
    grounding_citations: list[dict[str, Any]], model_sources: Any
) -> list[dict[str, Any]]:
    """Combine groundingMetadata citations (side channel, currently always
    empty when grounded+json_mode are combined — verified live) with sources
    the model wrote directly into its own JSON output (`sources` field, only
    requested when grounded). Deduplicated by URL.
    """
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(grounding_citations or []) + list(model_sources or []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append({"url": url, "title": str(item.get("title") or "")})
    return merged


def generate_section(
    *,
    blog_title: str,
    h2_question: str,
    product_title: str,
    product_summary: str,
    confirmed_facts: list[dict[str, Any]] | None,
    target_customer: str = "",
    brand_voice: str = "",
    keywords: str = "",
    shop: str | None = None,
) -> dict[str, Any]:
    """Generate one blog section. Falls back to empty fields on any LLM/parse failure.

    Grande boutique (agency) shops get a grounded call (Gemini + Google Search),
    so factual claims can carry cited sources (`citations`). Every other plan
    keeps the default gpt-4o-mini chain — `citations` is then always [].
    """
    fallback: dict[str, Any] = {"direct_answer": "", "body": "", "claims_used": [], "citations": []}
    tier = "grounded" if shop and get_plan_for_shop(shop) == "agency" else "default"
    try:
        router = get_router(shop=shop, tier=tier)
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
        keywords=keywords,
        grounded=(tier == "grounded"),
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
            "citations": _merge_citations(completion.citations, parsed.get("sources")),
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
    keywords: str = "",
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
            keywords=keywords,
            shop=shop,
        )
        section["h2"] = question.strip()
        sections.append(section)
    return sections
