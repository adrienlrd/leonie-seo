"""Localized merchant-question templates for the enrichment step.

These questions are shown to the merchant on the product card ("Improve"), so
they must be written in the shop's app language. They are *not* LLM-generated:
they are fixed templates, which is why they need translating here rather than a
prompt instruction.

Examples are deliberately niche-neutral. They used to be written for a pet-food
catalog ("small dogs that feel the cold", "indoor senior cats"), which read as
nonsense on any other store.

`{query}` is replaced with the product's primary keyword, `{topic}` with the
People-Also-Ask question it answers.
"""

from __future__ import annotations

from app.language import DEFAULT_LANGUAGE

# key → (question, placeholder), per language.
QUESTION_TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "fr": {
        "warranty": (
            "Quelle garantie pouvez-vous confirmer pour « {query} » ?",
            "Ex. garantie 2 ans, avec les conditions exactes.",
        ),
        "compatibility": (
            "Dans quel contexte ou usage principal « {query} » est-il conçu ?",
            "Ex. les situations, conditions ou configurations pour lesquelles il est prévu.",
        ),
        "dimensions": (
            "Quelles dimensions exactes peut-on indiquer pour « {query} » ?",
            "Ex. hauteur, largeur et capacité vérifiées.",
        ),
        "care": (
            "Quel entretien exact recommandez-vous pour « {query} » ?",
            "Ex. étapes de nettoyage et fréquence confirmées.",
        ),
        "materials": (
            "Quels matériaux composent réellement « {query} » ?",
            "Ex. acier inoxydable, coton bio ou silicone.",
        ),
        "origins": (
            "Quelle origine de fabrication pouvez-vous prouver pour « {query} » ?",
            "Ex. fabriqué en France, seulement si confirmé.",
        ),
        "certifications": (
            "Quelle certification vérifiée concerne « {query} » ?",
            "Ex. nom exact du label et périmètre concerné.",
        ),
        "size_recommendation": (
            "Comment un client choisit-il la bonne taille de « {query} » ?",
            "Ex. la mesure à prendre et la correspondance de taille confirmée.",
        ),
        "targets": (
            "À qui s'adresse principalement « {query} » ?",
            "Ex. le profil de client, le niveau ou l'usage auquel il convient le mieux.",
        ),
        "properties": (
            "Quelles sont les 2-3 propriétés distinctives de « {query} » face aux alternatives ?",
            "Ex. fermeture réglable, lavable en machine à 30 °C, durabilité vérifiée.",
        ),
        "delivery": (
            "Quelle information de livraison souhaitez-vous mentionner pour « {query} » ?",
            "Ex. expédié sous 24 h, livraison offerte dès 49 €.",
        ),
        "returns": (
            "Quelle politique de retour ou satisfaction s'applique à « {query} » ?",
            "Ex. retours acceptés 30 jours, remboursement garanti si insatisfait.",
        ),
        "use_cases": (
            "Quel bénéfice concret « {query} » apporte-t-il à vos clients, et quel problème résout-il ?",
            "Ex. la situation du quotidien qu'il améliore et la contrainte qu'il supprime.",
        ),
        "selection_criteria": (
            "Comment un client non-expert devrait-il choisir entre plusieurs « {query} » ?",
            "Ex. selon la taille, l'usage, le budget ou le niveau d'activité.",
        ),
    },
    "en": {
        "warranty": (
            "What warranty can you confirm for “{query}”?",
            "E.g. a 2-year warranty, with the exact conditions.",
        ),
        "compatibility": (
            "What context or main use is “{query}” designed for?",
            "E.g. the situations, conditions or setups it is built for.",
        ),
        "dimensions": (
            "What exact dimensions can you state for “{query}”?",
            "E.g. verified height, width and capacity.",
        ),
        "care": (
            "What exact care do you recommend for “{query}”?",
            "E.g. confirmed cleaning steps and frequency.",
        ),
        "materials": (
            "What materials is “{query}” actually made of?",
            "E.g. stainless steel, organic cotton or silicone.",
        ),
        "origins": (
            "What manufacturing origin can you prove for “{query}”?",
            "E.g. made in Portugal — only if confirmed.",
        ),
        "certifications": (
            "Which verified certification applies to “{query}”?",
            "E.g. the exact label name and what it covers.",
        ),
        "size_recommendation": (
            "How does a customer pick the right size of “{query}”?",
            "E.g. the measurement to take and the confirmed size chart.",
        ),
        "targets": (
            "Who is “{query}” mainly for?",
            "E.g. the customer profile, level or use case it suits best.",
        ),
        "properties": (
            "What are the 2-3 distinctive properties of “{query}” versus the alternatives?",
            "E.g. adjustable fastening, machine washable at 30 °C, verified durability.",
        ),
        "delivery": (
            "What delivery information do you want to state for “{query}”?",
            "E.g. ships within 24h, free delivery over €49.",
        ),
        "returns": (
            "What return or satisfaction policy applies to “{query}”?",
            "E.g. 30-day returns, money back if unsatisfied.",
        ),
        "use_cases": (
            "What concrete benefit does “{query}” bring your customers, and what problem does it solve?",
            "E.g. the everyday situation it improves and the frustration it removes.",
        ),
        "selection_criteria": (
            "How should a non-expert customer choose between several “{query}”?",
            "E.g. by size, use, budget or activity level.",
        ),
    },
    "de": {
        "warranty": (
            "Welche Garantie können Sie für „{query}“ bestätigen?",
            "Z. B. 2 Jahre Garantie, mit den genauen Bedingungen.",
        ),
        "compatibility": (
            "Für welchen Kontext oder Haupteinsatz ist „{query}“ gedacht?",
            "Z. B. die Situationen, Bedingungen oder Konfigurationen, für die es ausgelegt ist.",
        ),
        "dimensions": (
            "Welche genauen Maße können Sie für „{query}“ angeben?",
            "Z. B. geprüfte Höhe, Breite und Kapazität.",
        ),
        "care": (
            "Welche genaue Pflege empfehlen Sie für „{query}“?",
            "Z. B. bestätigte Reinigungsschritte und Häufigkeit.",
        ),
        "materials": (
            "Aus welchen Materialien besteht „{query}“ tatsächlich?",
            "Z. B. Edelstahl, Bio-Baumwolle oder Silikon.",
        ),
        "origins": (
            "Welche Herstellungsherkunft können Sie für „{query}“ belegen?",
            "Z. B. hergestellt in Portugal – nur wenn bestätigt.",
        ),
        "certifications": (
            "Welche geprüfte Zertifizierung betrifft „{query}“?",
            "Z. B. der genaue Name des Siegels und sein Geltungsbereich.",
        ),
        "size_recommendation": (
            "Wie wählt ein Kunde die richtige Größe von „{query}“?",
            "Z. B. das zu nehmende Maß und die bestätigte Größentabelle.",
        ),
        "targets": (
            "Für wen ist „{query}“ hauptsächlich gedacht?",
            "Z. B. das Kundenprofil, das Niveau oder der Anwendungsfall, zu dem es am besten passt.",
        ),
        "properties": (
            "Was sind die 2-3 unterscheidenden Eigenschaften von „{query}“ gegenüber Alternativen?",
            "Z. B. verstellbarer Verschluss, maschinenwaschbar bei 30 °C, geprüfte Haltbarkeit.",
        ),
        "delivery": (
            "Welche Lieferinformation möchten Sie zu „{query}“ angeben?",
            "Z. B. Versand innerhalb von 24 Stunden, kostenlose Lieferung ab 49 €.",
        ),
        "returns": (
            "Welche Rückgabe- oder Zufriedenheitsgarantie gilt für „{query}“?",
            "Z. B. 30 Tage Rückgaberecht, Geld zurück bei Unzufriedenheit.",
        ),
        "use_cases": (
            "Welchen konkreten Nutzen bringt „{query}“ Ihren Kunden und welches Problem löst es?",
            "Z. B. die Alltagssituation, die es verbessert, und das Ärgernis, das es beseitigt.",
        ),
        "selection_criteria": (
            "Wie sollte ein Laie zwischen mehreren „{query}“ wählen?",
            "Z. B. nach Größe, Verwendung, Budget oder Aktivitätsniveau.",
        ),
    },
    "es": {
        "warranty": (
            "¿Qué garantía puede confirmar para «{query}»?",
            "Ej. garantía de 2 años, con las condiciones exactas.",
        ),
        "compatibility": (
            "¿Para qué contexto o uso principal está diseñado «{query}»?",
            "Ej. las situaciones, condiciones o configuraciones para las que está previsto.",
        ),
        "dimensions": (
            "¿Qué dimensiones exactas puede indicar para «{query}»?",
            "Ej. altura, anchura y capacidad verificadas.",
        ),
        "care": (
            "¿Qué mantenimiento exacto recomienda para «{query}»?",
            "Ej. pasos de limpieza y frecuencia confirmados.",
        ),
        "materials": (
            "¿De qué materiales se compone realmente «{query}»?",
            "Ej. acero inoxidable, algodón orgánico o silicona.",
        ),
        "origins": (
            "¿Qué origen de fabricación puede demostrar para «{query}»?",
            "Ej. fabricado en Portugal, solo si está confirmado.",
        ),
        "certifications": (
            "¿Qué certificación verificada se aplica a «{query}»?",
            "Ej. el nombre exacto del sello y su alcance.",
        ),
        "size_recommendation": (
            "¿Cómo elige un cliente la talla correcta de «{query}»?",
            "Ej. la medida a tomar y la equivalencia de tallas confirmada.",
        ),
        "targets": (
            "¿A quién se dirige principalmente «{query}»?",
            "Ej. el perfil de cliente, el nivel o el uso al que mejor se adapta.",
        ),
        "properties": (
            "¿Cuáles son las 2-3 propiedades distintivas de «{query}» frente a las alternativas?",
            "Ej. cierre ajustable, lavable a máquina a 30 °C, durabilidad verificada.",
        ),
        "delivery": (
            "¿Qué información de envío desea indicar para «{query}»?",
            "Ej. enviado en 24 h, envío gratuito a partir de 49 €.",
        ),
        "returns": (
            "¿Qué política de devolución o satisfacción se aplica a «{query}»?",
            "Ej. devoluciones en 30 días, reembolso garantizado si no queda satisfecho.",
        ),
        "use_cases": (
            "¿Qué beneficio concreto aporta «{query}» a sus clientes y qué problema resuelve?",
            "Ej. la situación cotidiana que mejora y la molestia que elimina.",
        ),
        "selection_criteria": (
            "¿Cómo debería elegir un cliente no experto entre varios «{query}»?",
            "Ej. según el tamaño, el uso, el presupuesto o el nivel de actividad.",
        ),
    },
}

