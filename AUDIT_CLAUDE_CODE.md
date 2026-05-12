# ARCHIVE — AUDIT PROJET HISTORIQUE

> Document historique créé pour Claude Code. Il est conservé pour traçabilité et ne doit plus être utilisé comme consigne active Codex.
> État courant et règles actives : `AGENTS.md`, `ROADMAP.md`, `PROGRESS.md`.

# AUDIT PROJET — Shopify App SEO IA niche-driven

> **Pour Codex** : traiter ce fichier comme une archive d'audit. Ne pas relancer ce workflow tel quel sans le réadapter à l'état courant du repo.

---

## 1. Contexte du projet actuel

- **Nom du dépôt** : projet SEO automation pour leoniedelacroix.com (Shopify, marché FR pet products), prototype perso destiné à devenir un produit
- **État actuel connu** : pipeline Python avec GitHub Actions, utilise Google Search Console, PageSpeed Insights, Shopify API, Ahrefs Free
- **Objectif initial** : faire passer leoniedelacroix.com de quasi-zéro à un trafic organique significatif, avec uniquement des outils gratuits
- **Objectif élargi (final)** : transformer ce projet en **Shopify App publique** distribuée sur le Shopify App Store, ciblant les PME e-commerce françaises et internationales

---

## 2. Vision cible — produit final

Le produit est une **Shopify App native** qui :

1. **S'installe** depuis le Shopify App Store en 1 clic (OAuth Shopify standard, pas de GitHub, pas d'accès au theme repo)
2. **Accède à l'ensemble du store** via les APIs Shopify (Admin GraphQL, Storefront, Files, Metafields, Theme App Extensions)
3. **Aide le marchand à identifier une niche rentable** dans son catalogue (analyse produits + keywords + concurrence)
4. **Utilise une API IA** (GPT-4o mini privilégié pour ratio qualité/coût, fallback Cloudflare Workers AI / Groq) pour **générer le contenu SEO optimisé** :
   - Meta titles + meta descriptions (products, collections, pages, articles)
   - Descriptions produits enrichies et différenciantes
   - Alt text d'images en masse
   - JSON-LD / structured data (Product, Offer, FAQ, Article, BreadcrumbList) via metafields
   - Articles de blog longue-traîne ciblant la niche
   - Pages FAQ
   - Texte SEO sur pages collections (intro/outro)
   - Suggestions d'URL handles propres
5. **Applique les modifications** directement sur le store via Admin API (avec validation user à chaque étape ou en mode auto-approve)
6. **Mesure l'impact** en branchant Search Console + GA4 (si dispo) sur les URLs modifiées

**One-liner** : *"L'IA SEO qui choisit ta niche rentable, écrit ton contenu, et l'applique automatiquement à ton Shopify. En 1 install."*

**Distribution** : Shopify App Store, listing FR + EN, modèle freemium classique Shopify.

**Concurrents directs** (à étudier, pas à copier) : Smart SEO (Sherpas), AVADA SEO Suite, TinyIMG SEO, Booster SEO, Plug In SEO, JSON-LD for SEO. **Différenciateur visé** : niche-first + génération IA contextuelle vs leurs templates génériques.

**Contraintes opérationnelles** :
- Budget infra ≤ 12€/mois jusqu'à 100 stores actifs, ≤ 50€/mois jusqu'à 500 stores
- Coût IA marginal cible < 0,10€ par store/mois (ou refacturé via plans payants)
- Conformité Shopify App Store (passer le review, GDPR, billing via Shopify)

---

## 3. Roadmap cible en 3 phases

### Phase 1 — App scaffolding + audit SEO (mois 1-3)
Shopify App boilerplate (Remix ou Node), OAuth Shopify, accès Admin API, audit du store (produits, collections, pages, articles, sitemap, GSC connecté optionnellement), détection problèmes SEO de base, dashboard.

