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

from app.billing.quotas import GROUNDED_PLANS
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

# The grounded call answers in prose (Gemini forbids search + forced JSON), so it
# must not be told to reply in JSON.
_GROUNDED_SYSTEM = (
    "Tu es un rédacteur SEO + GEO pour boutiques Shopify. "
    "N'invente jamais un fait : si une affirmation n'a pas de preuve dans les FAITS "
    "PRODUIT CONFIRMÉS ou dans une source web que tu cites, retire-la."
)


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
    # Gemini refuses google_search together with a forced JSON responseMimeType
    # (see app/llm/providers/gemini.py), so a grounded call answers in prose. It
    # used to be asked for JSON anyway: json.loads then raised on every section
    # and the merchant silently got an empty article. Grounded sections are now
    # written in prose and reshaped by `_structure_section`.
    if grounded:
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
            "Rédige cette section d'article, en texte courant, en citant tes sources.\n"
            "1. Commence par une réponse directe de 40-60 mots qui répond au H2 dès la "
            "première phrase.\n"
            "2. Poursuis par 320-480 mots : plusieurs paragraphes de 2-3 phrases, et une "
            "liste à puces de 3-5 items quand c'est pertinent.\n"
            "3. N'affirme aucun fait vérifiable qui ne soit ni dans les FAITS CONFIRMÉS ni "
            "appuyé par une source web que tu cites.\n"
            "4. Jamais de markdown : pas de **gras**, pas de titres. Tirets `-` autorisés "
            "pour les puces.\n"
            "5. Ne présente jamais le produit sous un angle négatif : pas d'« inconvénients », "
            "pas de prix présenté comme un défaut."
        )

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
        "Réponds en JSON valide avec EXACTEMENT ces clés : direct_answer, body, claims_used."
    )


_STRUCTURE_SYSTEM = (
    "Tu reformates un texte en JSON valide et rien d'autre. "
    "Tu n'ajoutes aucun fait, aucune source et aucune phrase absente du texte fourni."
)


def _build_structure_prompt(prose: str) -> str:
    return (
        "Voici une section d'article rédigée en texte courant :\n\n"
        f"{prose}\n\n"
        "Découpe-la sans rien inventer ni retirer de substance :\n"
        "- direct_answer : la réponse directe d'ouverture (40-60 mots).\n"
        "- body : tout le reste du texte, sans markdown.\n"
        "- sources : liste d'objets {url, title} pour les URL citées dans le texte. "
        "N'invente aucune URL ; liste vide s'il n'y en a pas.\n\n"
        "Réponds en JSON valide avec EXACTEMENT ces clés : direct_answer, body, sources."
    )


def _structure_section(shop: str | None, prose: str) -> dict[str, Any] | None:
    """Reshape grounded prose into the section schema, or None if unusable.

    Deliberately the default (ungrounded, cheap) chain: Gemini cannot return
    JSON while searching, so the grounded call writes prose and this call — which
    invents nothing — gives it structure. Same split as
    `app/niche/signals/realtime_trends._structure_events`.
    """
    try:
        router = get_router(shop=shop, tier="default")
        completion = router.complete(
            _build_structure_prompt(prose),
            system=_STRUCTURE_SYSTEM,
            max_tokens=2048,
            temperature=0.0,
            json_mode=True,
        )
        parsed = json.loads(completion.text.strip())
    except (json.JSONDecodeError, LLMError) as exc:
        logger.warning("Blog section structuring failed: %s", exc)
        return None
    return parsed if isinstance(parsed, dict) else None


def _merge_citations(
    grounding_citations: list[dict[str, Any]], model_sources: Any
) -> list[dict[str, Any]]:
    """Combine groundingMetadata citations with URLs found in the prose.

    Grounding metadata is now actually populated: it was always empty while the
    grounded call also forced a JSON mime type. Deduplicated by URL.
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

    Paid plans (see `GROUNDED_PLANS`) get a grounded call (Gemini + Google
    Search), so factual claims can carry cited sources (`citations`). Free
    keeps the default gpt-5.4-nano chain — `citations` is then always [].
    """
    fallback: dict[str, Any] = {"direct_answer": "", "body": "", "claims_used": [], "citations": []}
    tier = "grounded" if shop and get_plan_for_shop(shop) in GROUNDED_PLANS else "default"
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

    if shop:
        from app.language import get_shop_language  # noqa: PLC0415
        from app.llm.language_context import language_context  # noqa: PLC0415

        prompt = f"{prompt}\n\n{language_context(get_shop_language(shop))}"

    grounded = tier == "grounded"
    try:
        completion = router.complete(
            prompt,
            system=_SYSTEM if not grounded else _GROUNDED_SYSTEM,
            max_tokens=2048,
            temperature=0.0,
            json_mode=not grounded,
        )
        if grounded:
            structured = _structure_section(shop, completion.text.strip())
            if structured is None:
                return fallback
            return {
                "direct_answer": str(structured.get("direct_answer", "") or ""),
                "body": str(structured.get("body", "") or ""),
                # claims_used is not asked of the grounded call: it writes prose,
                # and the reshaping call must not invent claim-to-fact mappings.
                "claims_used": [],
                "citations": _merge_citations(completion.citations, structured.get("sources")),
            }
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
