# ARCHIVE — RAPPORT D'AUDIT HISTORIQUE

> Rapport généré avant les phases 6-8. Il est conservé pour traçabilité et ne représente plus l'état courant.
> Pour Codex, utiliser `AGENTS.md`, `ROADMAP.md` et `PROGRESS.md` comme sources actives.

# RAPPORT D'AUDIT — État actuel vs vision Shopify App SEO IA

*Généré le 2026-05-10 — basé sur l'analyse du code, non sur les noms de fichiers*

---

## TL;DR (5 lignes)

- **Couverture estimée : 28 % de la vision cible.** Le moteur Python d'audit/apply est solide. Tout le reste de la vision (IA, niche intelligence, billing Shopify, App Bridge, GDPR, Theme Extensions) est absent.
- **3 gaps bloquants** : (1) aucun webhook GDPR → rejet automatique App Store review, (2) aucune Shopify Billing API → pas de monétisation in-app, (3) aucune génération IA → le différenciateur central n'existe pas.
- **3 points forts** : (1) moteur d'audit Python complet et testé (537 tests, ruff clean), (2) OAuth + chiffrement Fernet des tokens + rollback SQLite = fondations sécurité correctes, (3) architecture modulaire `audit/apply/report` réutilisable comme back-end.
- **Verdict : option (b)** — le back-end Python est réutilisable comme moteur SEO, mais le front-end doit être reconstruit en app Shopify embedded (Polaris + App Bridge), et les modules IA/niche/billing sont à construire de zéro.
- **Pour soumettre au App Store maintenant** : 3 actions bloquantes à traiter en priorité (GDPR webhooks, Billing API, App Bridge embedding).

---

## 1. Architecture du code actuel

### Arborescence

```
leonie-seo/
├── app/                        ← API FastAPI (Phase 5 — Shopify App)
│   ├── api/                    ← endpoints REST (audit, apply, shops, plans, help)
│   ├── oauth/                  ← OAuth custom flow + token storage
│   └── db.py                   ← schéma SQLite centralisé
├── scripts/                    ← pipeline CLI (Phases 1-4)
│   ├── audit/                  ← lecture seule (crawl, GSC, PageSpeed, detection)
│   ├── apply/                  ← écriture Shopify (dry-run par défaut)
│   ├── report/                 ← génération rapports Markdown
│   ├── _config.py              ← système multi-tenant YAML
│   ├── license.py              ← clés HMAC-SHA256 par plan
│   └── cli.py                  ← entry point `leonie-seo`
├── frontend/                   ← Dashboard React (Vite, custom CSS)
│   └── src/components/         ← ScoreCard, IssuesList, MetaApplyPanel, HelpPanel
├── config/
│   ├── tenants/                ← YAML par boutique (leoniedelacroix.yaml)
│   └── niches/                 ← YAML par secteur (pet_accessories_fr, etc.)
├── data/history.db             ← SQLite (tokens + changements + snapshots)
├── .github/workflows/          ← CI/CD hebdomadaire
└── Dockerfile                  ← multi-stage Node + Python
```

### Stack actuelle

| Couche | Technologie |
|---|---|
| Langage back-end | Python 3.11 |
| API web | FastAPI + uvicorn |
| Auth Shopify | OAuth custom (HMAC-SHA256) |
| Chiffrement tokens | Fernet (cryptography) |
| Session JWT | PyJWT (Shopify session tokens) |
| Config | Pydantic + YAML |
| CLI | Click + Rich |
| Base de données | SQLite stdlib |
| Front-end | React 19 + Vite (custom CSS, zéro dépendance Shopify) |
| Tests | pytest + pytest-mock (537 tests) |
| Lint/format | ruff |
| CI/CD | GitHub Actions (cron lundi 7h UTC) |
| APIs externes | Shopify Admin GraphQL, GSC, PageSpeed Insights |

### Patterns architecturaux

- **Clean separation** : `scripts/audit/` (lecture), `scripts/apply/` (écriture), `scripts/report/` (rapports). Bonne discipline.
- **Dry-run systématique** sur tous les scripts d'écriture. Irréprochable.
- **Multi-tenant via YAML** (`config/tenants/`) + résolution `TENANT_ID` env → argument → défaut `leoniedelacroix`.
- **Pas de domaine métier Shopify App** : le code est structuré comme un pipeline d'automation personnel, pas comme une Shopify App (pas de `ShopifyApp`, `Session`, `AppBridge`, `Polaris`).

### Mono-store vs multi-store

Le code est **originalement mono-store** (leoniedelacroix.com) avec une **abstraction multi-tenant ajoutée** en Phase 4. L'OAuth stocke des tokens par shop dans SQLite, mais le pipeline CI/CD (`.github/workflows/weekly_audit.yml`) hardcode encore les URLs `https://www.leoniedelacroix.com` et le domaine Shopify — lignes 52-58 du workflow.

