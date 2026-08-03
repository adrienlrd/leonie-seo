"""Localized, niche-neutral wording for blog idea suggestions.

Blog ideas are assembled deterministically (no LLM), so their wording has to be
translated here rather than prompted. The seasonal calendar used to key on
pet-shop vocabulary in French ("manteau", "mue", "poil"), which meant two
things: the copy was French on every store, and the seasonal angle never fired
at all outside a French pet shop, since no English product title contains
"manteau".

Triggers are now everyday seasonal words per language, so they match whatever
the merchant sells — a winter coat and a snowboard jacket both say "winter".

Placeholders: `{theme}` season label, `{title}` product title, `{keyword}`
primary keyword, `{query}` trending query, `{brand}` competitor brand,
`{event}` real-time event headline.
"""

from __future__ import annotations

from typing import Any

from app.language import DEFAULT_LANGUAGE

# Month → season key. Shared across languages; only the words differ.
SEASON_BY_MONTH: dict[int, str] = {
    1: "winter_cold",
    2: "winter_cold",
    3: "spring",
    4: "spring_outdoors",
    5: "fair_weather",
    6: "summer_heat",
    7: "heatwave",
    8: "heatwave",
    9: "back_to_school",
    10: "autumn",
    11: "pre_winter",
    12: "holidays",
}

# Season key → substrings looked for in the product title/keywords, per language.
# Deliberately generic: seasonal context, not product categories.
SEASON_TRIGGERS: dict[str, dict[str, tuple[str, ...]]] = {
    "fr": {
        "winter_cold": ("hiver", "froid", "chaud", "thermiq", "manteau", "isol", "neige"),
        "spring": ("printemps", "saison", "renouveau", "allerg", "nettoy"),
        "spring_outdoors": ("promenade", "extérieur", "randonn", "sortie", "plein air"),
        "fair_weather": ("voyage", "transport", "vacances", "sortie", "extérieur"),
        "summer_heat": ("été", "chaleur", "fraîch", "eau", "hydrat", "ventil", "solaire"),
        "heatwave": ("canicule", "chaleur", "fraîch", "eau", "hydrat", "solaire", "ombre"),
        "back_to_school": ("rentrée", "routine", "organisation", "quotidien", "rangement"),
        "autumn": ("automne", "pluie", "humid", "intérieur", "imperméab"),
        "pre_winter": ("hiver", "froid", "chaud", "couverture", "isol", "confort"),
        "holidays": ("cadeau", "fêtes", "noël", "offrir", "coffret"),
    },
    "en": {
        "winter_cold": ("winter", "cold", "warm", "thermal", "coat", "insulat", "snow"),
        "spring": ("spring", "season", "allerg", "clean", "fresh"),
        "spring_outdoors": ("outdoor", "walk", "hike", "trail", "trip"),
        "fair_weather": ("travel", "transport", "holiday", "vacation", "outdoor"),
        "summer_heat": ("summer", "heat", "cool", "water", "hydrat", "fan", "sun"),
        "heatwave": ("heatwave", "heat", "cool", "water", "hydrat", "sun", "shade"),
        "back_to_school": ("back to school", "routine", "organis", "everyday", "storage"),
        "autumn": ("autumn", "fall", "rain", "damp", "indoor", "waterproof"),
        "pre_winter": ("winter", "cold", "warm", "blanket", "insulat", "comfort"),
        "holidays": ("gift", "holiday", "christmas", "present", "bundle"),
    },
    "de": {
        "winter_cold": ("winter", "kalt", "warm", "thermo", "mantel", "isolier", "schnee"),
        "spring": ("frühling", "saison", "allerg", "reinig", "frisch"),
        "spring_outdoors": ("draußen", "spaziergang", "wander", "ausflug", "outdoor"),
        "fair_weather": ("reise", "transport", "urlaub", "ausflug", "draußen"),
        "summer_heat": ("sommer", "hitze", "kühl", "wasser", "hydrat", "ventilator", "sonne"),
        "heatwave": ("hitzewelle", "hitze", "kühl", "wasser", "hydrat", "sonne", "schatten"),
        "back_to_school": ("schulanfang", "routine", "organis", "alltag", "aufbewahr"),
        "autumn": ("herbst", "regen", "feucht", "drinnen", "wasserdicht"),
        "pre_winter": ("winter", "kalt", "warm", "decke", "isolier", "komfort"),
        "holidays": ("geschenk", "feiertag", "weihnacht", "schenken", "set"),
    },
    "es": {
        "winter_cold": ("invierno", "frío", "frio", "cálid", "térmic", "abrigo", "aisl", "nieve"),
        "spring": ("primavera", "temporada", "alerg", "limpie", "fresc"),
        "spring_outdoors": ("paseo", "exterior", "senderis", "salida", "aire libre"),
        "fair_weather": ("viaje", "transporte", "vacaciones", "salida", "exterior"),
        "summer_heat": ("verano", "calor", "fresc", "agua", "hidrat", "ventilador", "solar"),
        "heatwave": ("ola de calor", "calor", "fresc", "agua", "hidrat", "solar", "sombra"),
        "back_to_school": ("vuelta al cole", "rutina", "organiz", "día a día", "almacenaj"),
        "autumn": ("otoño", "lluvia", "húmed", "interior", "impermeab"),
        "pre_winter": ("invierno", "frío", "frio", "manta", "aisl", "confort"),
        "holidays": ("regalo", "fiestas", "navidad", "obsequi", "estuche"),
    },
}

