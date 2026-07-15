"""On-demand blog idea suggestions: seasonal/trending, competitor alternatives,
and per-product advantage guides.

Built deterministically from data the app already has (latest analysis products,
competitor signals, current month) so it needs no extra LLM or network call. Each
suggestion carries an outline the section generator can turn into a full article.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Marketplaces make poor "alternative to X" blog angles — skip them, keep niche rivals.
_MARKETPLACES = frozenset(
    {"amazon", "cdiscount", "fnac", "ebay", "aliexpress", "rakuten", "leboncoin", "temu", "wish"}
)

# Pet-shop seasonal calendar (FR): month → list of (theme label, trigger keywords).
# Generic enough for any pet niche; an idea is only emitted when a product matches.
_SEASONAL: dict[int, list[tuple[str, tuple[str, ...]]]] = {
    1: [("Froid de l'hiver", ("manteau", "chaud", "froid", "hiver", "pull"))],
    2: [("Froid de l'hiver", ("manteau", "chaud", "froid", "hiver", "pull"))],
    3: [("Retour du printemps", ("mue", "brosse", "poil", "promenade", "allergie"))],
    4: [("Printemps & promenades", ("harnais", "laisse", "promenade", "tique", "puce"))],
    5: [("Beaux jours", ("promenade", "voyage", "transport", "tique", "puce"))],
    6: [("Chaleur estivale", ("fontaine", "eau", "hydratation", "fraîch", "chaleur", "ventil"))],
    7: [("Canicule", ("fontaine", "eau", "hydratation", "fraîch", "chaleur", "coup de chaleur"))],
    8: [("Canicule", ("fontaine", "eau", "hydratation", "fraîch", "chaleur", "voyage"))],
    9: [("Rentrée", ("anti-stress", "anxiété", "solitude", "jouet", "routine"))],
    10: [("Automne", ("poil", "brosse", "mue", "intérieur", "jouet"))],
    11: [("Pré-hiver", ("manteau", "chaud", "couchage", "panier", "couverture"))],
    12: [("Fêtes de fin d'année", ("cadeau", "jouet", "friandise", "panier", "confort"))],
}


def _norm(text: Any) -> str:
    return str(text or "").lower()


def _primary_keyword(product: dict[str, Any]) -> str:
    for kw in product.get("seo_keywords") or []:
        if isinstance(kw, dict) and str(kw.get("query") or "").strip():
            return str(kw["query"]).strip()
    return str(product.get("product_title") or "").strip()


def _product_haystack(product: dict[str, Any]) -> str:
    parts = [_norm(product.get("product_title")), _norm(product.get("product_summary"))]
    parts += [_norm(kw.get("query")) for kw in (product.get("seo_keywords") or []) if isinstance(kw, dict)]
    return " ".join(parts)


def _idea(
    *,
    title: str,
    target_keyword: str,
    intro: str,
    outline: list[str],
    angle: str,
    source_label: str,
    product: dict[str, Any],
    source_url: str = "",
) -> dict[str, Any]:
    return {
        "title": title,
        "target_keyword": target_keyword,
        "intro": intro,
        "outline": outline,
        "angle": angle,
        "source_label": source_label,
        "source_url": source_url,
        "product_id": str(product.get("product_id") or ""),
        "product_title": str(product.get("product_title") or ""),
    }


def _seasonal_ideas(products: list[dict[str, Any]], month: int, limit: int) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for theme_label, triggers in _SEASONAL.get(month, []):
        for product in products:
            hay = _product_haystack(product)
            if not any(t in hay for t in triggers):
                continue
            title = product.get("product_title") or _primary_keyword(product)
            kw = _primary_keyword(product)
            ideas.append(
                _idea(
                    title=f"{theme_label} : bien choisir {title.lower()} pour son animal",
                    target_keyword=kw,
                    intro=f"À l'approche de la période « {theme_label.lower()} », voici comment {title.lower()} aide votre animal, et comment bien le choisir.",
                    outline=[
                        f"Pourquoi {title.lower()} est utile pendant cette période ?",
                        f"Comment bien choisir {kw} ?",
                        "Conseils pratiques et erreurs à éviter",
                    ],
                    angle="seasonal",
                    source_label=f"Tendance saisonnière · {theme_label}",
                    product=product,
                )
            )
            if len(ideas) >= limit:
                return ideas
    return ideas


def _trend_ideas(products: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Use rising Google Trends queries stored on the product (when present)."""
    ideas: list[dict[str, Any]] = []
    for product in products:
        rising = [str(q).strip() for q in (product.get("trend_rising") or []) if str(q).strip()]
        for query in rising:
            ideas.append(
                _idea(
                    title=f"{query.capitalize()} : ce qu'il faut savoir",
                    target_keyword=query,
                    intro=f"« {query} » est une recherche en forte hausse. Voici une réponse claire et nos conseils.",
                    outline=[
                        f"Qu'est-ce que {query} ?",
                        f"Comment {product.get('product_title', '')} répond à ce besoin ?",
                        "Nos recommandations",
                    ],
                    angle="trend",
                    source_label="Tendance Google (en hausse)",
                    product=product,
                )
            )
            if len(ideas) >= limit:
                return ideas
    return ideas


