"""Multilingual meta generation — native SEO content in EN, DE, NL, FR via LLM."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from app.llm.batch import _brand_pattern  # shared brand-token regex builder
from app.llm.prompts import load_prompt
from app.llm.provider import LLMError
from app.llm.router import LLMRouter

SUPPORTED_LOCALES: dict[str, str] = {
    "fr": "français",
    "en": "English",
    "de": "Deutsch",
    "nl": "Nederlands",
}

_TITLE_RE = re.compile(r"TITLE:\s*(.+)", re.IGNORECASE)
_DESC_RE = re.compile(r"DESCRIPTION:\s*(.+)", re.IGNORECASE)


@dataclass
class MultilingualMetaResult:
    """LLM-generated meta tags for a single locale.

    Attributes:
        locale: ISO locale code (e.g. "en", "de").
        locale_name: Human-readable language name (e.g. "English").
        title: Generated SEO meta title.
        description: Generated SEO meta description.
        provider: LLM provider used.
        error: Error message if generation failed, None on success.
    """

    locale: str
    locale_name: str
    title: str = ""
    description: str = ""
    provider: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.title)


def _primary_keyword(product_title: str, brand: str | None = None) -> str:
    """Derive primary keyword from title — brand name stripped, lowercase."""
    pattern = _brand_pattern(brand)
    if pattern is None:
        return product_title.lower()
    base = pattern.sub("", product_title).strip(" -–")
    return (base or product_title).lower()


def _parse_response(text: str) -> tuple[str, str]:
    """Extract TITLE and DESCRIPTION from LLM response."""
    title = ""
    description = ""
    m = _TITLE_RE.search(text)
    if m:
        title = m.group(1).strip().strip('"').strip("'")
    m = _DESC_RE.search(text)
    if m:
        description = m.group(1).strip().strip('"').strip("'")
    return title, description


def generate_meta_locale(
    product: dict,
    locale: str,
    router: LLMRouter,
    *,
    brand: str | None = None,
) -> MultilingualMetaResult:
    """Generate SEO meta title and description for a product in a specific locale.

    Args:
        product: Shopify product dict (title, product_type, body_html, id, vendor).
        locale: Target locale code — must be in SUPPORTED_LOCALES.
        router: Configured LLMRouter instance.
        brand: Merchant brand to use in the generated copy. When None, falls
               back to the product's `vendor` field. Always pass the tenant
               config brand in multi-tenant contexts.

    Returns:
        MultilingualMetaResult with title and description on success.

    Raises:
        ValueError: If locale is not supported.
    """
    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported locale '{locale}'. Supported: {list(SUPPORTED_LOCALES)}")

    locale_name = SUPPORTED_LOCALES[locale]
    result = MultilingualMetaResult(locale=locale, locale_name=locale_name)

    product_title = str(product.get("title", ""))
    product_type = str(product.get("product_type", "accessoire animal"))
    effective_brand = brand or str(product.get("vendor", "")) or ""
    primary_keyword = _primary_keyword(product_title, effective_brand)

    # Extract secondary keywords from NER entities if available
    entities = product.get("_entities")
    secondary_keywords: list[str] = entities.all_keywords[:4] if entities else []

    try:
        tmpl = load_prompt("meta_multilingual")
        system = tmpl.render_system(locale=locale, locale_name=locale_name)
        prompt = tmpl.render_user(
            product_title=product_title,
            product_type=product_type,
            brand=effective_brand,
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            locale=locale,
            locale_name=locale_name,
        )
        completion = router.complete(
            prompt,
            system=system,
            max_tokens=tmpl.max_tokens,
            temperature=tmpl.temperature,
        )
        title, description = _parse_response(completion.text)
        if not title:
            result.error = "LLM response missing TITLE field"
            return result

        result.title = title
        result.description = description
        result.provider = completion.provider
    except LLMError as exc:
        result.error = str(exc)

    return result


def generate_meta_all_locales(
    product: dict,
    locales: list[str],
    router: LLMRouter,
    *,
    brand: str | None = None,
    max_workers: int = 4,
) -> list[MultilingualMetaResult]:
    """Generate SEO meta tags for a product across multiple locales in parallel.

    Args:
        product: Shopify product dict.
        locales: List of locale codes to generate for.
        router: Configured LLMRouter instance.
        brand: Merchant brand passed through to every per-locale generation.
               Falls back to product.vendor when None.
        max_workers: Thread pool size (default 4 — one per locale).

    Returns:
        List of MultilingualMetaResult, one per locale, in input order.
    """
    invalid = [l for l in locales if l not in SUPPORTED_LOCALES]  # noqa: E741
    if invalid:
        raise ValueError(f"Unsupported locales: {invalid}. Supported: {list(SUPPORTED_LOCALES)}")

    if len(locales) == 1:
        return [generate_meta_locale(product, locales[0], router, brand=brand)]

    results_map: dict[str, MultilingualMetaResult] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(generate_meta_locale, product, locale, router, brand=brand): locale
            for locale in locales
        }
        for future in as_completed(futures):
            locale = futures[future]
            try:
                results_map[locale] = future.result()
            except (RuntimeError, TypeError, ValueError) as exc:
                results_map[locale] = MultilingualMetaResult(
                    locale=locale,
                    locale_name=SUPPORTED_LOCALES[locale],
                    error=str(exc),
                )

    return [results_map[l] for l in locales]  # noqa: E741
