"""Help and FAQ endpoint — bilingual (FR/EN) structured FAQ for the dashboard."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/help", tags=["help"])

_FAQ: list[dict] = [
    # ── Getting started ────────────────────────────────────────────────────
    {
        "id": "install-cli",
        "category": "installation",
        "question_fr": "Comment installer l'outil ?",
        "question_en": "How do I install the tool?",
        "answer_fr": (
            "Clonez le dépôt, installez les dépendances avec `pip install -e .`, "
            "copiez `.env.example` en `.env` et remplissez vos identifiants Shopify et Google."
        ),
        "answer_en": (
            "Clone the repository, install dependencies with `pip install -e .`, "
            "copy `.env.example` to `.env` and fill in your Shopify and Google credentials."
        ),
    },
    {
        "id": "first-audit",
        "category": "getting_started",
        "question_fr": "Comment lancer mon premier audit ?",
        "question_en": "How do I run my first audit?",
        "answer_fr": (
            "Exécutez dans l'ordre : `leonie-seo audit crawl` → `leonie-seo audit gsc` → "
            "`leonie-seo audit pagespeed` → `leonie-seo audit detect`. "
            "Puis `leonie-seo report weekly` pour générer le rapport."
        ),
        "answer_en": (
            "Run in order: `leonie-seo audit crawl` → `leonie-seo audit gsc` → "
            "`leonie-seo audit pagespeed` → `leonie-seo audit detect`. "
            "Then `leonie-seo report weekly` to generate the report."
        ),
    },
    {
        "id": "what-is-crawl",
        "category": "getting_started",
        "question_fr": "Qu'est-ce qu'un 'crawl' ?",
        "question_en": "What is a 'crawl'?",
        "answer_fr": (
            "Le crawl prend un snapshot de votre catalogue Shopify : tous les produits, "
            "collections, méta-données et images. Il est stocké localement dans "
            "`data/raw/shopify_snapshot.json` et sert de base à toutes les analyses."
        ),
        "answer_en": (
            "A crawl takes a snapshot of your Shopify catalog: all products, collections, "
            "meta fields and images. It is stored locally in `data/raw/shopify_snapshot.json` "
            "and serves as the basis for all analyses."
        ),
    },
    # ── Apply / fixes ──────────────────────────────────────────────────────
    {
        "id": "apply-dry-run",
        "category": "apply",
        "question_fr": "L'outil peut-il modifier mon site sans confirmation ?",
        "question_en": "Can the tool modify my store without confirmation?",
        "answer_fr": (
            "Non. Tous les scripts `apply` fonctionnent en `--dry-run` par défaut. "
            "Vous voyez un aperçu des modifications avant de passer `--apply` pour les écrire sur Shopify."
        ),
        "answer_en": (
            "No. All `apply` commands run in `--dry-run` mode by default. "
            "You see a preview of the changes before passing `--apply` to write them to Shopify."
        ),
    },
    {
        "id": "rollback",
        "category": "apply",
        "question_fr": "Comment annuler une modification appliquée ?",
        "question_en": "How do I undo an applied change?",
        "answer_fr": (
            "Toutes les modifications sont tracées dans `data/history.db`. "
            "Pour annuler les 5 dernières : `leonie-seo apply rollback --last 5`."
        ),
        "answer_en": (
            "All changes are tracked in `data/history.db`. "
            "To undo the last 5 changes: `leonie-seo apply rollback --last 5`."
        ),
    },
    # ── Plans ──────────────────────────────────────────────────────────────
    {
        "id": "plan-differences",
        "category": "plans",
        "question_fr": "Quelles sont les différences entre les plans ?",
        "question_en": "What are the plan differences?",
        "answer_fr": (
            "Free : audit et détection uniquement. "
            "Pro : audit + rapports + apply meta/alt + hreflang + alertes email (1 boutique). "
            "Agency : toutes les fonctionnalités, boutiques illimitées."
        ),
        "answer_en": (
            "Free: audit and detection only. "
            "Pro: audit + reports + apply meta/alt + hreflang + email alerts (1 store). "
            "Agency: all features, unlimited stores."
        ),
    },
    {
        "id": "plan-expiry",
        "category": "plans",
        "question_fr": "Que se passe-t-il si ma licence expire ?",
        "question_en": "What happens when my license expires?",
        "answer_fr": (
            "Le plan bascule automatiquement en Free. L'audit reste disponible. "
            "Les fonctionnalités d'écriture (apply, rapports, alertes) sont désactivées."
        ),
        "answer_en": (
            "The plan automatically falls back to Free. Auditing remains available. "
            "Write features (apply, reports, alerts) are disabled."
        ),
    },
    {
        "id": "multiple-stores",
        "category": "plans",
        "question_fr": "Puis-je gérer plusieurs boutiques ?",
        "question_en": "Can I manage multiple stores?",
        "answer_fr": (
            "Oui, avec le plan Agency. Chaque boutique a son propre fichier "
            "`config/tenants/XXX.yaml`. Passez `--tenant XXX` aux commandes CLI."
        ),
        "answer_en": (
            "Yes, with the Agency plan. Each store has its own `config/tenants/XXX.yaml` file. "
            "Pass `--tenant XXX` to CLI commands."
        ),
    },
    # ── Data & privacy ────────────────────────────────────────────────────
    {
        "id": "data-privacy",
        "category": "privacy",
        "question_fr": "Mes données Shopify restent-elles sur mon serveur ?",
        "question_en": "Does my Shopify data stay on my server?",
        "answer_fr": (
            "Oui. Léonie SEO est un outil auto-hébergé. Vos tokens d'accès et données produits "
            "ne quittent jamais votre environnement (CLI local ou serveur Docker)."
        ),
        "answer_en": (
            "Yes. Léonie SEO is a self-hosted tool. Your access tokens and product data "
            "never leave your environment (local CLI or Docker server)."
        ),
    },
    # ── Support ───────────────────────────────────────────────────────────
    {
        "id": "support-contact",
        "category": "support",
        "question_fr": "Comment contacter le support ?",
        "question_en": "How do I contact support?",
        "answer_fr": (
            "Ouvrez une issue sur le dépôt GitHub ou envoyez un email à support@leonie-seo.com."
        ),
        "answer_en": ("Open an issue on the GitHub repository or email support@leonie-seo.com."),
    },
    {
        "id": "theme-compatibility",
        "category": "support",
        "question_fr": "L'app est-elle compatible avec tous les thèmes Shopify ?",
        "question_en": "Is the app compatible with all Shopify themes?",
        "answer_fr": (
            "Les fonctions d'audit et de mise à jour meta/alt sont universelles (API Admin). "
            "Le snippet Liquid hreflang doit être intégré manuellement dans `theme.liquid`."
        ),
        "answer_en": (
            "Audit and meta/alt update features are universal (Admin API). "
            "The hreflang Liquid snippet must be manually integrated into `theme.liquid`."
        ),
    },
]

_CATEGORIES: list[dict] = [
    {"id": "installation", "label_fr": "Installation", "label_en": "Installation"},
    {"id": "getting_started", "label_fr": "Premiers pas", "label_en": "Getting started"},
    {"id": "apply", "label_fr": "Appliquer des corrections", "label_en": "Applying fixes"},
    {"id": "plans", "label_fr": "Plans & licences", "label_en": "Plans & licenses"},
    {"id": "privacy", "label_fr": "Données & confidentialité", "label_en": "Data & privacy"},
    {"id": "support", "label_fr": "Support", "label_en": "Support"},
]


@router.get("/faq")
async def get_faq(lang: str = "fr") -> dict:
    """Return structured FAQ entries and categories.

    Args:
        lang: Language code — "fr" (default) or "en".

    Returns:
        Dict with "categories" list and "items" list, each localised to `lang`.
    """
    effective = lang if lang in ("fr", "en") else "fr"
    q_key = f"question_{effective}"
    a_key = f"answer_{effective}"
    label_key = f"label_{effective}"

    categories = [{"id": c["id"], "label": c[label_key]} for c in _CATEGORIES]

    items = [
        {
            "id": item["id"],
            "category": item["category"],
            "question": item[q_key],
            "answer": item[a_key],
        }
        for item in _FAQ
    ]

    return {"categories": categories, "items": items}
