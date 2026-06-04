"""HTML feature extraction for competitor SEO/GEO analysis."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from app.crawl.mini import extract_html_signals

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'-]*")
_QUESTION_STARTS = (
    "comment",
    "pourquoi",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "combien",
    "où",
    "ou",
    "quand",
    "est-ce",
    "peut-on",
    "dois-je",
)


class _FeatureParser(HTMLParser):
    def __init__(self, base_domain: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_domain = base_domain
        self.skip_depth = 0
        self.current_heading: str | None = None
        self.current_paragraph = False
        self.current_link = False
        self.current_table = False
        self.current_table_text: list[str] = []
        self.text_parts: list[str] = []
        self.paragraphs: list[str] = []
        self.links: list[str] = []
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.h3: list[str] = []
        self.image_count = 0
        self.images_missing_alt_count = 0
        self.list_count = 0
        self.table_texts: list[str] = []
        self.classes_and_ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        attr = {key.lower(): value or "" for key, value in attrs}
        if lower in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return
        class_id = " ".join([attr.get("class", ""), attr.get("id", "")]).strip()
        if class_id:
            self.classes_and_ids.append(class_id.lower())
        if lower in {"h1", "h2", "h3"}:
            self.current_heading = lower
        elif lower == "p":
            self.current_paragraph = True
            self.text_parts.append(" ")
        elif lower == "a":
            self.current_link = True
            if attr.get("href"):
                self.links.append(attr["href"])
        elif lower == "img":
            self.image_count += 1
            if not attr.get("alt", "").strip():
                self.images_missing_alt_count += 1
        elif lower in {"ul", "ol"}:
            self.list_count += 1
        elif lower == "table":
            self.current_table = True
            self.current_table_text = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if lower in {"h1", "h2", "h3"}:
            self.current_heading = None
        elif lower == "p":
            self.current_paragraph = False
        elif lower == "a":
            self.current_link = False
        elif lower == "table" and self.current_table:
            table_text = _normalize_text(" ".join(self.current_table_text))
            if table_text:
                self.table_texts.append(table_text)
            self.current_table = False
            self.current_table_text = []

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = _normalize_text(data)
        if not text:
            return
        self.text_parts.append(text)
        if self.current_table:
            self.current_table_text.append(text)
        if self.current_heading == "h1":
            self.h1.append(text)
        elif self.current_heading == "h2":
            self.h2.append(text)
        elif self.current_heading == "h3":
            self.h3.append(text)
        elif self.current_paragraph:
            self.paragraphs.append(text)


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_jsonld = False
        self.current_parts: list[str] = []
        self.blocks: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "script" and attr.get("type", "").lower() == "application/ld+json":
            self.in_jsonld = True
            self.current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self.in_jsonld:
            return
        raw = "".join(self.current_parts).strip()
        if raw:
            try:
                self.blocks.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
        self.in_jsonld = False
        self.current_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_jsonld:
            self.current_parts.append(data)


def extract_competitor_features(html: str, *, url: str = "") -> dict[str, Any]:
    """Extract structural SEO, GEO/AEO, schema and platform features from HTML."""
    base_domain = urlsplit(url).netloc.lower().removeprefix("www.")
    parser = _FeatureParser(base_domain)
    parser.feed(html or "")
    jsonld_parser = _JsonLdParser()
    jsonld_parser.feed(html or "")
    core = extract_html_signals(html or "")
    text = _normalize_text(" ".join(parser.text_parts))
    text_lower = text.lower()
    schema_types = sorted({*core.get("jsonld_types", []), *_schema_types(jsonld_parser.blocks)})
    schema_types_lower = {str(item).lower() for item in schema_types}
    jsonld_count = len(jsonld_parser.blocks) or _count_jsonld_blocks(html or "")
    faq_questions = _count_faq_questions(parser, schema_types_lower, jsonld_parser.blocks)
    internal_links, external_links = _count_links(parser.links, base_domain)
    word_count = len(_WORD_RE.findall(text))
    short_answers = _count_short_answer_blocks(parser.paragraphs)
    has_product_schema = "product" in schema_types_lower
    has_offer_schema = bool({"offer", "aggregateoffer"} & schema_types_lower)
    has_breadcrumb_schema = "breadcrumblist" in schema_types_lower
    has_faq_schema = "faqpage" in schema_types_lower
    has_article_schema = bool({"article", "blogposting", "newsarticle"} & schema_types_lower)
    has_organization_schema = "organization" in schema_types_lower
    has_faq_block = faq_questions > 0 or has_faq_schema or _class_hint(parser, "faq")
    has_specs_table = _has_product_specs_table(parser.table_texts)
    has_comparison_table = _has_comparison_table(parser.table_texts, text_lower)
    has_shopify_cdn = "cdn.shopify.com" in html.lower() or "myshopify.com" in html.lower()
    features = {
        "url": url,
        "title": core.get("title", ""),
        "title_length": len(core.get("title", "") or ""),
        "meta_description": core.get("meta_description", ""),
        "meta_description_length": len(core.get("meta_description", "") or ""),
        "h1_count": len(parser.h1),
        "h1_text": parser.h1[0] if parser.h1 else "",
        "h2_count": len(parser.h2),
        "h2_texts": parser.h2[:20],
        "h3_count": len(parser.h3),
        "word_count": word_count,
        "paragraph_count": len(parser.paragraphs),
        "image_count": parser.image_count,
        "images_missing_alt_count": parser.images_missing_alt_count,
        "internal_link_count": internal_links,
        "external_link_count": external_links,
        "canonical_present": bool(core.get("canonical")),
        "has_faq_block": has_faq_block,
        "faq_question_count": faq_questions,
        "has_short_answer_block": short_answers > 0,
        "short_answer_block_count": short_answers,
        "has_comparison_table": has_comparison_table,
        "has_bullet_lists": parser.list_count > 0,
        "has_how_to_structure": _contains_any(text_lower, ["comment ", "étape", "etape", "how to"]),
        "has_pros_cons": _contains_any(
            text_lower,
            ["avantages", "inconvénients", "inconvenients", "points forts", "pros", "cons"],
        ),
        "has_buying_guide": _contains_any(
            text_lower,
            [
                "guide d'achat",
                "guide achat",
                "comment choisir",
                "critères de choix",
                "criteres de choix",
            ],
        ),
        "has_definition_block": _has_definition_block(parser.paragraphs),
        "has_reviews_or_social_proof": _contains_any(
            text_lower,
            ["avis client", "avis clients", "étoiles", "etoiles", "trustpilot", "reviews"],
        ),
        "has_product_specs_table": has_specs_table,
        "answerability_score": _answerability_score(
            has_faq_block=has_faq_block,
            has_short_answer=short_answers > 0,
            has_definition=_has_definition_block(parser.paragraphs),
            has_lists=parser.list_count > 0,
            has_schema=has_faq_schema or has_product_schema,
            word_count=word_count,
        ),
        "ai_readability_score": _ai_readability_score(
            word_count=word_count,
            paragraph_count=len(parser.paragraphs),
            h2_count=len(parser.h2),
            has_lists=parser.list_count > 0,
            short_answer_count=short_answers,
        ),
        "jsonld_count": jsonld_count,
        "schema_types": sorted({str(item) for item in schema_types}),
        "has_product_schema": has_product_schema,
        "has_offer_schema": has_offer_schema,
        "has_breadcrumb_schema": has_breadcrumb_schema,
        "has_faq_schema": has_faq_schema,
        "has_article_schema": has_article_schema,
        "has_organization_schema": has_organization_schema,
        "schema_completeness_score": _schema_completeness_score(
            has_product_schema=has_product_schema,
            has_offer_schema=has_offer_schema,
            has_breadcrumb_schema=has_breadcrumb_schema,
            has_faq_schema=has_faq_schema,
            has_organization_schema=has_organization_schema,
        ),
        "is_shopify": has_shopify_cdn or "shopify" in html.lower(),
        "shopify_cdn_detected": has_shopify_cdn,
        "detected_platform": "shopify"
        if has_shopify_cdn or "shopify" in html.lower()
        else "unknown",
    }
    return features


def extract_merchant_product_features(product: dict[str, Any]) -> dict[str, Any]:
    """Build a best-effort merchant feature set from Shopify snapshot fields."""
    seo = product.get("seo") if isinstance(product.get("seo"), dict) else {}
    body_html = (
        product.get("body_html")
        or product.get("descriptionHtml")
        or product.get("description")
        or ""
    )
    title = str(seo.get("title") or product.get("title") or "")
    description = str(seo.get("description") or "")
    html = (
        "<html><head>"
        f"<title>{title}</title>"
        f'<meta name="description" content="{description}">'
        "</head><body>"
        f"{body_html}"
        "</body></html>"
    )
    return extract_competitor_features(html, url=f"/products/{product.get('handle', '')}")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _count_jsonld_blocks(html: str) -> int:
    return len(re.findall(r"<script[^>]+application/ld\+json[^>]*>", html, flags=re.I))


def _count_links(links: list[str], base_domain: str) -> tuple[int, int]:
    internal = external = 0
    for link in links:
        href = link.strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        parsed = urlsplit(href)
        if not parsed.netloc:
            internal += 1
            continue
        domain = parsed.netloc.lower().removeprefix("www.")
        if base_domain and (domain == base_domain or domain.endswith(f".{base_domain}")):
            internal += 1
        else:
            external += 1
    return internal, external


def _count_faq_questions(
    parser: _FeatureParser,
    schema_types_lower: set[str],
    jsonld_blocks: list[Any],
) -> int:
    candidates = parser.h2 + parser.h3 + parser.h1
    count = 0
    for text in candidates:
        raw = text.strip().lower()
        if raw.endswith("?") or raw.split(" ", 1)[0] in _QUESTION_STARTS:
            count += 1
    if "faqpage" in schema_types_lower:
        count = max(count, _count_schema_questions(jsonld_blocks))
    return count


def _count_schema_questions(blocks: list[Any]) -> int:
    total = 0
    for block in blocks:
        total += _count_schema_questions_in_node(block)
    return total


def _schema_types(blocks: list[Any]) -> list[str]:
    values: list[str] = []
    for block in blocks:
        values.extend(_schema_types_in_node(block))
    return values


def _schema_types_in_node(node: Any) -> list[str]:
    if isinstance(node, list):
        values: list[str] = []
        for item in node:
            values.extend(_schema_types_in_node(item))
        return values
    if not isinstance(node, dict):
        return []
    values: list[str] = []
    node_type = node.get("@type")
    if isinstance(node_type, list):
        values.extend(str(item) for item in node_type if item)
    elif node_type:
        values.append(str(node_type))
    for value in node.values():
        if isinstance(value, (dict, list)):
            values.extend(_schema_types_in_node(value))
    return values


def _count_schema_questions_in_node(node: Any) -> int:
    if isinstance(node, list):
        return sum(_count_schema_questions_in_node(item) for item in node)
    if not isinstance(node, dict):
        return 0
    node_type = node.get("@type")
    count = 0
    if isinstance(node_type, str) and node_type.lower() == "question":
        count += 1
    elif isinstance(node_type, list) and any(str(item).lower() == "question" for item in node_type):
        count += 1
    for value in node.values():
        if isinstance(value, (dict, list)):
            count += _count_schema_questions_in_node(value)
    return count


def _count_short_answer_blocks(paragraphs: list[str]) -> int:
    return sum(1 for paragraph in paragraphs if 20 <= len(_WORD_RE.findall(paragraph)) <= 80)


def _has_definition_block(paragraphs: list[str]) -> bool:
    for paragraph in paragraphs[:6]:
        lower = paragraph.lower()
        if re.search(r"\b(est un|est une|désigne|designe|correspond à|correspond a)\b", lower):
            return True
    return False


def _has_product_specs_table(table_texts: list[str]) -> bool:
    return any(
        _contains_any(
            text.lower(),
            [
                "dimension",
                "matière",
                "matiere",
                "poids",
                "taille",
                "compatibilité",
                "specification",
            ],
        )
        for text in table_texts
    )


def _has_comparison_table(table_texts: list[str], text_lower: str) -> bool:
    return bool(table_texts) and (
        _contains_any(text_lower, ["comparer", "comparatif", "vs", "différence", "difference"])
        or any(
            _contains_any(text.lower(), ["avantage", "prix", "critère", "critere"])
            for text in table_texts
        )
    )


def _class_hint(parser: _FeatureParser, needle: str) -> bool:
    return any(needle in value for value in parser.classes_and_ids)


def _contains_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _answerability_score(
    *,
    has_faq_block: bool,
    has_short_answer: bool,
    has_definition: bool,
    has_lists: bool,
    has_schema: bool,
    word_count: int,
) -> int:
    score = 10
    score += 25 if has_faq_block else 0
    score += 20 if has_short_answer else 0
    score += 15 if has_definition else 0
    score += 10 if has_lists else 0
    score += 15 if has_schema else 0
    score += 5 if word_count >= 300 else 0
    return max(0, min(100, score))


def _ai_readability_score(
    *,
    word_count: int,
    paragraph_count: int,
    h2_count: int,
    has_lists: bool,
    short_answer_count: int,
) -> int:
    score = 20
    score += 20 if 250 <= word_count <= 1800 else 8 if word_count > 0 else 0
    score += 20 if paragraph_count >= 3 else 5 if paragraph_count else 0
    score += 20 if h2_count >= 2 else 5 if h2_count else 0
    score += 15 if has_lists else 0
    score += min(15, short_answer_count * 5)
    return max(0, min(100, score))


def _schema_completeness_score(
    *,
    has_product_schema: bool,
    has_offer_schema: bool,
    has_breadcrumb_schema: bool,
    has_faq_schema: bool,
    has_organization_schema: bool,
) -> int:
    score = 0
    score += 35 if has_product_schema else 0
    score += 20 if has_offer_schema else 0
    score += 20 if has_breadcrumb_schema else 0
    score += 15 if has_faq_schema else 0
    score += 10 if has_organization_schema else 0
    return max(0, min(100, score))
