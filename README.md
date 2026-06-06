# Giulio Geo

> **FR** | [EN below](#english-version)

Outil d'audit et d'optimisation SEO pour boutiques Shopify. Crawle votre catalogue, analyse vos données Google Search Console, détecte les problèmes SEO et applique les corrections directement sur Shopify — en CLI ou via un dashboard web.

---

## Vision

Giulio Geo est un **copilote SEO niche-first pour boutiques Shopify** — conçu pour évoluer de l'outil CLI personnel vers une **app SaaS embarquée dans l'admin Shopify**.

**Le marché est saturé sur** : meta tags automatiques, alt texts, compression images, schema basique (AVADA, Smart SEO, TinyIMG, Booster SEO le font tous).

**Notre angle** : *"quel contenu longue traîne mon catalogue peut réellement dominer ?"* — clusters produits, saturation SERP, keyword gaps vs concurrents — puis génération + application avec validation humaine à chaque étape.

**Contraintes respectées** : budget infra ≤ 12 €/mois, fallbacks LLM gratuits, validation marchande avant apply, conformité Shopify App Store (GDPR, Billing API, App Bridge).

### Roadmap en 11 phases (105 tâches)

| Phase | Périmètre | Statut |
|---|---|---|
| 1 — Fondations & Audit | Crawl, GSC, PageSpeed, détection, score | ✅ |
| 2 — Application supervisée | ICE matrix, apply meta/alt, rollback, alertes | ✅ |
| 3 — Contenu SEO & Niche | Briefs blog, descriptions LT, maillage, E-E-A-T | ✅ |
| 4 — Productisation | Multi-tenant YAML, CLI universel, licences, Docker | ✅ |
| 5 — App Shopify publique | OAuth, FastAPI, plans, doc | ✅ 5/6 (tâche 49 review) |
| 6 — Conformité & Infra async | GDPR, Billing API, async queue, App Bridge, Polaris, Postgres | ✅ |
| 7 — Moteur IA & Niche | LLM provider, Niche Intelligence concrète, observabilité | ✅ |
| 8 — Scale & App Store final | Theme Extension, embeddings, GA4, Common Crawl, préparation App Store | ✅ |
| 9 — Pilote marchand réel | App pilote custom, vraie boutique, retours terrain avant publication | ✅ |
| 10 — Parité scripts CLI → App Shopify | Porter les fonctions CLI restantes dans l'app embedded avant publication | 🔄 3/21 |
| 11 — Soumission App Store publique | Go/no-go puis soumission après pilote + parité fonctionnelle | ⏳ |

---

## Distribution & facturation

Giulio Geo se distribue selon **deux modes** :

| Mode | Cible | Auth | Facturation |
|---|---|---|---|
| 🛍️ **Shopify App Store** | Marchands Shopify (install 1 clic) | OAuth Shopify | **Shopify Billing API** — obligatoire pour App Store |
| ⚙️ **Self-hosted / CLI** | Agences, devs, déploiements internes | Token Custom App | Licence HMAC `LEONIE_API_KEY` |

Voir [`docs/plans.md`](docs/plans.md) pour le détail.

### Pilote marchand réel avant App Store

Avant la soumission publique, Giulio Geo passe par une app pilote Shopify séparée, distribuée directement à la boutique réelle et reliée à l'URL stable `https://pilot.leoniedelacroix.com`. Le déroulé opératoire est documenté dans [`docs/pilot-real-store-setup.md`](docs/pilot-real-store-setup.md), et le plan de test réel dans [`docs/pilot-real-store-test-plan.md`](docs/pilot-real-store-test-plan.md).

Smoke check public du pilote :

```bash
leonie-seo pilot smoke-public
```

## Plans

| Fonctionnalité | Free | Pro | Agency |
|---|:---:|:---:|:---:|
| Audit & détection d'issues | ✅ | ✅ | ✅ |
| Score SEO & rapport Markdown | ❌ | ✅ | ✅ |
| Mise à jour méta / alt text | ❌ | ✅ | ✅ |
| Génération IA (meta, FAQ, briefs blog) | ❌ | ✅ | ✅ |
| Niche Intelligence engine | ❌ | ✅ | ✅ |
| Hreflang (BE/CH expansion) | ❌ | ✅ | ✅ |
| Alertes email (CWV, positions) | ❌ | ✅ | ✅ |
| Multilinguisme IA (EN/DE/NL) | ❌ | ❌ | ✅ |
| GA4 revenue attribution | ❌ | ❌ | ✅ |
| Boutiques | 1 | 1 | Illimité |

---

## Installation

### Option A — pip (CLI)

```bash
git clone https://github.com/adrienlrd/leonie-seo.git
cd leonie-seo
pip install -e .
cp .env.example .env        # remplir les variables
leonie-seo --help
```

### Option B — Docker (backend Python + CLI)

```bash
docker build -t leonie-seo .

# Backend FastAPI (API REST consommée par l'app Shopify Remix)
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/reports:/app/reports \
  --env-file .env \
  --entrypoint uvicorn \
  leonie-seo app.main:app --host 0.0.0.0 --port 8000

# CLI dans la même image
docker run --rm --env-file .env leonie-seo audit crawl
```

> Pour la couche UI Shopify embedded (App Bridge + Polaris), voir `shopify-app/` — scaffold Remix séparé.

### Option C — Script d'installation rapide

```bash
curl -sSL https://raw.githubusercontent.com/adrienlrd/leonie-seo/main/install.sh | bash
```

---

## Configuration `.env`

```env
# Shopify
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_STORE_DOMAIN=xxx.myshopify.com

# Google
PAGESPEED_API_KEY=...

# App web (OAuth Shopify)
SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
SHOPIFY_SCOPES=read_products,write_products
APP_URL=https://votre-domaine.com

# Licence (plans Pro/Agency)
LEONIE_API_KEY=LEO-...

# Alertes email
GMAIL_SENDER=...
GMAIL_APP_PASSWORD=...
ALERT_EMAIL=...
```

---

## Workflow CLI hebdomadaire

```bash
leonie-seo audit crawl           # snapshot catalogue Shopify
leonie-seo audit gsc             # données GSC 90 jours
leonie-seo audit pagespeed       # Core Web Vitals
leonie-seo audit detect          # détection problèmes
leonie-seo report weekly         # rapport Markdown
# → lire reports/YYYY-MM-DD/report.md

leonie-seo apply meta --dry-run  # prévisualiser corrections
leonie-seo apply meta --apply    # appliquer sur Shopify
```

---

## Gestion des licences (mode self-hosted / CLI)

> Pour le mode Shopify App Store, voir Shopify Billing API dans [`docs/plans.md`](docs/plans.md) — les commandes ci-dessous ne s'appliquent **pas** au mode App Store.

```bash
# Générer une clé pour un client (Agency)
leonie-seo license issue --tenant client-boutique --plan agency --days 365

# Vérifier la licence active
leonie-seo license check
```

---

## Structure du projet

```
shopify-app/      ← App Shopify embedded (Remix + App Bridge + Polaris)
  app/            ← routes Remix, OAuth sessions multi-tenant
  extensions/     ← Theme App Extension (JSON-LD)

app/              ← Backend Python (moteur SEO / IA)
  api/            ← endpoints REST consommés par shopify-app/
  oauth/          ← OAuth Shopify + webhooks GDPR
  billing/        ← Shopify Billing API (appSubscriptionCreate)
  jobs/           ← async queue Postgres-backed
  llm/            ← provider abstraction (GPT-4o mini + fallbacks)
  niche/          ← Niche Intelligence engine (clusters, gaps, signals)
  embeddings/     ← multilingual-e5-base + pgvector
  impact/         ← ROI estimation (CTR curve × conv × AOV)
  ga4/            ← GA4 Data API client + funnel
  jsonld/         ← Schema.org builders (Product, Collection, Org)
  observability/  ← logs JSON, métriques par tenant, coût LLM
  apply/          ← bulk orchestrator (rate-limit, retry)

scripts/          ← CLI Click (audit + apply + report) — réutilisable
  audit/          ← lecture seule : crawl, GSC, PageSpeed
  apply/          ← écriture Shopify (dry-run par défaut)
  report/         ← génération rapports Markdown

config/
  tenants/        ← YAML par boutique
  niches/         ← règles métier par secteur
  prompts/        ← templates Jinja2 par type de contenu

data/
  history.db      ← SQLite legacy (migration Neon Postgres en Phase 6)
  raw/            ← exports bruts (gitignored)

reports/          ← rapports horodatés YYYY-MM-DD/
```

---

## Documentation complète

- [Guide utilisateur (FR)](docs/guide-utilisateur.fr.md)
- [User guide (EN)](docs/user-guide.en.md)
- [Détail des plans](docs/plans.md)
- [Pilote réel avant App Store](docs/pilot-real-store-setup.md)

---

---

## English version

SEO audit and optimization tool for Shopify stores. Crawls your catalog, analyzes Google Search Console data, detects SEO issues and applies fixes directly on Shopify — via CLI or a web dashboard.

**Vision**: a niche-aware SEO copilot that evolves from a personal CLI into a Shopify-embedded SaaS — powered by LLMs for content generation, semantic clustering, and automated audits. Target infrastructure cost: ≤ €12/month.

### Quick start

```bash
pip install -e .
cp .env.example .env   # fill in your credentials
leonie-seo --help
```

### Weekly CLI workflow

```bash
leonie-seo audit crawl       # Shopify catalog snapshot
leonie-seo audit gsc         # 90-day GSC data
leonie-seo audit pagespeed   # Core Web Vitals
leonie-seo audit detect      # detect SEO issues
leonie-seo report weekly     # generate Markdown report

leonie-seo apply meta --dry-run   # preview fixes
leonie-seo apply meta --apply     # push to Shopify
```

### Full documentation

- [User guide (EN)](docs/user-guide.en.md)
- [Guide utilisateur (FR)](docs/guide-utilisateur.fr.md)
- [Plans & pricing](docs/plans.md)