### Phase 2 — Niche selection + génération IA (mois 4-6)
Module d'analyse de niche, sélection assistée, génération IA en masse de meta tags / alt text / descriptions, application via Admin API, validation user.

### Phase 3 — Contenu long format + automation (mois 7-9)
Articles de blog, pages FAQ, structured data avancé via metafields, Theme App Extension pour injecter du JSON-LD sans toucher au theme, programmation d'optimisation continue.

---

## 4. Modules cible — checklist détaillée

Pour chaque module ci-dessous, vérifie dans le code actuel :
- ❌ Absent
- 🟡 Partiel (préciser ce qui manque)
- ✅ Présent (préciser fichiers concernés)

### 4.1 Shopify App scaffolding (Phase 1, critique)
- [ ] Boilerplate Shopify App (Shopify CLI, template Remix Node ou Next.js)
- [ ] OAuth Shopify (managed install ou custom flow)
- [ ] Webhooks essentiels : `app/uninstalled`, `shop/update`, `products/update`, `customers/data_request` (GDPR), `customers/redact`, `shop/redact`
- [ ] Session storage (Postgres/Redis)
- [ ] Shopify Billing API (RecurringApplicationCharge ou App Subscriptions GraphQL)
- [ ] Embedded app dans Shopify Admin (App Bridge React)
- [ ] Polaris UI (composants natifs Shopify Admin)
- [ ] Conformité App Store : privacy policy, GDPR endpoints, performance budget Web Vitals app embed, listing assets

### 4.2 Connecteurs externes (Phase 1)
- [ ] OAuth Google Search Console (optionnel mais critique pour mesurer impact)
- [ ] OAuth Google Analytics 4 (optionnel, pour Revenue Attribution)
- [ ] PageSpeed Insights API (gratuit, 25k/jour) — audit CWV
- [ ] CrUX BigQuery / CrUX History API (LCP/CLS/INP réels)
- [ ] Bing Webmaster Tools API (optionnel, backlinks competitor)

### 4.3 Lecture du store (Phase 1)
- [ ] Pull complet via Admin GraphQL : products, variants, collections, pages, blogs, articles
- [ ] Pull metafields (existants pour ne pas écraser)
- [ ] Pull theme settings actuels (lecture seule, JSON)
- [ ] Pull files API (images avec URLs, sizes, alt text actuels)
- [ ] Pull URL redirects existants
- [ ] Pull robots.txt.liquid actuel (lecture)
- [ ] Pull shop locales (multi-langue Shopify Markets)
- [ ] Bulk operations Admin API pour gros catalogues (>1000 produits)
- [ ] Respect des rate limits Shopify (1000 points/min standard, 2000 Plus)

### 4.4 Audit SEO (Phase 1)
Détection des problèmes (au niveau produit/collection/page/article) :
- [ ] Meta title manquant ou > 60 chars ou < 30 chars
- [ ] Meta description manquante ou hors plage 120-160 chars
- [ ] Meta title/description dupliqués entre URLs
- [ ] URL handle non-optimisé (trop long, contient stopwords FR/EN)
- [ ] Description produit trop courte (< 200 mots) ou dupliquée
- [ ] Alt text image manquant ou générique ("image1.jpg")
- [ ] Schema Product manquant (vérifier via metafields ou theme)
- [ ] Schema BreadcrumbList manquant
- [ ] Schema Organization manquant
- [ ] Schema FAQ manquant sur collections/pages adaptées
- [ ] Pas de blog actif (opportunité contenu)
- [ ] Articles de blog dépourvus de meta + JSON-LD Article
- [ ] Collection sans description (vide en haut/bas)
- [ ] Pages sans contenu (about, contact souvent vides)
- [ ] Hreflang manquants pour stores Shopify Markets multi-langues
- [ ] Redirects manquants pour produits dépublié (404 → 301)
- [ ] CWV LCP/INP/CLS hors seuil (CrUX p75)

