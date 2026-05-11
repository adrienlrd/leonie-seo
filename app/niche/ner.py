"""Rule-based NER for Shopify product descriptions — pet accessories domain."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class ProductEntities:
    """Structured entities extracted from a product description.

    Attributes:
        materials: Fabric/material terms found (cuir, nylon, coton…).
        certifications: Quality/eco certifications (OEKO-TEX, bio, vegan…).
        origins: Geographic or manufacturing origins (France, made in France…).
        targets: Animal/size targets (chien, chiot, petit chien…).
        properties: Functional properties (imperméable, réglable, lavable…).
    """

    materials: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    origins: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)

    @property
    def all_keywords(self) -> list[str]:
        """Flat deduplicated list of all entities, ordered by category priority."""
        seen: set[str] = set()
        result: list[str] = []
        for kw in (
            self.certifications
            + self.origins
            + self.materials
            + self.properties
            + self.targets
        ):
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result

    @property
    def is_empty(self) -> bool:
        return not any([self.materials, self.certifications, self.origins, self.targets, self.properties])


# ---------------------------------------------------------------------------
# Curated vocabulary — pet accessories FR
# ---------------------------------------------------------------------------

# Each entry: (canonical_form, [variant_patterns…])
# Patterns are matched case-insensitively after accent normalisation.

_MATERIALS: list[tuple[str, list[str]]] = [
    ("cuir", ["cuir", "leather"]),
    ("nylon", ["nylon"]),
    ("coton", ["coton", "cotton"]),
    ("laine", ["laine", "wool"]),
    ("velours", ["velours", "velvet"]),
    ("polyester", ["polyester"]),
    ("neoprene", ["neoprene", "néoprène"]),
    ("chanvre", ["chanvre", "hemp"]),
    ("bambou", ["bambou", "bamboo"]),
    ("lin", ["lin", "linen"]),
    ("caoutchouc", ["caoutchouc", "rubber"]),
    ("silicone", ["silicone"]),
    ("metal", ["metal", "métal", "acier", "steel", "aluminium", "inox"]),
    ("corde", ["corde", "rope", "cordon"]),
    ("toile", ["toile", "canvas"]),
    ("plastique", ["plastique", "plastic"]),
    ("ceramique", ["ceramique", "céramique", "ceramic"]),
    ("bois", ["bois", "wood"]),
    ("mousse", ["mousse", "foam", "memory foam"]),
]

_CERTIFICATIONS: list[tuple[str, list[str]]] = [
    ("OEKO-TEX", ["oeko.?tex", "oeko tex"]),
    ("GOTS", ["gots"]),
    ("bio", [r"\bbio\b", r"\borganique\b", r"\borganic\b"]),
    ("vegan", [r"\bvegan\b", r"\bvégétalien\b"]),
    ("recyclé", ["recycl[eé]", "recycled", "upcycl[eé]", r"\beco.?friendly\b"]),
    ("fait main", ["fait main", "handmade", r"\bartisanal"]),
    ("certifié", [r"certifi[eé]"]),
    ("éco-responsable", ["éco.responsable", "eco.responsable", r"\bdurable\b"]),
    ("sans BPA", ["sans bpa", "bpa.?free"]),
]

_ORIGINS: list[tuple[str, list[str]]] = [
    ("fabriqué en France", [r"fabriqu[ée] en france", r"made in france", r"origine france"]),
    ("made in Italy", [r"made in italy", r"fabriqué en italie"]),
    ("made in Portugal", [r"made in portugal", r"fabriqué au portugal"]),
    ("Europe", [r"\beurope\b", r"europ[eé]en"]),
    ("France", [r"\bfrance\b"]),
]

_TARGETS: list[tuple[str, list[str]]] = [
    ("chiot", [r"\bchiots?\b", r"\bpuppy\b"]),
    ("petit chien", [r"petit.?chien", r"petite.?race", r"petite taille", r"\bsmall dog\b"]),
    ("grand chien", [r"grand.?chien", r"grande.?race", r"grande taille", r"\blarge dog\b"]),
    ("chien", [r"\bchien\b", r"\bdog\b", r"\bcanin\b"]),
    ("chaton", [r"\bchaton\b", r"\bkitten\b"]),
    ("chat", [r"\bchat\b", r"\bcat\b", r"\bfélin\b", r"\bfelin\b"]),
    ("lapin", [r"\blapin\b", r"\brabbit\b"]),
    ("rongeur", [r"\brongeur\b", r"\bhamster\b", r"\bcobaye\b"]),
]

_PROPERTIES: list[tuple[str, list[str]]] = [
    ("imperméable", [r"imperm[eé]able", r"waterproof", r"résistant à l'eau", r"resistant.*eau"]),
    ("réglable", [r"réglable", r"reglable", r"ajustable", r"taille ajustable"]),
    ("lavable", [r"lavable", r"machine.?washable", r"lavage en machine"]),
    ("respirant", [r"respirant", r"breathable"]),
    ("rembourré", [r"rembourr[eé]", r"matelassé", r"padded", r"matelasse"]),
    ("réfléchissant", [r"réfl[eé]chissant", r"reflective", r"haute visibilité", r"haute visibilite"]),
    ("anti-traction", [r"anti.?traction", r"no.?pull", r"sans traction"]),
    ("ergonomique", [r"ergonomique", r"ergonomic", r"anatomique"]),
    ("léger", [r"\bl[eé]ger\b", r"\blégers\b", r"\blightweight\b"]),
    ("solide", [r"\bsolide\b", r"\brésistant\b", r"\bdurable\b", r"\brobuste\b"]),
    ("design", [r"\bdesign\b", r"\bélégant\b", r"\belgant\b", r"\bstylé\b"]),
    ("confortable", [r"confortable", r"comfortable", r"\bconfort\b"]),
]


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase + NFKD accent removal (keeps spaces and punctuation for regex)."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _build_patterns(
    vocab: list[tuple[str, list[str]]],
) -> list[tuple[str, list[re.Pattern[str]]]]:
    compiled = []
    for canonical, variants in vocab:
        patterns = [re.compile(v, re.IGNORECASE) for v in variants]
        compiled.append((canonical, patterns))
    return compiled


_MATERIAL_PATTERNS = _build_patterns(_MATERIALS)
_CERT_PATTERNS = _build_patterns(_CERTIFICATIONS)
_ORIGIN_PATTERNS = _build_patterns(_ORIGINS)
_TARGET_PATTERNS = _build_patterns(_TARGETS)
_PROPERTY_PATTERNS = _build_patterns(_PROPERTIES)


def _match_category(
    text_normalized: str,
    patterns: list[tuple[str, list[re.Pattern[str]]]],
) -> list[str]:
    """Return canonical forms found in text, preserving order of first match."""
    found: list[str] = []
    seen: set[str] = set()
    for canonical, compiled in patterns:
        if canonical in seen:
            continue
        for pat in compiled:
            if pat.search(text_normalized):
                found.append(canonical)
                seen.add(canonical)
                break
    return found


def extract_entities(text: str) -> ProductEntities:
    """Extract product entities from raw text using curated rule-based matching.

    Args:
        text: Any concatenation of product title, description, tags, product_type.
              HTML tags are stripped before matching.

    Returns:
        ProductEntities with matched terms per category.
    """
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", text)
    norm = _normalize(clean)

    return ProductEntities(
        materials=_match_category(norm, _MATERIAL_PATTERNS),
        certifications=_match_category(norm, _CERT_PATTERNS),
        origins=_match_category(norm, _ORIGIN_PATTERNS),
        targets=_match_category(norm, _TARGET_PATTERNS),
        properties=_match_category(norm, _PROPERTY_PATTERNS),
    )


def enrich_product(product: dict) -> dict:
    """Add '_entities' key to a product dict without mutating the original.

    Concatenates title, body_html, product_type, and tags before extraction.

    Args:
        product: Shopify product dict (title, body_html, product_type, tags).

    Returns:
        New dict with '_entities': ProductEntities added.
    """
    tags = product.get("tags", [])
    if isinstance(tags, list):
        tags_text = " ".join(tags)
    elif isinstance(tags, str):
        tags_text = tags
    else:
        tags_text = ""

    text = " ".join(
        filter(
            None,
            [
                str(product.get("title", "")),
                str(product.get("body_html", "")),
                str(product.get("product_type", "")),
                tags_text,
            ],
        )
    )
    return {**product, "_entities": extract_entities(text)}