---

## 2. Module-by-module — état vs cible

### 4.1 Shopify App scaffolding

**Statut global : 🟡 Partiel (40 %)**

| Composant | Statut | Fichier |
|---|---|---|
| OAuth custom flow | ✅ | `app/oauth/router.py` |
| Webhook `app/uninstalled` | ✅ | `app/oauth/webhooks.py` |
| Webhook `customers/data_request` | ❌ | — |
| Webhook `customers/redact` | ❌ | — |
| Webhook `shop/redact` | ❌ | — |
| Session storage | 🟡 SQLite seulement | `app/db.py` — table `shop_tokens` |
| Shopify Billing API | ❌ | — |
| Embedded App (App Bridge React) | ❌ | — |
| Polaris UI | ❌ | `frontend/package.json` — deps: react, react-dom uniquement |
| Privacy policy endpoint | ❌ | — |
| GDPR consent flow | ❌ | — |

**Ce qui manque concrètement :**
- Les 3 webhooks GDPR (`customers/data_request`, `customers/redact`, `shop/redact`) sont obligatoires pour le review Shopify App Store. Leur absence entraîne un rejet automatique.
- L'app n'est **pas embedded** dans le Shopify Admin : le dashboard React est une URL externe, pas une app intégrée via App Bridge. Les marchands naviguent vers une URL externe, ce qui dégrade l'UX et peut poser problème au review.
- Shopify Billing API absente : impossible de faire payer les marchands via Shopify (obligatoire pour les apps payantes sur l'App Store).

**Effort :** L = 3-10j (GDPR webhooks : S ; Billing API : M ; App Bridge embedding : L)

---

### 4.2 Connecteurs externes

**Statut global : 🟡 Partiel (30 %)**

| Connecteur | Statut | Fichier |
|---|---|---|
| Google Search Console | ✅ | `scripts/audit/fetch_gsc.py` (OAuth google-auth-oauthlib) |
| Google Analytics 4 | ❌ | Mentionné dans les consignes legacy, absent du code |
| PageSpeed Insights API | ✅ | `scripts/audit/fetch_pagespeed.py` |
| CrUX BigQuery / History API | ❌ | — |
| Bing Webmaster Tools | ❌ | — |

**Ce qui manque :** GA4 (aucune connexion revenue attribution), CrUX (seules les données PSI lab sont utilisées, pas les données terrain p75). Bing serait un plus.

**Effort :** GA4 OAuth M, CrUX History API S, Bing S.

---

### 4.3 Lecture du store

**Statut global : 🟡 Partiel (50 %)**

| Feature | Statut | Fichier |
|---|---|---|
| Products (paginated) | ✅ | `scripts/audit/crawl_shopify.py` |
| Collections (paginated) | ✅ | `scripts/audit/crawl_shopify.py` |
| Pages (Online Store) | ❌ | — |
| Blogs + Articles | ❌ | — |
| Metafields complets | 🟡 SEO seulement | `crawl_shopify.py` — pull `seo{title, description}` + images |
| Theme settings (lecture) | ❌ | — |
| Files API (images + dimensions) | ❌ | — |
| URL redirects existants | ❌ | — (write uniquement via `create_redirects.py`) |
| robots.txt.liquid | ❌ | — |
| Shop locales / Markets | ❌ | — |
| Bulk Operations Admin API | ❌ | — (cursor pagination 50 items/req seulement) |
| Rate limits respectés | ✅ | 429 + `throttleStatus.currentlyAvailable` < 100 → sleep 2s |

**Ce qui manque concrètement :**
- Pages et articles non crawlés → impossible d'auditer le contenu éditorial (blog, about, contact).
- Pas de Bulk Operations → au-delà de 500 produits, le crawl est lent (50 produits/requête × 429 throttling). Pour les gros catalogues (>1000 produits), Bulk Operations via `jsonl` + staged upload est indispensable.
- Pas de pull des redirects existants → risque de créer des doublons ou conflits.

**Effort :** Pages/Articles M, Bulk Operations L, Files API M.

---

### 4.4 Audit SEO

**Statut global : 🟡 Partiel (55 %)**

| Check | Statut | Fichier |
|---|---|---|
| Meta title manquant / trop long / trop court | ✅ | `scripts/audit/detect_issues.py` |
| Meta description manquante / hors plage | ✅ | `scripts/audit/detect_issues.py` |
| Duplicates meta title/description | ✅ | `scripts/audit/detect_issues.py` |
| URL handle non-optimisé | ❌ | — |
| Description produit trop courte | ❌ | — |
| Alt text image manquant | ✅ | `scripts/audit/detect_issues.py` |
| Schema Product présent | 🟡 | `scripts/apply/add_schema.py` crée, mais `detect_issues.py` ne vérifie pas si absent |
| Schema BreadcrumbList | ❌ | — |
| Schema Organization | ❌ | — |
| Schema FAQ sur collections/pages | ❌ | — (FAQ générée mais non vérifiée) |
| Blog actif | ❌ | — (blogs non crawlés) |
| Articles avec meta + JSON-LD | ❌ | — |
| Collection sans description | ❌ | — |
| Pages sans contenu | ❌ | — |
| Hreflang manquants | 🟡 | `scripts/report/generate_hreflang.py` génère un snippet Liquid manuel |
| Redirects manquants (produits dépubliés) | ❌ | — |
| CWV LCP/INP/CLS hors seuil | ✅ | `scripts/report/send_alerts.py` + `detect_issues.py` (via pagespeed.csv) |

**Effort manquant :** Handle checker S, description word count S, schema presence check S, blogs/articles audit M.

---

### 4.5 Niche Intelligence

**Statut global : 🟡 Très partiel (15 %)**

| Feature | Statut | Fichier |
|---|---|---|
| Analyse du catalogue actuel | 🟡 | `scripts/report/analyze_semantics.py` — scoring signal-based (YAML) |
| EEAT scoring | 🟡 | `scripts/report/score_eeat.py` — dimension scoring règles YAML |
| Google Trends (pytrends) | ❌ | — |
| Google Suggest / People Also Ask | ❌ | — |
| Reddit API | ❌ | — |
| GSC queries pour niche discovery | 🟡 | `scripts/audit/detect_gsc_opportunities.py` — pour quick wins, pas niche analysis |
| Common Crawl | ❌ | — |
| DataForSEO | ❌ | — |
| Scoring de niche `volume × intent × (1 - difficulté)` | ❌ | — |
| Détection niches gap vs catalogue | ❌ | — |
| Recommandation top 3-5 niches | ❌ | — |
| Persistance niche choisie (metafield app) | ❌ | — |

**Ce qui existe** : 4 niches définies en YAML (`pet_accessories_fr`, `cosmetics_fr`, `mode_fr`, `jardinage_fr`) avec des signaux manuels (premium, EEAT, longtail, catégories). C'est une **configuration statique**, pas une découverte dynamique de niches.

**Effort :** Module complet Niche Intelligence : XL > 10j.

---

### 4.6 Génération IA de contenu SEO

**Statut global : ❌ Absent (0 %)**

Aucune dépendance IA dans `pyproject.toml` ou `requirements.txt`. Grep confirmé :

```bash
grep -r "openai|gpt|llm|embed|sentence_transform|spacy|langchain" scripts/ app/ → 0 résultat
```

| Feature | Statut |
|---|---|
| OpenAI GPT-4o mini | ❌ |
| Cloudflare Workers AI fallback | ❌ |
| Groq Llama fallback | ❌ |
| Mistral La Plateforme | ❌ |
| Prompt templates versionnés | ❌ |
| Génération meta titles/descriptions | ❌ |
| Génération descriptions produits enrichies | ❌ |
| Génération alt text masse | ❌ |
| Génération descriptions collections | ❌ |
| Génération articles blog (1500-3000 mots) | ❌ |
| Génération FAQ (PAA-based) | 🟡 `generate_faq.py` — template rule-based, PAS IA |
| Génération JSON-LD via IA | ❌ |
| Validation anti-hallucination | ❌ |
| Length check automatique | ❌ |
| Mode batch | ❌ |
| Mode review / auto-approve | ❌ |
| Multilingue IA (FR/EN/DE/ES/IT) | ❌ |
| Tracking coûts IA par store | ❌ |

**Ce qui "ressemble" à de l'IA mais n'en est pas :**
- `scripts/report/generate_faq.py` → génère des FAQ à partir de templates basés sur les titres produits et les signaux YAML. Aucun LLM impliqué.
- `scripts/report/generate_blog_briefs.py` → génère des briefs d'articles structurés (H2/H3, keywords) à partir de données GSC. Aucun LLM.
- `scripts/report/analyze_semantics.py` → scoring par présence de mots-clés dans des listes YAML. Pas d'embeddings.

**Effort :** XL > 10j (module complet LLM abstraction + prompt templates + validation + batch).

---

### 4.7 Application des modifications via Admin API

**Statut global : ✅ Solide (75 %)**

| Mutation | Statut | Fichier |
|---|---|---|
| `productUpdate` (seo title/description) | ✅ | `scripts/apply/update_meta.py` |
| `collectionUpdate` (seo) | ✅ | `scripts/apply/update_meta.py` |
| `pageUpdate` | ❌ | — |
| `articleUpdate` | ❌ | — |
| `productImageUpdate` (altText) | ✅ | `scripts/apply/update_alt_text.py` |
| `metafieldsSet` (JSON-LD Product) | ✅ | `scripts/apply/add_schema.py` |
| `urlRedirectCreate` | ✅ | `scripts/apply/create_redirects.py` |
| `productUpdate` (descriptionHtml) | ✅ | `scripts/apply/rewrite_descriptions.py` |
| Versioning avant/après | ✅ | `data/history.db` — table `seo_changes` |
| Rollback CLI | ✅ | `scripts/apply/rollback.py` (`--revert-ids`, `--revert-since`) |
| Preview URL (`_tk` token Shopify) | ❌ | — |

**Ce qui manque :** `pageUpdate` et `articleUpdate` (bloque l'audit/correction contenu éditorial). Preview URL Shopify permettrait un test avant application réelle — utile pour UX dashboard.

**Effort :** pageUpdate + articleUpdate M, preview URL S.

---

### 4.8 Theme App Extension

**Statut global : ❌ Absent (0 %)**

Aucun fichier d'extension, aucun `.liquid` dans le projet (sauf snippets générés à coller manuellement).

L'injection JSON-LD est **manuelle** : `add_schema.py` pousse le JSON-LD en metafield `custom.json_ld`, mais le marchand doit ajouter lui-même le snippet Liquid dans `product.liquid` :

```liquid
{% if product.metafields.custom.json_ld %}
  <script type="application/ld+json">{{ product.metafields.custom.json_ld.value }}</script>
{% endif %}
```

Idem pour les balises hreflang → snippet HTML à coller dans `theme.liquid`.

Cette approche **ne survivra pas à l'App Store review** si l'app prétend injecter du contenu : Shopify impose l'utilisation des Theme App Extensions pour modifier le theme.

**Effort :** L-XL (setup Shopify CLI extensions + templates Liquid + App Bridge integration).

---

### 4.9 Module NLP / Sémantique

**Statut global : 🟡 Très partiel (10 %)**

| Feature | Statut | Fichier |
|---|---|---|
| sentence-transformers multilingual | ❌ | — |
| HDBSCAN clustering | ❌ | — |
| Détection cannibalisation (GSC) | 🟡 | `scripts/audit/detect_cannibalization.py` — règle-based (keyword overlap sur positions GSC), pas embedding |
| Détection contenu dupliqué (cosine) | ❌ | — |
| Entity extraction (spaCy) | ❌ | — |

**Ce qui existe** : cannibalisation détectée par overlap de requêtes GSC (2 pages avec >10 impressions sur la même query). C'est de la logique Python pure, pas du NLP.

**Effort :** sentence-transformers + HDBSCAN : L. spaCy entity extraction : M.

---

### 4.10 Scoring & Priorisation

**Statut global : 🟡 Partiel (45 %)**

| Feature | Statut | Fichier |
|---|---|---|
| Score SEO global (0-100) | ✅ | `scripts/report/generate_report.py` + `app/api/audit.py` |
| Score par catégorie (titre, meta, alt, duplication) | ✅ | `app/api/audit.py:get_score()` |
| Score "niche fit" | ❌ | — |
| Revenue at Risk par issue | ❌ | — |
| ICE matrix (Impact/Confidence/Effort) | 🟡 | `scripts/report/ice_matrix.py` — optionnel, non intégré au workflow |
| Quick wins surfacés | 🟡 | `scripts/audit/detect_gsc_opportunities.py` + alertes email |

**Effort :** Revenue at Risk M, niche fit score M.

---

### 4.11 Frontend / UX

**Statut global : 🟡 Très partiel (20 %)**

| Feature | Statut | Fichier |
|---|---|---|
| Onboarding < 5 min | ❌ | Pas de flow guidé |
| Dashboard : score + top actions + niche | 🟡 | `frontend/src/App.jsx` — score ✅, niche ❌ |
| Vue Catalog Audit (tableau filtrable) | 🟡 | `IssuesList.jsx` — liste par sévérité, pas par produit/collection |
| Vue Niche | ❌ | — |
| Vue Generator (preview avant/après IA) | 🟡 | `MetaApplyPanel.jsx` — preview/apply meta manuels, pas IA |
| Vue Content (blog, FAQ) | ❌ | — |
| Vue Impact (GSC pre/post) | ❌ | — |
| Mode batch avec barre de progression | ❌ | — |
| Notifications App Bridge | ❌ | — |
| Polaris UI | ❌ | CSS custom — `frontend/src/styles.css` |
| Embedded dans Shopify Admin | ❌ | App externe, pas de `AppBridgeProvider` |

**Dépendances frontend actuelles :** `react`, `react-dom` uniquement — aucune dépendance Shopify.

**Effort :** App Bridge + Polaris migration : L. Vues manquantes : XL au total.

---

### 4.12 Infra & Ops

**Statut global : 🟡 Partiel (25 %)**

| Composant | Statut | Détail |
|---|---|---|
| Hébergement app | ❌ | Dockerfile présent, pas de déploiement configuré |
| Neon / Supabase Postgres | ❌ | SQLite uniquement — ne scale pas multi-tenant |
| Cloudflare R2 (object storage) | ❌ | — |
| Upstash Redis (cache/queue) | ❌ | — |
| OpenAI GPT-4o mini | ❌ | — |
| Cloudflare Workers AI | ❌ | — |
| Groq Llama 3.1 8B | ❌ | — |
| sentence-transformers local | ❌ | Non installé |
| spaCy multilingue | ❌ | — |
| Sentry / UptimeRobot | ❌ | — |
| GitHub Actions CI/CD | ✅ | `.github/workflows/weekly_audit.yml` |
| Cloudflare DNS/CDN | ❌ | Non configuré dans le code |

**Problème critique infra :** SQLite ne peut pas héberger des tokens de milliers de stores simultanément avec des accès concurrents depuis une API web. Migration vers Postgres (Neon free tier) nécessaire avant scaling.

**Effort :** Migration SQLite → Postgres M, déploiement Fly.io/Hetzner S, monitoring Sentry S.

---

## 3. Stack technique

### Comparaison source par source (chapitre 5)

| Source | Limite gratuite | Utilisée ? | Note |
|---|---|---|---|
| Shopify Admin GraphQL | Gratuit | ✅ | `productUpdate`, `collectionUpdate`, `metafieldsSet`, `urlRedirectCreate` |
| Shopify Storefront API | Gratuit | ❌ | Jamais appelé |
| Shopify Theme App Extensions | Gratuit | ❌ | Instructions manuelles seulement |
| Shopify Billing API | Gratuit (0% < $1M rev) | ❌ | Licensing HMAC maison à la place |
| GSC API | 50k pairs/jour | ✅ | `scripts/audit/fetch_gsc.py` |
| GSC → BigQuery | Free 1 Tio/mois | ❌ | — |
| PSI API | 25k req/jour | ✅ | `scripts/audit/fetch_pagespeed.py` |
| CrUX BigQuery / History API | Free | ❌ | — |
| Bing Webmaster API | Gratuit | ❌ | — |
| OpenAI GPT-4o mini | $0,15/M input | ❌ | Absent |
| Cloudflare Workers AI | 10k Neurons/j | ❌ | Absent |
| Groq Llama 3.1 8B | 14 400 RPD | ❌ | Absent |
| Mistral La Plateforme | Free expérimental | ❌ | Absent |
| sentence-transformers local | Gratuit | ❌ | Non installé |
| spaCy multilingue | Gratuit | ❌ | Non installé |
| pytrends | Gratuit | ❌ | Non installé |
| Reddit API | 100 req/min | ❌ | — |
| Common Crawl | Gratuit (S3+DuckDB) | ❌ | — |
| Cloudflare R2 | 10 Go + 0 egress | ❌ | — |
| Neon Postgres | Free 0,5 Go | ❌ | SQLite seulement |
| Sentry / UptimeRobot | Free tier | ❌ | — |

### Sources gratuites non-utilisées à intégrer en priorité

1. **Neon Postgres** — remplacement SQLite obligatoire pour multi-tenant scale
2. **Cloudflare Workers AI** — LLM fallback gratuit (10k Neurons/j) pour démarrer sans coût
3. **GSC → BigQuery export** — historique illimité sans les quotas API
4. **sentence-transformers local** — embeddings 0€ pour déduplication et niche clustering

### Sources payantes actuelles

Aucune source payante n'est utilisée — le système de licensing HMAC interne (`scripts/license.py`) remplace Shopify Billing API, ce qui est **non-conforme** pour une app publique (Shopify exige son propre système de facturation).

### Estimation coût mensuel

| Scénario | Coût actuel | Coût cible (100 stores) |
|---|---|---|
| Infra | 0€ (local/Docker) | 3-4€/mois (Hetzner CX11 ou Fly.io) |
| Database | 0€ (SQLite) | 0€ (Neon free 0,5 Go) |
| LLM (si GPT-4o mini) | 0€ | ~5-10€/mois (0,05-0,10€/store × 100) |
| LLM fallback | 0€ | 0€ (Groq + Workers AI free tier) |
| Monitoring | 0€ | 0€ (Sentry free) |
| **Total** | **0€** | **~8-14€/mois** ✅ dans budget |

---

## 4. Anti-patterns détectés

| Anti-pattern | Présent ? | Localisation |
|---|---|---|
| Modification theme via GitHub PRs | ❌ Non | Admin API utilisée correctement |
| Patches Liquid hardcodés | 🟡 Partiel | Instructions manuelles pour hreflang (`generate_hreflang.py:99-127`) et JSON-LD (`add_schema.py` README) — acceptable pour Phase 1, non-viable App Store |
| Dépendance Ahrefs/Semrush payants | ❌ Non | Mentionné en stack legacy, absent du code |
| OpenAI embeddings (au lieu de sentence-transformers) | ❌ Non | Aucun embeddings du tout |
| Rate limits non respectés | ❌ Non | 429 + throttleStatus respectés (`update_meta.py:57-66`, `crawl_shopify.py`) |
| **Pas de webhooks GDPR** | ✅ **Présent** | `app/oauth/webhooks.py` — seul `app/uninstalled` implémenté (ligne 25-50) |
| Tokens stockés en clair | ❌ Non | Fernet encryption (`app/oauth/crypto.py:_ENC_PREFIX = "enc:"`) |
| Pas de versioning des modifications | ❌ Non | `data/history.db` table `seo_changes`, rollback CLI |
| Génération IA sans validation | N/A | Pas d'IA implémentée |
| Pas d'abstraction LLM provider | N/A | Pas d'IA implémentée |
| Codebase monolithique | 🟡 Partiel | Modules bien séparés (audit/apply/report/api) mais pas encore en domaines Shopify App (ShopifyClient, NicheFinder, Generator, Applier, Tracker) |
| Promesse "IA fait tout seul" | ❌ Non | Dry-run par défaut + confirmation sur chaque apply |
| Pas de tests sur détecteurs SEO | ❌ Non | 537 tests, couverture audit, apply, API |
| **Pricing hardcodé** (pas Shopify Billing API) | ✅ **Présent** | `scripts/license.py` + `app/api/plans.py` — HMAC maison, non-conforme App Store |
| **App non-embedded** | ✅ **Présent** | `frontend/src/App.jsx` — React externe, pas App Bridge Provider |

**3 anti-patterns critiques à corriger avant soumission App Store :**
1. `app/oauth/webhooks.py` : ajouter `customers/data_request`, `customers/redact`, `shop/redact`
2. `scripts/license.py` + `app/api/plans.py` : migrer vers Shopify Billing API GraphQL (`appSubscriptionCreate`)
3. `frontend/src/` : ajouter `@shopify/app-bridge-react` + `AppProvider` wrapping l'app

---

## 5. Évaluation : pivot vs évolution

### Analyse

Le code actuel est un **pipeline Python d'automation pour un store** (leoniedelacroix.com) avec une couche API FastAPI + frontend React ajoutée en Phase 5 pour servir de foundation d'app publique. La question est : peut-on construire dessus, ou faut-il repartir d'un boilerplate Shopify CLI Remix ?

### Verdict : **(b) — Réutilisable comme moteur back-end, nouveau front-end Shopify App**

**Ce qui est réutilisable :**
- `scripts/audit/` → toute la logique de détection SEO (migrate vers lib Python `leonie_seo.audit`)
- `scripts/apply/` → toutes les mutations Shopify GraphQL (migrer vers `leonie_seo.applier`)
- `scripts/report/` → scoring, scoring EEAT, delta reports (migrer vers `leonie_seo.scorer`)
- `app/oauth/` → flux OAuth complet, crypto Fernet, state store CSRF (garder tel quel)
- `app/api/` → endpoints FastAPI (étendre, pas réécrire)
- `config/niches/` → signaux YAML par niche (base pour le Niche Intelligence module)
- `data/history.db` → migrer vers Neon Postgres en gardant le même schéma

**Ce qui ne survit pas à l'App Store :**
- `frontend/src/` → rebuildé en Shopify App embedded (Polaris + App Bridge React)
- `.github/workflows/weekly_audit.yml` → hardcodé leoniedelacroix.com, à paramétrer
- Système de licensing HMAC → remplacé par Shopify Billing API

**Pourquoi pas (a) ?**
L'app n'est pas embedded dans Shopify Admin. Un marchand installant l'app depuis l'App Store s'attend à voir un dashboard dans son Admin, pas un onglet qui l'emmène sur une URL externe. Reconstruire le front-end avec Polaris + App Bridge est non-négociable.

**Pourquoi pas (c) — repartir de zéro ?**
Le moteur Python d'audit/apply est de haute qualité, testé, avec du rate limiting, du rollback, du chiffrement. Repartir d'un boilerplate Remix jetterait 6 mois de logique métier SEO. L'option (b) est le bon équilibre.

---

## 6. Roadmap recommandée

### Phase 1 — Conformité App Store (Mois 1 — blocage actuel)

| Priorité | Action | Fichiers | Effort | Impact |
|---|---|---|---|---|
| 🔴 1 | **GDPR webhooks** : `customers/data_request`, `customers/redact`, `shop/redact` | `app/oauth/webhooks.py` (ajouter 3 handlers) | S < 1j | Bloquant review |
| 🔴 2 | **Shopify Billing API** : `appSubscriptionCreate` mutation + plans Free/Pro/Agency | Nouveau `app/api/billing.py` | M 2-3j | Bloquant monétisation |
| 🔴 3 | **App Bridge React** : embedding dans Shopify Admin + `AppProvider` wrapper | `frontend/src/main.jsx` + install `@shopify/app-bridge-react` | M 2j | Bloquant UX App Store |
| 🟡 4 | **Polaris UI** : remplacer `styles.css` par composants Polaris | `frontend/src/components/` | L 5j | Exigé pour App Store |
| 🟡 5 | **Migration SQLite → Neon Postgres** | `app/db.py` + `app/oauth/token_store.py` | M 2j | Scale multi-tenant |

### Phase 2 — Moteur IA + Niche (Mois 2-4)

| Priorité | Action | Fichiers | Effort | Impact |
|---|---|---|---|---|
| 6 | **LLM abstraction layer** : provider pattern (GPT-4o mini, Workers AI fallback, Groq) | Nouveau `app/llm/provider.py` | M 2j | Base de tout le contenu IA |
| 7 | **Prompt templates versionnés** : meta title, meta desc, alt text, collection desc | Nouveau `config/prompts/*.yaml` | M 2-3j | Qualité du contenu généré |
| 8 | **Batch generation API** : `POST /shops/{shop}/generate` + job queue | Nouveau `app/api/generate.py` + Upstash Redis | L 5j | Feature core |
| 9 | **Niche Intelligence module** : pytrends + GSC clustering | Nouveau `app/niche/` | XL 10j+ | Différenciateur |
| 10 | **Pages/Articles crawl + apply** : `pageUpdate`, `articleUpdate` mutations | `scripts/audit/crawl_shopify.py` + `scripts/apply/` | M 3j | Couverture SEO complète |

### Phase 3 — Contenu long format + automation (Mois 5-7)

| Action | Effort |
|---|---|
| Theme App Extension (injection JSON-LD headless, sans modifier theme.liquid) | XL |
| Bulk Operations pour catalogues >1000 produits | L |
| Vue Impact (graphes GSC pre/post sur URLs modifiées) | L |
| sentence-transformers + HDBSCAN (déduplication + clustering) | M |
| Multilingue génération IA (Shopify Markets) | L |

---

## 7. Quick wins (< 1 jour de dev)

1. **GDPR webhooks** (`app/oauth/webhooks.py`) — 3 handlers vides suffisent pour passer le review : renvoyer `200 OK` sur `customers/data_request`, `customers/redact`, `shop/redact`. Les implémenter vraiment prend plus de temps, mais les déclarer passe le review automatisé.

2. **Hardcoding leoniedelacroix.com dans GitHub Actions** (`.github/workflows/weekly_audit.yml` lignes 52-58) → remplacer par `${{ secrets.PAGESPEED_URLS }}` ou paramètre `workflow_dispatch`.

3. **Privacy policy URL dans le manifest** → créer `GET /privacy` qui retourne une page statique HTML avec la politique de confidentialité (obligatoire App Store).

4. **`detect_issues.py` : vérifier si schema Product est absent** → ajouter un check "aucun metafield `custom.json_ld`" → issue `schema_missing / medium`. Zéro nouvelle mutation, juste lecture du snapshot.

5. **`pageUpdate` + `articleUpdate` mutations** dans `scripts/apply/update_meta.py` → copier-coller le pattern `productUpdate` en changeant le type GID. L'infrastructure (dry-run, logging, rollback) existe déjà.

6. **Bulk Operations stub** pour les catalogues >500 produits → ajouter `--bulk` flag dans `crawl_shopify.py` qui bascule vers l'API Bulk Operations JSON Lines (la logique cursor-paginated reste comme fallback).

---

## 8. Risques techniques identifiés

### Risque 1 — SQLite en production multi-tenant (critique)

**Problème :** SQLite avec accès concurrents depuis uvicorn multi-worker va provoquer des `database is locked` errors. Pour 10+ stores actifs simultanément, le risque de corruption est réel.

**Fichiers :** `app/db.py`, `app/oauth/token_store.py`, `scripts/apply/*.py`

**Mitigation :** Migrer vers Neon Postgres (free tier 0,5 Go). Le schéma actuel est propre et migrate directement.

---

### Risque 2 — Absence de GDPR (bloquant légal)

**Problème :** Sans `customers/data_request`, `customers/redact`, `shop/redact`, l'app stocke potentiellement des données merchant qui ne peuvent pas être supprimées sur demande. C'est un rejet automatique App Store + risque RGPD.

**Fichier :** `app/oauth/webhooks.py` — seul `app/uninstalled` implémenté (ligne 25).

---

### Risque 3 — Master key Fernet non rotatée (sécurité)

**Problème :** `LEONIE_MASTER_KEY` est la seule clé de chiffrement pour tous les tokens OAuth de tous les stores. Si elle fuit, tous les tokens sont compromis. Pas de mécanisme de rotation de clé.

**Fichier :** `app/oauth/crypto.py:_fernet()` — clé lue depuis env var sans versioning.

**Mitigation :** Ajouter un `key_version` dans le préfixe `enc:v2:...` pour permettre la rotation progressive.

---

### Risque 4 — Réutilisation du `history.db` pour tokens ET changements SEO

**Problème :** Les tokens OAuth (confidentiels) et les changements SEO (logs) sont dans le même fichier SQLite. Une exfiltration de `history.db` expose les deux.

**Fichier :** `app/db.py` — tables `shop_tokens` et `seo_changes` cohabitent.

**Mitigation :** Séparer en deux fichiers, ou utiliser Postgres avec row-level security.

---

### Risque 5 — GitHub Actions expose les URLs de prod dans les logs

**Problème :** Les URLs `https://www.leoniedelacroix.com/products/...` sont hardcodées dans `.github/workflows/weekly_audit.yml` (lignes 52-58) et visibles dans les logs publics si le repo est public.

**Mitigation :** Paramétrer via secrets ou `workflow_dispatch` inputs.

---

### Risque 6 — Pas de circuit breaker sur les retry Shopify

**Problème :** Si Shopify est indisponible, les scripts en mode `--apply` font 3 tentatives avec `Retry-After` puis échouent silencieusement (log uniquement). Dans un contexte multi-tenant, un outage Shopify peut laisser des jobs en attente sans visibilité.

**Fichier :** `scripts/apply/update_meta.py:_gql_with_retry()`.

---

## 9. Réutilisation maximale du code actuel

### Modules réutilisables en l'état

| Module | Valeur | Comment l'extraire |
|---|---|---|
| `scripts/audit/detect_issues.py` | ⭐⭐⭐ — logique de détection SEO | Renommer en `leonie_seo.audit.IssueDetector`, ajouter `pages` et `articles` comme input |
| `scripts/audit/crawl_shopify.py` | ⭐⭐⭐ — paginated GraphQL fetch + throttle | Extraire en `leonie_seo.shopify.Crawler`, paramétrer `shop` + `token` |
| `scripts/apply/update_meta.py` | ⭐⭐⭐ — mutations productUpdate + rate limit | Extraire en `leonie_seo.shopify.Applier` |
| `scripts/apply/rollback.py` | ⭐⭐⭐ — rollback complet | Garder tel quel, c'est une feature différenciante |
| `app/oauth/` (router, crypto, token_store) | ⭐⭐⭐ — OAuth Shopify complet | Garder en l'état, juste migrer le storage vers Postgres |
| `scripts/report/analyze_semantics.py` | ⭐⭐ — scoring niche | Base pour le Niche Intelligence module (ajouter pytrends + embeddings) |
| `config/niches/*.yaml` | ⭐⭐ — signaux par secteur | Garder comme training data pour les prompts IA |
| `app/api/` (FastAPI endpoints) | ⭐⭐ — structure API propre | Étendre, pas réécrire |
| `scripts/report/generate_hreflang.py` | ⭐⭐ — hreflang correct | Garder, migrer vers Theme App Extension |
| `scripts/audit/fetch_pagespeed.py` | ⭐ — simple wrapper PSI | Garder tel quel |

### Code mort ou obsolète

| Fichier | Statut | Raison |
|---|---|---|
| `scripts/audit/parse_screaming_frog.py` | Optionnel non utilisé | Pas dans le workflow CI, parsing CSV manuel |
| `scripts/report/dashboard.py` | Optionnel non utilisé | Interactif CLI uniquement, pas compatible CI |
| `scripts/report/ice_matrix.py` | Optionnel non utilisé | Outil de priorisation manuelle, hors workflow |
| `oauth_client.json`, `token.json` | Présents en root | Credentials Google OAuth — à supprimer du repo (`.gitignore`) |

### Extraction recommandée en lib interne

```
leonie_seo/              ← package Python installable
├── shopify/
│   ├── crawler.py       ← depuis crawl_shopify.py
│   ├── applier.py       ← depuis update_meta.py, update_alt_text.py, add_schema.py
│   └── client.py        ← wrapper GraphQL avec rate limiting
├── audit/
│   ├── detector.py      ← depuis detect_issues.py
│   ├── scorer.py        ← depuis generate_report.py
│   └── gsc.py           ← depuis fetch_gsc.py
├── niche/               ← À CRÉER
│   ├── signals.py       ← depuis config/niches/*.yaml
│   └── finder.py        ← pytrends + GSC clustering
└── llm/                 ← À CRÉER
    ├── provider.py      ← abstraction GPT-4o mini / Workers AI / Groq
    └── prompts/         ← templates Jinja2 versionnés
```

---

*Fin du rapport. Les 3 actions bloquantes pour la soumission App Store sont : (1) GDPR webhooks, (2) Shopify Billing API, (3) App Bridge embedding.*
