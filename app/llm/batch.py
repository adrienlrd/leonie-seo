"""Concurrent LLM batch generation for Shopify product meta tags."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from app.llm.prompts import load_prompt
from app.llm.provider import LLMError
from app.llm.router import LLMRouter
from app.niche.ner import enrich_product


def _brand_pattern(brand: str | None) -> re.Pattern[str] | None:
    """Compile a case-insensitive regex matching every token of the brand.

    Returns None when the brand is empty or unset — callers then skip the
    brand-stripping step. Splits on whitespace AND non-alphanumeric so
    "Acme Pets" yields a pattern that strips both "acme" and "pets"
    (and similar variants typed by merchants).
    """
    if not brand:
        return None
    tokens = [re.escape(t) for t in re.split(r"\W+", brand) if len(t) > 1]
    if not tokens:
        return None
    return re.compile(r"\b(?:" + "|".join(tokens) + r")\b", re.IGNORECASE)


@dataclass
class MetaResult:
    product_id: str
    product_title: str
    generated_title: str = ""
    generated_description: str = ""
    provider: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.generated_title)


def _primary_keyword(product_title: str, brand: str | None = None) -> str:
    """Derive primary keyword from title — brand name stripped, lowercase.

    Args:
        product_title: The Shopify product title.
        brand: The merchant brand name. When provided, every token of the
               brand is stripped from the title before lowercasing. When
               empty/None, the title is returned as-is.
    """
    pattern = _brand_pattern(brand)
    if pattern is None:
        return product_title.lower()
    base = pattern.sub("", product_title).strip(" -–")
    return (base or product_title).lower()


def _generate_one(product: dict, router: LLMRouter, brand: str | None) -> MetaResult:
    enriched = enrich_product(product)
    product_id = str(enriched.get("id", ""))
    title = str(enriched.get("title", ""))
    product_type = str(enriched.get("product_type", ""))
    body = str(enriched.get("body_html", ""))[:300]
    entities = enriched.get("_entities")

    # Resolve brand: explicit > product.vendor (Shopify field) > None.
    effective_brand = brand or str(enriched.get("vendor", "")) or None
    keyword = _primary_keyword(title, effective_brand)
    category = product_type or "accessoire animal"
    secondary_keywords = entities.all_keywords[:6] if entities else []

    try:
        title_tmpl = load_prompt("meta_title")
        title_prompt = title_tmpl.render_user(
            product_title=title,
            category=category,
            primary_keyword=keyword,
            secondary_keywords=secondary_keywords,
        )
        title_result = router.complete(
            title_prompt,
            system=title_tmpl.render_system(),
            max_tokens=title_tmpl.max_tokens,
            temperature=title_tmpl.temperature,
        )

        desc_tmpl = load_prompt("meta_description")
        desc_prompt = desc_tmpl.render_user(
            product_title=title,
            meta_title=title_result.text,
            primary_keyword=keyword,
            current_description=body,
        )
        desc_result = router.complete(
            desc_prompt,
            system=desc_tmpl.render_system(),
            max_tokens=desc_tmpl.max_tokens,
            temperature=desc_tmpl.temperature,
        )

        return MetaResult(
            product_id=product_id,
            product_title=title,
            generated_title=title_result.text,
            generated_description=desc_result.text,
            provider=title_result.provider,
        )

    except LLMError as exc:
        return MetaResult(
            product_id=product_id,
            product_title=title,
            error=str(exc),
        )


def generate_meta_for_products(
    products: list[dict],
    router: LLMRouter,
    *,
    brand: str | None = None,
    max_workers: int = 10,
) -> list[MetaResult]:
    """Generate meta title + description for each product concurrently.

    Args:
        products: List of Shopify product dicts (id, title, product_type, body_html).
        router: Configured LLMRouter instance.
        brand: Merchant brand name to strip from generated keywords. When None,
               falls back to each product's `vendor` field. Always pass the
               tenant config brand in multi-tenant contexts.
        max_workers: Thread pool size — GPT-4o mini handles ~50 req/min on Tier 1,
                     10 workers gives ~100 products/60 s within that budget.

    Returns:
        List of MetaResult in completion order (not input order).
        Products that fail contain error text and success=False.
    """
    if not products:
        return []

    results: list[MetaResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_generate_one, p, router, brand): p for p in products}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except (RuntimeError, TypeError, ValueError) as exc:  # pragma: no cover
                product = futures[future]
                results.append(
                    MetaResult(
                        product_id=str(product.get("id", "")),
                        product_title=str(product.get("title", "")),
                        error=f"Unexpected error: {exc}",
                    )
                )

    return results