SEASON_LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "winter_cold": "Froid de l'hiver",
        "spring": "Retour du printemps",
        "spring_outdoors": "Printemps & sorties",
        "fair_weather": "Beaux jours",
        "summer_heat": "Chaleur estivale",
        "heatwave": "Canicule",
        "back_to_school": "Rentrée",
        "autumn": "Automne",
        "pre_winter": "Pré-hiver",
        "holidays": "Fêtes de fin d'année",
    },
    "en": {
        "winter_cold": "Winter cold",
        "spring": "Spring is back",
        "spring_outdoors": "Spring & outdoors",
        "fair_weather": "Fair weather",
        "summer_heat": "Summer heat",
        "heatwave": "Heatwave",
        "back_to_school": "Back to school",
        "autumn": "Autumn",
        "pre_winter": "Early winter",
        "holidays": "Holiday season",
    },
    "de": {
        "winter_cold": "Winterkälte",
        "spring": "Frühlingsanfang",
        "spring_outdoors": "Frühling & Draußen",
        "fair_weather": "Schöne Tage",
        "summer_heat": "Sommerhitze",
        "heatwave": "Hitzewelle",
        "back_to_school": "Schulanfang",
        "autumn": "Herbst",
        "pre_winter": "Vorwinter",
        "holidays": "Festtage",
    },
    "es": {
        "winter_cold": "Frío del invierno",
        "spring": "Vuelve la primavera",
        "spring_outdoors": "Primavera y aire libre",
        "fair_weather": "Buen tiempo",
        "summer_heat": "Calor del verano",
        "heatwave": "Ola de calor",
        "back_to_school": "Vuelta al cole",
        "autumn": "Otoño",
        "pre_winter": "Antes del invierno",
        "holidays": "Fiestas de fin de año",
    },
}

