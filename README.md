# Léonie SEO

> **FR** | [EN below](#english-version)

Outil d'audit et d'optimisation SEO pour boutiques Shopify. Crawle votre catalogue, analyse vos données Google Search Console, détecte les problèmes SEO et applique les corrections directement sur Shopify — en CLI ou via un dashboard web.

---

## Plans

| Fonctionnalité | Free | Pro | Agency |
|---|:---:|:---:|:---:|
| Audit & détection d'issues | ✅ | ✅ | ✅ |
| Score SEO & rapport Markdown | ❌ | ✅ | ✅ |
| Mise à jour méta / alt text | ❌ | ✅ | ✅ |
| Hreflang (BE/CH expansion) | ❌ | ✅ | ✅ |
| Alertes email (CWV, positions) | ❌ | ✅ | ✅ |
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

### Option B — Docker (web app + CLI)

```bash
docker build -t leonie-seo .

# Web app (dashboard React + API FastAPI)
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/reports:/app/reports \
  --env-file .env \
  --entrypoint uvicorn \
  leonie-seo app.main:app --host 0.0.0.0 --port 8000

# CLI dans le même image
docker run --rm --env-file .env leonie-seo audit crawl
```

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

## Gestion des licences

```bash
# Générer une clé pour un client (Agency)
leonie-seo license issue --tenant client-boutique --plan agency --days 365

# Vérifier la licence active
leonie-seo license check
```

---

## Structure du projet

```
app/              ← API FastAPI + OAuth Shopify
  api/            ← endpoints REST (audit, apply, shops, plans)
  oauth/          ← flux OAuth marchands
frontend/         ← Dashboard React (Vite)
scripts/
  audit/          ← lecture seule : crawl, GSC, PageSpeed
  apply/          ← écriture Shopify (dry-run par défaut)
  report/         ← génération rapports Markdown
config/
  tenants/        ← YAML par boutique
  niches/         ← règles métier par secteur
data/
  history.db      ← SQLite : historique + rollback
  raw/            ← exports bruts (gitignored)
reports/          ← rapports horodatés YYYY-MM-DD/
```

---

## Documentation complète

- [Guide utilisateur (FR)](docs/guide-utilisateur.fr.md)
- [User guide (EN)](docs/user-guide.en.md)
- [Détail des plans](docs/plans.md)

---

---

## English version

SEO audit and optimization tool for Shopify stores. Crawls your catalog, analyzes Google Search Console data, detects SEO issues and applies fixes directly on Shopify — via CLI or a web dashboard.

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
