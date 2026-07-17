"""Per-language NLP resources (stopwords, intent signals, origin phrases).

v1 design: consumers use the UNION across the four supported languages
instead of threading the shop language into every deep tokenization call.
Stopword/intent unions are safe (they only filter function words or add
intent detection in the other languages); over-filtering across languages
is negligible for e-commerce keyword text.
"""

from __future__ import annotations

STOPWORDS_DE = {
    "der", "die", "das", "ein", "eine", "einen", "einem", "einer", "und",
    "oder", "aber", "für", "fur", "mit", "von", "aus", "auf", "bei", "nach",
    "über", "uber", "unter", "durch", "gegen", "ohne", "um", "zu", "zum",
    "zur", "im", "in", "am", "an", "ist", "sind", "war", "sein", "ihre",
    "ihr", "sie", "er", "es", "wir", "ich", "du", "nicht", "auch", "wie",
    "was", "wer", "wo", "wann", "warum", "welche", "welcher", "welches",
    "dem", "den", "des", "man", "mehr", "sehr", "noch", "nur", "als", "so",
}

STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "pero",
    "para", "por", "con", "sin", "de", "del", "en", "sobre", "entre", "hasta",
    "desde", "que", "qué", "como", "cómo", "cuando", "cuándo", "donde",
    "dónde", "quien", "quién", "cual", "cuál", "es", "son", "era", "ser",
    "estar", "está", "están", "su", "sus", "mi", "mis", "tu", "tus", "se",
    "lo", "le", "les", "no", "sí", "si", "más", "mas", "muy", "ya", "al",
}

STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "of", "in",
    "on", "at", "by", "to", "into", "over", "under", "about", "against",
    "without", "is", "are", "was", "were", "be", "been", "being", "it",
    "its", "this", "that", "these", "those", "you", "your", "we", "our",
    "they", "their", "he", "she", "his", "her", "not", "also", "how",
    "what", "who", "where", "when", "why", "which", "more", "very", "so",
    "as", "than", "only", "just",
}

INFORMATIONAL_SIGNALS_EN = {
    "how", "why", "when", "what", "which", "difference", "guide", "tips",
    "tutorial", "learn", "understand", "definition", "meaning", "benefits",
    "advantages",
}
INFORMATIONAL_SIGNALS_DE = {
    "wie", "warum", "wann", "was", "welche", "unterschied", "ratgeber",
    "anleitung", "tipps", "lernen", "verstehen", "bedeutung", "vorteile",
}
INFORMATIONAL_SIGNALS_ES = {
    "cómo", "como", "por qué", "cuándo", "qué", "cuál", "diferencia",
    "guía", "guia", "consejos", "tutorial", "aprender", "entender",
    "significado", "ventajas",
}

COMMERCIAL_SIGNALS_EN = {
    "buy", "price", "cheap", "best", "deal", "discount", "sale", "shop",
    "order", "delivery", "shipping", "review", "reviews",
}
COMMERCIAL_SIGNALS_DE = {
    "kaufen", "preis", "günstig", "gunstig", "beste", "bester", "angebot",
    "rabatt", "bestellen", "lieferung", "versand", "vergleich", "erfahrungen",
}
COMMERCIAL_SIGNALS_ES = {
    "comprar", "precio", "barato", "mejor", "oferta", "descuento",
    "rebajas", "pedido", "envío", "envio", "tienda", "comparativa",
    "opiniones", "reseña",
}

ORIGIN_PATTERNS_EN = ("made in usa", "made in america", "made in the usa", "made in uk")
ORIGIN_PATTERNS_DE = ("hergestellt in deutschland", "made in germany", "aus deutschland")
ORIGIN_PATTERNS_ES = ("fabricado en españa", "hecho en españa", "made in spain")

CONFIDENCE_ALIASES_EXTRA = {
    # German
    "hoch": "high", "mittel": "medium", "niedrig": "low", "gering": "low",
    # Spanish
    "alta": "high", "alto": "high", "media": "medium", "medio": "medium",
    "baja": "low", "bajo": "low",
}


def stopwords_all() -> frozenset[str]:
    """Union of en/de/es stopwords — added on top of consumers' French sets."""
    return frozenset(STOPWORDS_EN | STOPWORDS_DE | STOPWORDS_ES)


def informational_signals_all() -> frozenset[str]:
    return frozenset(
        INFORMATIONAL_SIGNALS_EN | INFORMATIONAL_SIGNALS_DE | INFORMATIONAL_SIGNALS_ES
    )


def commercial_signals_all() -> frozenset[str]:
    return frozenset(COMMERCIAL_SIGNALS_EN | COMMERCIAL_SIGNALS_DE | COMMERCIAL_SIGNALS_ES)


def origin_patterns_all() -> tuple[str, ...]:
    return ORIGIN_PATTERNS_EN + ORIGIN_PATTERNS_DE + ORIGIN_PATTERNS_ES