def _event_ideas(
    products: list[dict[str, Any]],
    realtime_signals: dict[str, Any] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Real-time events + rising queries (Gemini + Google Search grounding,
    Grande boutique plan only — `realtime_signals` is None for every other
    shop, so this is a no-op elsewhere). Deterministic assembly, no extra LLM
    call here: matched to a product the same way `_seasonal_ideas` matches by
    keyword overlap, so an idea only appears when it is actually sellable.
    """
    if not realtime_signals or not products:
        return []
    citations = realtime_signals.get("citations") or []
    default_source_url = ""
    if citations and isinstance(citations[0], dict):
        default_source_url = str(citations[0].get("url") or "")

    # The grounded prompt already asks for events/queries scoped to this shop's
    # niche and products (see realtime_trends._build_prompt), so a literal
    # keyword match is a nice-to-have, not a requirement: an event like "canicule"
    # won't literally contain "fontaine", yet is exactly the case this feature
    # exists for. Prefer a real keyword match; fall back to the top product
    # (the seed list is already priority-ordered) so the idea is never dropped.
    def _best_product(text: str) -> dict[str, Any]:
        hay_words = [w for w in _norm(text).split() if len(w) > 3]
        matched = next((p for p in products if any(w in _product_haystack(p) for w in hay_words)), None)
        return matched or products[0]

    ideas: list[dict[str, Any]] = []

    for event in realtime_signals.get("events") or []:
        title_text = str((event or {}).get("title") or "").strip()
        if not title_text:
            continue
        product = _best_product(title_text)
        p_title = product.get("product_title") or _primary_keyword(product)
        source_url = str(event.get("source_url") or "") or default_source_url
        ideas.append(
            _idea(
                title=f"{title_text} : {p_title.lower()}, la solution du moment",
                target_keyword=_primary_keyword(product),
                intro=f"{title_text}. Voici pourquoi {p_title.lower()} répond directement à ce besoin, maintenant.",
                outline=[title_text, f"Comment {p_title.lower()} aide concrètement", "Conseils pratiques"],
                angle="event",
                source_label="Actualité en temps réel (sourcée)",
                source_url=source_url,
                product=product,
            )
        )
        if len(ideas) >= limit:
            return ideas

    for query_item in realtime_signals.get("rising_queries") or []:
        query = str((query_item or {}).get("query") or "").strip()
        if not query:
            continue
        product = _best_product(query)
        p_title = product.get("product_title") or _primary_keyword(product)
        source_url = str(query_item.get("source_url") or "") or default_source_url
        ideas.append(
            _idea(
                title=f"{query.capitalize()} : ce qu'il faut savoir maintenant",
                target_keyword=query,
                intro=f"« {query} » est en hausse en ce moment. Voici une réponse claire, avec {p_title.lower()}.",
                outline=[
                    f"Pourquoi « {query} » est recherché en ce moment",
                    f"Comment {p_title.lower()} répond à ce besoin",
                    "Nos recommandations",
                ],
                angle="event",
                source_label="Tendance en temps réel (Google Search)",
                source_url=source_url,
                product=product,
            )
        )
        if len(ideas) >= limit:
            return ideas
    return ideas


def _competitor_brand(domain: str) -> str:
    name = domain.lower().replace("www.", "")
    name = name.split(".")[0]
    return name.replace("-", " ").title()


def _competitor_ideas(
    products: list[dict[str, Any]],
    competitor_signals: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    seen_domains: set[str] = set()
    first_product = products[0] if products else None
    for sig in competitor_signals or []:
        if not isinstance(sig, dict):
            continue
        domain = _norm(sig.get("domain")).replace("www.", "")
        root = domain.split(".")[0]
        if not domain or root in _MARKETPLACES or domain in seen_domains:
            continue
        keyword = str(sig.get("matched_keyword") or "").strip()
        # Pick the product whose keyword best matches this competitor signal.
        product = next(
            (p for p in products if keyword and keyword.lower() in _product_haystack(p)),
            first_product,
        )
        if not product:
            continue
        seen_domains.add(domain)
        brand = _competitor_brand(domain)
        kw = keyword or _primary_keyword(product)
        title = product.get("product_title") or kw
        ideas.append(
            _idea(
                title=f"Alternative à {brand} : pourquoi choisir {title.lower()} ?",
                target_keyword=f"alternative {brand.lower()}",
                intro=f"Vous comparez {brand} et d'autres options ? Voici une alternative et ce qui distingue {title.lower()}.",
                outline=[
                    f"Ce que propose {brand}",
                    f"Pourquoi {title.lower()} est une bonne alternative",
                    "Comparatif : critères qui comptent vraiment",
                ],
                angle="competitor",
                source_label=f"Concurrent détecté · {brand}",
                product=product,
            )
        )
        if len(ideas) >= limit:
            return ideas
    return ideas


def _advantage_ideas(products: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for product in products:
        title = str(product.get("product_title") or "").strip()
        if not title:
            continue
        kw = _primary_keyword(product)
        ideas.append(
            _idea(
                title=f"Les avantages de {title.lower()} : le guide complet",
                target_keyword=kw,
                intro=f"Découvrez en détail les avantages de {title.lower()} et comment il améliore le quotidien de votre animal.",
                outline=[
                    f"Quels sont les avantages de {title.lower()} ?",
                    "À qui s'adresse ce produit ?",
                    "Comment bien l'utiliser au quotidien ?",
                ],
                angle="advantages",
                source_label="Avantages produit",
                product=product,
            )
        )
        if len(ideas) >= limit:
            return ideas
    return ideas


def build_blog_idea_suggestions(
    *,
    products: list[dict[str, Any]],
    competitor_signals: list[dict[str, Any]] | None = None,
    realtime_signals: dict[str, Any] | None = None,
    now: datetime | None = None,
    max_per_angle: int = 3,
) -> list[dict[str, Any]]:
    """Return blog idea suggestions across event, seasonal, trend, competitor
    and advantage angles. `realtime_signals` (Grande boutique plan only, None
    everywhere else) is ranked first — it is the freshest, most time-sensitive
    signal.
    """
    products = [p for p in (products or []) if isinstance(p, dict) and p.get("product_title")]
    if not products:
        return []
    month = (now or datetime.now()).month
    suggestions: list[dict[str, Any]] = []
    suggestions += _event_ideas(products, realtime_signals, max_per_angle)
    suggestions += _seasonal_ideas(products, month, max_per_angle)
    suggestions += _trend_ideas(products, max_per_angle)
    suggestions += _competitor_ideas(products, competitor_signals or [], max_per_angle)
    suggestions += _advantage_ideas(products, max_per_angle)
    # Dedup by title, keep first occurrence (seasonal/trend prioritized by order).
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for idea in suggestions:
        key = idea["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(idea)
    return unique