# angle → {title, intro, outline[], source_label} per language.
IDEA_TEMPLATES: dict[str, dict[str, dict[str, Any]]] = {
    "fr": {
        "seasonal": {
            "title": "{theme} : bien choisir {title}",
            "intro": "À l'approche de la période « {theme} », voici en quoi {title} est utile, et comment bien le choisir.",
            "outline": [
                "Pourquoi {title} est utile pendant cette période ?",
                "Comment bien choisir {keyword} ?",
                "Conseils pratiques et erreurs à éviter",
            ],
            "source_label": "Tendance saisonnière · {theme}",
        },
        "trend": {
            "title": "{query} : ce qu'il faut savoir",
            "intro": "« {query} » est une recherche en forte hausse. Voici une réponse claire et nos conseils.",
            "outline": [
                "Qu'est-ce que {query} ?",
                "Comment {title} répond à ce besoin ?",
                "Nos recommandations",
            ],
            "source_label": "Tendance Google (en hausse)",
        },
        "event": {
            "title": "{event} : {title}, la solution du moment",
            "intro": "{event}. Voici pourquoi {title} répond directement à ce besoin, maintenant.",
            "outline": ["{event}", "Comment {title} aide concrètement", "Conseils pratiques"],
            "source_label": "Actualité en temps réel (sourcée)",
        },
        "competitor": {
            "title": "Alternative à {brand} : pourquoi choisir {title} ?",
            "intro": "Vous comparez {brand} et d'autres options ? Voici une alternative et ce qui distingue {title}.",
            "outline": [
                "Ce que propose {brand}",
                "Pourquoi {title} est une bonne alternative",
                "Comparatif : critères qui comptent vraiment",
            ],
            "source_label": "Concurrent détecté · {brand}",
            "keyword": "alternative {brand}",
        },
        "advantages": {
            "title": "Les avantages de {title} : le guide complet",
            "intro": "Découvrez en détail les avantages de {title} et ce qu'il change au quotidien.",
            "outline": [
                "Quels sont les avantages de {title} ?",
                "À qui s'adresse ce produit ?",
                "Comment bien l'utiliser au quotidien ?",
            ],
            "source_label": "Avantages produit",
        },
    },
    "en": {
        "seasonal": {
            "title": "{theme}: choosing the right {title}",
            "intro": "With {theme} coming up, here is why {title} helps, and how to choose it well.",
            "outline": [
                "Why is {title} useful at this time of year?",
                "How do you choose the right {keyword}?",
                "Practical tips and mistakes to avoid",
            ],
            "source_label": "Seasonal trend · {theme}",
        },
        "trend": {
            "title": "{query}: what you need to know",
            "intro": "“{query}” is a fast-rising search. Here is a clear answer and our advice.",
            "outline": [
                "What is {query}?",
                "How does {title} meet that need?",
                "Our recommendations",
            ],
            "source_label": "Google trend (rising)",
        },
        "event": {
            "title": "{event}: {title}, the timely answer",
            "intro": "{event}. Here is why {title} answers that need right now.",
            "outline": ["{event}", "How {title} helps in practice", "Practical tips"],
            "source_label": "Real-time news (sourced)",
        },
        "competitor": {
            "title": "Alternative to {brand}: why choose {title}?",
            "intro": "Comparing {brand} with other options? Here is an alternative and what sets {title} apart.",
            "outline": [
                "What {brand} offers",
                "Why {title} is a solid alternative",
                "Head to head: the criteria that actually matter",
            ],
            "source_label": "Competitor detected · {brand}",
            "keyword": "{brand} alternative",
        },
        "advantages": {
            "title": "The benefits of {title}: the complete guide",
            "intro": "A detailed look at the benefits of {title} and what it changes day to day.",
            "outline": [
                "What are the benefits of {title}?",
                "Who is this product for?",
                "How do you get the most out of it?",
            ],
            "source_label": "Product benefits",
        },
    },
    "de": {
        "seasonal": {
            "title": "{theme}: {title} richtig auswählen",
            "intro": "Zur Zeit von {theme} lesen Sie hier, wofür {title} nützlich ist und wie Sie gut auswählen.",
            "outline": [
                "Warum ist {title} in dieser Zeit nützlich?",
                "Wie wählt man {keyword} richtig aus?",
                "Praktische Tipps und häufige Fehler",
            ],
            "source_label": "Saisonaler Trend · {theme}",
        },
        "trend": {
            "title": "{query}: Was Sie wissen sollten",
            "intro": "„{query}“ ist eine stark steigende Suchanfrage. Hier eine klare Antwort und unsere Tipps.",
            "outline": [
                "Was ist {query}?",
                "Wie deckt {title} diesen Bedarf?",
                "Unsere Empfehlungen",
            ],
            "source_label": "Google-Trend (steigend)",
        },
        "event": {
            "title": "{event}: {title}, die passende Lösung",
            "intro": "{event}. Hier lesen Sie, warum {title} genau jetzt darauf antwortet.",
            "outline": ["{event}", "Wie {title} konkret hilft", "Praktische Tipps"],
            "source_label": "Aktuelle Nachricht (mit Quelle)",
        },
        "competitor": {
            "title": "Alternative zu {brand}: Warum {title} wählen?",
            "intro": "Sie vergleichen {brand} mit anderen Optionen? Hier eine Alternative und was {title} auszeichnet.",
            "outline": [
                "Was {brand} bietet",
                "Warum {title} eine gute Alternative ist",
                "Vergleich: die Kriterien, die wirklich zählen",
            ],
            "source_label": "Wettbewerber erkannt · {brand}",
            "keyword": "{brand} Alternative",
        },
        "advantages": {
            "title": "Die Vorteile von {title}: der komplette Ratgeber",
            "intro": "Ein genauer Blick auf die Vorteile von {title} und was sich im Alltag ändert.",
            "outline": [
                "Was sind die Vorteile von {title}?",
                "Für wen ist dieses Produkt gedacht?",
                "Wie nutzt man es im Alltag am besten?",
            ],
            "source_label": "Produktvorteile",
        },
    },
    "es": {
        "seasonal": {
            "title": "{theme}: elegir bien {title}",
            "intro": "Ante la llegada de {theme}, le explicamos para qué sirve {title} y cómo elegirlo bien.",
            "outline": [
                "¿Por qué {title} es útil en esta época?",
                "¿Cómo elegir bien {keyword}?",
                "Consejos prácticos y errores a evitar",
            ],
            "source_label": "Tendencia estacional · {theme}",
        },
        "trend": {
            "title": "{query}: lo que hay que saber",
            "intro": "«{query}» es una búsqueda en fuerte aumento. Aquí tiene una respuesta clara y nuestros consejos.",
            "outline": [
                "¿Qué es {query}?",
                "¿Cómo responde {title} a esta necesidad?",
                "Nuestras recomendaciones",
            ],
            "source_label": "Tendencia de Google (al alza)",
        },
        "event": {
            "title": "{event}: {title}, la solución del momento",
            "intro": "{event}. Le explicamos por qué {title} responde directamente a esta necesidad, ahora.",
            "outline": ["{event}", "Cómo ayuda {title} en concreto", "Consejos prácticos"],
            "source_label": "Actualidad en tiempo real (con fuente)",
        },
        "competitor": {
            "title": "Alternativa a {brand}: ¿por qué elegir {title}?",
            "intro": "¿Está comparando {brand} con otras opciones? Aquí tiene una alternativa y lo que distingue a {title}.",
            "outline": [
                "Qué ofrece {brand}",
                "Por qué {title} es una buena alternativa",
                "Comparativa: los criterios que de verdad importan",
            ],
            "source_label": "Competidor detectado · {brand}",
            "keyword": "alternativa {brand}",
        },
        "advantages": {
            "title": "Las ventajas de {title}: la guía completa",
            "intro": "Descubra en detalle las ventajas de {title} y qué cambia en el día a día.",
            "outline": [
                "¿Cuáles son las ventajas de {title}?",
                "¿A quién se dirige este producto?",
                "¿Cómo aprovecharlo al máximo cada día?",
            ],
            "source_label": "Ventajas del producto",
        },
    },
}


def templates_for(language: str) -> dict[str, dict[str, Any]]:
    """Return the idea wording templates for a language."""
    return IDEA_TEMPLATES.get(language, IDEA_TEMPLATES[DEFAULT_LANGUAGE])


def season_for(language: str, month: int) -> tuple[str, tuple[str, ...]] | None:
    """Return (localized season label, trigger substrings) for a month."""
    key = SEASON_BY_MONTH.get(month)
    if key is None:
        return None
    labels = SEASON_LABELS.get(language, SEASON_LABELS[DEFAULT_LANGUAGE])
    triggers = SEASON_TRIGGERS.get(language, SEASON_TRIGGERS[DEFAULT_LANGUAGE])
    return labels[key], triggers[key]
