# ARCHITECTURE.md — Léonie SEO

## Vue d'ensemble

Léonie SEO est une application SEO Shopify hybride. Le dépôt contient un backend Python/FastAPI, un moteur CLI Click, des scripts d'audit et d'optimisation SEO, des jobs asynchrones, et une app Shopify embedded Remix/React dans `shopify-app/`. L'objectif est de faire évoluer un moteur CLI SEO vers une app Shopify publique avec validation marchande et garde-fous avant application.

## Flux principal

1. Le marchand utilise l'app Shopify embedded dans `shopify-app/`.
2. L'app Remix appelle le backend Python.
3. Le backend FastAPI orchestre les imports, analyses et actions SEO.
4. Les traitements longs passent par les jobs.
5. Les moteurs existants sous `scripts/` sont réutilisés quand possible.
6. Les résultats sont affichés dans l'app et/ou générés dans les rapports.
7. Les écritures Shopify doivent rester supervisées, en dry-run par défaut, avec confirmation explicite.

## Modules principaux

| Module | Rôle | Règle de modification |
|---|---|---|
| `app/` | Backend Python, API, jobs, intégrations, logique applicative. | Modifier avec tests ciblés. Prudence sur OAuth, Billing, jobs et écritures Shopify. |
| `scripts/` | CLI Click et moteurs historiques d'audit, apply et report. | Préserver la compatibilité CLI et le dry-run par défaut. |
| `shopify-app/` | App Shopify embedded Remix, React, App Bridge et Polaris. | Lancer typecheck/build après changement UI. |
| `config/` | Config tenants, niches et prompts. | Ne pas y mettre de valeurs privées. |
| `data/` | Données locales et exports. | Ne pas versionner de données sensibles ou générées. |
| `reports/` | Rapports générés. | Ne versionner que si explicitement demandé. |
| `tests/` | Tests Python. | Ajouter ou mettre à jour les tests avec les changements de logique. |
| `docs/` | Documentation projet, pilote, architecture et handoff. | Garder à jour après changement significatif. |
| `.claude/` | Configuration et subagents Claude Code partagés. | Garder uniquement des paramètres sûrs et partageables. |

## Frontières

- `shopify-app/` porte l'UI Shopify embedded.
- `app/` porte l'API, l'orchestration et les intégrations serveur.
- `scripts/` porte les moteurs CLI réutilisables.
- La logique métier SEO ne doit pas être dupliquée entre Remix et Python.
- Les opérations Shopify sensibles doivent rester centralisées et protégées.
- Les données doivent rester isolées par boutique.

## Intégrations détectées

| Intégration | État |
|---|---|
| Shopify app embedded | Présente via `shopify-app/`. |
| Shopify OAuth | Présent côté application. |
| Shopify Billing | Présent côté backend. |
| Webhooks / conformité Shopify | Présents dans le périmètre projet. |
| FastAPI | Présent dans `app/`. |
| CLI Click | Présent via `scripts/cli.py`. |
| Google Search Console | Présent dans le périmètre Phase 10. |
| PageSpeed / Core Web Vitals | Présent dans le périmètre Phase 10. |
| GA4 | Présent dans le périmètre projet. |
| LLM / IA | Présent via dépendances optionnelles et modules `app/llm/`. |
| Remix / React / TypeScript | Présent dans `shopify-app/`. |
| Polaris / App Bridge | Présent dans `shopify-app/package.json`. |

## Règles de modification

### Stable

- Authentification Shopify
- Billing Shopify
- Webhooks et conformité
- Garde-fous d'écriture Shopify
- Jobs asynchrones
- Commandes CLI documentées

### Peut changer plus facilement

- Documentation
- Texte UI marchand
- Présentation des rapports
- Tests
- Vues en lecture seule

### Nécessite validation ciblée

- Écriture Shopify
- Billing
- OAuth et scopes
- Jobs
- Schéma de données
- Déploiement
- Intégrations externes

## Zones risquées

- `app/oauth/`
- `app/billing/`
- `app/jobs/`
- `app/safety.py`
- `scripts/apply/`
- `shopify-app/shopify.app*.toml`
- `render.yaml`
- `.env.example`

## Exemples

✅ Good change: ajouter une carte UI en lecture seule qui consomme un endpoint existant, puis lancer `cd shopify-app && npm run typecheck` et `cd shopify-app && npm run build`.

✅ Good change: ajouter un endpoint FastAPI qui réutilise un détecteur existant dans `scripts/audit/`, avec tests ciblés.

❌ Bad change: créer un second moteur de détection dans Remix alors qu'une logique Python existe déjà.

❌ Bad change: ajouter un chemin d'écriture Shopify sans dry-run, confirmation explicite et garde-fou pilot-safe.

❌ Bad change: changer le gestionnaire de package Node sans demande explicite.