### 4.5 Niche Intelligence (Phase 2 — différenciateur)
- [ ] Module "Niche Finder" : analyse du catalogue actuel + tendances marché pour suggérer une niche
- [ ] Sources data niche :
  - [ ] Google Trends (pytrends, gratuit) : courbes de tendance par keyword candidat
  - [ ] Google Suggest / People Also Ask scraping (gratuit, throttlé)
  - [ ] Reddit API (gratuit, intent transactionnel via subreddits)
  - [ ] GSC queries du store (gratuit, via OAuth)
  - [ ] Common Crawl Web Graph (gratuit) pour estimer concurrence backlinks
  - [ ] Optionnel : DataForSEO Standard Queue (pay-per-use) pour SERP volumes — uniquement si budget le permet
- [ ] Scoring de niche : `volume × intent_commercial × (1 - difficulté) × (1 - saturation_SERP)`
- [ ] Détection des "niches déjà servies" par les produits actuels vs "niches gap"
- [ ] Recommandation top 3-5 niches avec justification
- [ ] Persistance du choix de niche (metafield app `app_namespace.niche.target`)

### 4.6 Génération IA de contenu SEO (Phase 2 — cœur produit)
- [ ] Provider LLM principal : OpenAI GPT-4o mini (recommandé : ratio qualité/coût imbattable, $0,15/M input, $0,60/M output)
- [ ] Fallback gratuit : Cloudflare Workers AI Llama 3.1 8B (10k Neurons/jour) ou Groq Llama 3.1 8B (14 400 RPD)
- [ ] Optionnel : Mistral La Plateforme (souverain UE, RGPD-friendly)
- [ ] Module de prompt templates versionnés (Jinja2 ou similaire) pour :
  - [ ] Meta title produit (avec niche + product name + USP)
  - [ ] Meta description produit (avec CTA + USP + niche keyword)
  - [ ] Description produit enrichie (300-500 mots, structure introduction + bénéfices + spec + cas d'usage)
  - [ ] Alt text image produit
  - [ ] Description collection (intro 100 mots + outro 200 mots avec keywords longue-traîne)
  - [ ] Article de blog complet (1500-3000 mots, structure H2/H3, FAQ intégrée)
  - [ ] FAQ d'une page (5-10 paires Q/A basées sur PAA Google)
  - [ ] JSON-LD Product, FAQPage, Article, BreadcrumbList
- [ ] Validation pré-application :
  - [ ] Anti-hallucination : règles strictes "n'invente pas de specs produit, base-toi uniquement sur la description fournie"
  - [ ] Length check (titles 50-60c, meta 140-155c)
  - [ ] Schema validator (Schema.org Validator + Google Rich Results Test API)
  - [ ] Detection contenu dupliqué entre URLs (cosine similarity embeddings)
- [ ] Mode batch (générer pour 50/100/tout le catalogue d'un coup)
- [ ] Mode review (l'utilisateur valide chaque suggestion ou bulk-approve par catégorie)
- [ ] Mode auto-approve (sur opt-in, pour mass updates)
- [ ] Multilingue : génération adaptée locale (FR, EN, DE, ES, IT) si le store est sur Shopify Markets
- [ ] Tracking des coûts IA par store (pour pricing & monitoring)

### 4.7 Application des modifications via Admin API (Phase 2)
- [ ] `productUpdate` GraphQL : title, descriptionHtml, handle, seo (title, description), tags
- [ ] `collectionUpdate` : title, descriptionHtml, handle, seo
- [ ] `pageUpdate` (Online Store API) : title, body, handle, seo
- [ ] `articleUpdate` : title, content, handle, seo
- [ ] `productImageUpdate` ou Files API : altText
- [ ] Metafields create/update pour structured data custom :
  - [ ] Namespace `seo_app` ou unique au app
  - [ ] Type `json` pour JSON-LD (Product, FAQPage, Article)
- [ ] URL redirects create (`urlRedirectCreate`) pour gérer changements de handle
- [ ] Versioning des modifications (avant/après stockés en DB pour rollback)
- [ ] Bouton "Rollback" par modification ou par batch
- [ ] Mode preview (URL preview Shopify avec `_tk` token)

### 4.8 Theme App Extension (Phase 3 — injection JSON-LD propre)
- [ ] Theme App Extension Block : `app-embed` qui injecte JSON-LD dans `<head>` ou `<body>` sans modifier le theme
- [ ] Templates Liquid de l'extension lisant les metafields générés par l'app
- [ ] Compatibilité Online Store 2.0 themes (Dawn, Sense, Refresh, Studio, Origin, Crave, Empire, Impulse)
- [ ] Fallback pour anciens themes (instructions manuelles à l'utilisateur)

### 4.9 Module NLP / sémantique (transversal)
- [ ] Embeddings local sentence-transformers `multilingual-e5-base` (recommandé FR) — 0€
- [ ] HDBSCAN clustering des produits par thématique (utile pour niche finder + détection cannibalisation)
- [ ] Détection cannibalisation : 2+ produits/collections ciblant les mêmes keywords
- [ ] Détection contenu dupliqué (texte produit copié-collé d'un fournisseur)
- [ ] Entity extraction (spaCy `fr_core_news_lg` + `en_core_web_lg`) pour identifier brand/material/color/use-case dans titles & descriptions

### 4.10 Scoring & priorisation
- [ ] Score SEO global du store (0-100)
- [ ] Score par catégorie (technique, contenu, structured data, niche fit)
- [ ] **Revenue at Risk** par issue : `n_URLs × revenue_organique_moyen × impact_coef`
- [ ] Priorisation des actions par (impact × facilité)
- [ ] Quick Wins surfacés en haut du dashboard

### 4.11 Frontend / UX (Polaris)
- [ ] Onboarding < 5 min : install → connect GSC (skip possible) → premier audit
- [ ] Dashboard principal : score SEO, top 5 actions priorisées, niche actuelle
- [ ] Vue "Catalog Audit" : tableau filtrable produits/collections avec issues
- [ ] Vue "Niche" : niche choisie, opportunités, gap analysis
- [ ] Vue "Generator" : sélection items + bouton "Générer" + preview avant/après
- [ ] Vue "Content" : articles de blog générés, FAQ, planning
- [ ] Vue "Impact" : graphes GSC pre/post (CTR, position, impressions, clicks) sur URLs modifiées
- [ ] Mode batch avec barre de progression (Web Workers ou Polling sur jobs)
- [ ] Notifications via Shopify App Bridge

### 4.12 Infra & ops (budget ≤ 12€/mois jusqu'à 100 stores)
- [ ] Hébergement app : **Cloudflare Workers + Hono** OU **Fly.io** OU **Hetzner CX11** (3,29€) OU **Vercel Hobby** (gratuit)
- [ ] Database : **Neon** (Postgres serverless, scale-to-zero, free 0,5 Go/projet) OU **Supabase free** (500 Mo, pause après 7j inactif)
- [ ] Object storage : **Cloudflare R2** (10 Go gratuits, egress 0)
- [ ] Cache + Queue : **Upstash Redis free** (10k cmd/jour, 256 Mo)
- [ ] LLM principal : **OpenAI GPT-4o mini** (pay-per-use, ~0,01-0,05€/store/mois pour optim complète)
- [ ] LLM fallback gratuit : **Cloudflare Workers AI** (10k Neurons/jour) + **Groq Llama 3.1 8B** (14 400 RPD)
- [ ] Embeddings : **sentence-transformers** local (gratuit) — pas d'OpenAI embeddings
- [ ] Monitoring : **Sentry free** + **UptimeRobot free** + **Plausible self-hosted**
- [ ] CI/CD : **GitHub Actions** (2000 min/mois free)
- [ ] DNS + CDN : **Cloudflare** (gratuit)

---

## 5. Stack technique gratuit ou pay-per-use — comparaison

Vérifie si le projet utilise ces sources :

| Source | Limite gratuite / coût | Utilisée ? |
|---|---|---|
| Shopify Admin GraphQL | Gratuit (custom app) | ? |
| Shopify Storefront API | Gratuit (tokenless 1000 complexity max) | ? |
| Shopify Theme App Extensions | Gratuit | ? |
| Shopify Billing API | Gratuit (Shopify prend 20% commission Shopify Plus, 0% sur revenu < $1M) | ? |
| GSC API | 50k pairs/jour/property | ? |
| GSC → BigQuery export | Sans limite (BQ free 1 Tio queries/mois) | ? |
| PSI API | 25k req/jour | ? |
| CrUX BigQuery / History API | Free tier BQ | ? |
| OpenAI GPT-4o mini | $0,15/M input, $0,60/M output | ? |
| Cloudflare Workers AI | 10k Neurons/jour gratuit | ? |
| Groq Llama 3.1 8B | 14 400 RPD gratuit | ? |
| Mistral La Plateforme | Free tier expérimental | ? |
| sentence-transformers local | Gratuit | ? |
| spaCy multilingue | Gratuit | ? |
| pytrends (Google Trends) | Gratuit (rate-limited) | ? |
| Reddit API | 100 req/min gratuit | ? |
| Common Crawl Web Graph | Gratuit (S3 + DuckDB local) | ? |
| Bing Webmaster API | Gratuit | ? |
| Cloudflare R2 | 10 Go + egress 0 | ? |
| Neon Postgres | Free 0,5 Go/projet, scale-to-zero | ? |
| Sentry / UptimeRobot | Free tier | ? |

---

## 6. Anti-patterns à flagger si trouvés dans le code actuel

- [ ] **Modification du theme via GitHub PRs** — vision abandonnée, on passe par Admin API + Theme App Extensions
- [ ] **Patches Liquid hardcodés** — l'app n'a pas accès au theme repo
- [ ] **Dépendance à Ahrefs/Semrush API payantes** — remplaçable par GSC + Common Crawl + scraping léger
- [ ] **OpenAI embeddings utilisés** — sentence-transformers local fait le job pour 0€
- [ ] **Pas de respect rate limits Shopify** (risque ban app)
- [ ] **Pas de webhooks GDPR** (rejet automatique au App Store review)
- [ ] **Tokens stockés en clair** au lieu de chiffrés en DB
- [ ] **Pas de versioning des modifications** (rollback impossible = churn massif)
- [ ] **Génération IA sans validation** (length, schema, hallucination → faux SEO)
- [ ] **Pas d'abstraction sur le LLM provider** (rend impossible le switch GPT → Workers AI quand quota explose)
- [ ] **Codebase monolithique** au lieu de modules : `shopify_client`, `audit`, `niche_finder`, `generator`, `applier`, `tracker`
- [ ] **Promesse "AI fait tout tout seul"** — UX devrait toujours laisser l'utilisateur valider
- [ ] **Pas de tests** sur les détecteurs SEO (false positives) ni sur les prompts IA (regressions)
- [ ] **Pricing hardcodé en code** au lieu d'utiliser Shopify Billing API
- [ ] **App non-embedded** (mauvais UX dans Shopify Admin)

---

## 7. Format de sortie attendu

Génère un fichier `RAPPORT_AUDIT.md` à la racine du projet avec la structure suivante :

```
# RAPPORT D'AUDIT — État actuel vs vision Shopify App SEO IA

## TL;DR (5 lignes max)
- Pourcentage global de couverture estimé
- 3 plus gros gaps prioritaires
- 3 plus gros points forts
- Verdict : pivot nécessaire ou évolution possible du code actuel ?

## 1. Architecture du code actuel
- Arborescence des dossiers
- Stack utilisée (langages, frameworks, libs principales)
- Patterns architecturaux observés
- Le code actuel est-il un script perso pour leoniedelacroix.com ou déjà structuré comme une app ?

## 2. Module-by-module — état vs cible
Pour CHACUNE des 12 sous-sections du chapitre 4 :
- Statut (❌ / 🟡 / ✅)
- Fichiers existants couvrant ce module (avec chemins)
- Ce qui manque concrètement
- Effort estimé pour atteindre la cible (S < 1j / M = 1-3j / L = 3-10j / XL > 10j)

## 3. Stack technique
- Comparaison source par source (chapitre 5)
- Sources gratuites NON-utilisées qui devraient l'être
- Sources payantes utilisées qui peuvent être remplacées par gratuites
- Estimation coût mensuel actuel vs cible (≤ 12€/mois)

## 4. Anti-patterns détectés
- Pour chaque anti-pattern du chapitre 6 trouvé, citer fichier:ligne

## 5. Évaluation : pivot vs évolution
Le code actuel est probablement un pipeline d'automation pour UN store (leoniedelacroix.com).
Pour devenir une Shopify App publique multi-tenant, est-il :
  (a) Réutilisable en grande partie (juste refactor multi-tenant + UI Shopify) ?
  (b) Réutilisable comme moteur back-end (logique SEO/IA) mais nécessite un nouveau front-end Shopify App ?
  (c) Trop spécifique → repartir d'un boilerplate Shopify CLI Remix template ?

Donner une recommandation argumentée.

## 6. Roadmap recommandée
- Top 10 actions priorisées par (impact × facilité)
- Pour chaque : description, fichiers à créer/modifier, effort, dépendances
- Distinguer Phase 1 / 2 / 3 du chapitre 3

## 7. Quick wins (< 1 jour de dev)
- Liste des fixes triviaux qui rapprochent immédiatement de la vision

## 8. Risques techniques identifiés
- Dépendances fragiles, dette technique, code mort, problèmes de sécurité (tokens en clair, etc.)

## 9. Réutilisation maximale du code actuel
- Quels modules du code existant sont VRAIMENT utiles pour la Shopify App ?
- Comment les extraire en libs réutilisables ?
```

---

## 8. Règles d'analyse historiques

1. **Ne modifie aucun fichier** pendant l'audit. Génère uniquement `RAPPORT_AUDIT.md`.
2. **Lis le code en profondeur**, pas seulement les noms de fichiers. Les patterns comptent plus que les noms.
3. **Ne suppose pas** : si un module semble absent, vérifie via grep récursif sur les concepts (`shopify`, `oauth`, `gpt`, `openai`, `meta_description`, `metafield`, `niche`, etc.).
4. **Cite les chemins de fichiers exacts** dans les références (`src/seo/audit.py:42`).
5. **Sois brutal mais constructif** : la finalité est d'identifier les gaps, pas de flatter le code existant.
6. **Pondère par impact business** : un module "Génération IA" manquant > un module "Niche scoring" manquant > un anti-pattern stylistique.
7. **Vérifie les dépendances** : `requirements.txt`, `package.json`, `pyproject.toml`. La présence de `shopify_python_api`, `openai`, `langchain`, `playwright`, `sentence_transformers` change l'analyse.
8. **Identifie le code mort** : modules importés nulle part, fonctions jamais appelées.
9. **Estime l'effort** en T-shirt size (S < 1j, M = 1-3j, L = 3-10j, XL > 10j).
10. **N'oublie pas le contexte mono-store actuel** : le code est probablement écrit pour leoniedelacroix.com en dur. Évalue ce qui doit devenir multi-tenant.

---

## 9. Hors scope de cet audit

- La partie **GEO / LLM SEO / AI Search Optimization** (visibilité dans ChatGPT, Perplexity, AI Overviews Google) sera traitée dans un audit séparé ultérieurement
- L'**aspect commercial** (pricing, GTM, copywriting App Store)
- Le **branding** et le visuel de l'App Store listing
- Le **process de soumission Shopify App Store** (App review, App listing) — sera traité avant lancement

---

**Fin du brief. Bon audit.**