# Rationale shown under each question, per language.
WHY_TEMPLATES: dict[str, dict[str, str]] = {
    "fr": {
        "fact": "Permet une réponse factuelle liée à « {topic} ».",
        "answerability": "Améliore la Répondabilité IA — pilier à 20 % dans le Score GEO.",
        "trust": "Améliore le pilier Confiance — à 15 % dans le Score GEO.",
        "use_cases": "Fournit l'angle éditorial central pour un article ou une FAQ qui accroche.",
        "selection_criteria": (
            "Structure un guide d'achat naturellement optimisé pour les requêtes de comparaison."
        ),
    },
    "en": {
        "fact": "Enables a factual answer tied to “{topic}”.",
        "answerability": "Improves AI answerability — a 20% pillar of the GEO Score.",
        "trust": "Improves the Trust pillar — 15% of the GEO Score.",
        "use_cases": "Provides the central editorial angle for an article or FAQ that hooks.",
        "selection_criteria": (
            "Structures a buying guide naturally optimized for comparison queries."
        ),
    },
    "de": {
        "fact": "Ermöglicht eine faktische Antwort zu „{topic}“.",
        "answerability": "Verbessert die KI-Beantwortbarkeit – eine 20-%-Säule des GEO-Scores.",
        "trust": "Verbessert die Säule Vertrauen – 15 % des GEO-Scores.",
        "use_cases": "Liefert den zentralen redaktionellen Ansatz für einen Artikel oder eine FAQ.",
        "selection_criteria": (
            "Strukturiert einen Kaufratgeber, der natürlich für Vergleichsanfragen optimiert ist."
        ),
    },
    "es": {
        "fact": "Permite una respuesta factual ligada a «{topic}».",
        "answerability": "Mejora la respondibilidad por IA: un pilar del 20 % en la puntuación GEO.",
        "trust": "Mejora el pilar de Confianza: el 15 % de la puntuación GEO.",
        "use_cases": "Aporta el ángulo editorial central para un artículo o una FAQ que enganche.",
        "selection_criteria": (
            "Estructura una guía de compra optimizada de forma natural para consultas de comparación."
        ),
    },
}


def questions_for(language: str) -> dict[str, tuple[str, str]]:
    """Return the question/placeholder templates for a language."""
    return QUESTION_TEMPLATES.get(language, QUESTION_TEMPLATES[DEFAULT_LANGUAGE])


def why_for(language: str) -> dict[str, str]:
    """Return the "why it matters" strings for a language."""
    return WHY_TEMPLATES.get(language, WHY_TEMPLATES[DEFAULT_LANGUAGE])
