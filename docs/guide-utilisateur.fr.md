# Guide utilisateur — Léonie SEO

## Table des matières

1. [Présentation](#présentation)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Premiers pas — Mode CLI](#premiers-pas--mode-cli)
5. [Premiers pas — Dashboard web](#premiers-pas--dashboard-web)
6. [Référence des commandes CLI](#référence-des-commandes-cli)
7. [Les plans](#les-plans)
8. [FAQ](#faq)

---

## Présentation

Léonie SEO automatise l'audit SEO de votre boutique Shopify. Il :

- Crawle votre catalogue (produits, collections, méta-données)
- Récupère vos données Google Search Console (positions, clics, impressions)
- Mesure vos Core Web Vitals via PageSpeed Insights
- Détecte les problèmes SEO prioritaires (méta manquants, alt text absent, balises dupliquées…)
- Génère un rapport Markdown hebdomadaire avec les corrections prêtes à appliquer
- Pousse les corrections directement sur Shopify (avec confirmation)

---

## Installation

### Prérequis

- Python 3.11 ou supérieur
- Un compte Google Cloud avec Search Console activé
- Un token Shopify Admin API (Custom App ou OAuth)

### Via pip

```bash
git clone https://github.com/adrienlrd/leonie-seo.git
cd leonie-seo
pip install -e .
```

### Via Docker

```bash
docker build -t leonie-seo .
docker run --rm --env-file .env leonie-seo --help
```

### Script rapide

```bash
curl -sSL https://raw.githubusercontent.com/adrienlrd/leonie-seo/main/install.sh | bash
```

---

## Configuration

Copiez le fichier d'exemple et remplissez vos identifiants :

```bash
cp .env.example .env
```

### Variables obligatoires

| Variable | Description |
|---|---|
| `SHOPIFY_ACCESS_TOKEN` | Token Shopify Admin API (`shpat_...`) |
| `SHOPIFY_STORE_DOMAIN` | Domaine myshopify (`xxx.myshopify.com`) |
| `PAGESPEED_API_KEY` | Clé API Google PageSpeed Insights |

### Variables pour le dashboard web (OAuth)

| Variable | Description |
|---|---|
| `SHOPIFY_CLIENT_ID` | ID de votre app Shopify Partners |
| `SHOPIFY_CLIENT_SECRET` | Secret de votre app |
| `SHOPIFY_SCOPES` | `read_products,write_products,read_content` |
| `APP_URL` | URL publique de votre instance |

### Variables pour les alertes email

| Variable | Description |
|---|---|
| `GMAIL_SENDER` | Adresse Gmail expéditeur |
| `GMAIL_APP_PASSWORD` | Mot de passe d'application Gmail |
| `ALERT_EMAIL` | Destinataire des alertes |

### Licence (plans Pro/Agency)

```env
LEONIE_API_KEY=LEO-...       # votre clé de licence
LICENSE_SECRET=...           # secret de signature (fourni avec la clé)
```

---

## Premiers pas — Mode CLI

### 1. Lancer un audit complet

```bash
# Crawl du catalogue Shopify
leonie-seo audit crawl

# Données Google Search Console (90 derniers jours)
leonie-seo audit gsc

# Core Web Vitals
leonie-seo audit pagespeed

# Détection des problèmes SEO
leonie-seo audit detect
```

### 2. Générer le rapport

```bash
leonie-seo report weekly
```

Le rapport est créé dans `reports/YYYY-MM-DD/report.md`. Il contient :
- Score SEO global avec détail par composant
- Liste des problèmes classés par sévérité (critical / high / medium / low)
- Corrections suggérées avec impact estimé

### 3. Appliquer les corrections

**Les scripts d'application fonctionnent toujours en dry-run par défaut.**

```bash
# Prévisualiser les corrections meta
leonie-seo apply meta --dry-run

# Appliquer après validation
leonie-seo apply meta --apply

# Alt text des images
leonie-seo apply alt --dry-run
leonie-seo apply alt --apply

# Redirections 301 depuis un CSV
leonie-seo apply redirects --file data/raw/redirects.csv --dry-run
leonie-seo apply redirects --file data/raw/redirects.csv --apply
```

---

## Premiers pas — Dashboard web

### Lancer l'API et le frontend

```bash
# API FastAPI (port 8000)
uvicorn app.main:app --reload

# Dashboard React en dev (port 5173)
cd frontend && npm run dev
```

Ouvrez `http://localhost:5173/?shop=xxx.myshopify.com` dans votre navigateur.

### Onglets disponibles

| Onglet | Description |
|---|---|
| **Dashboard** | Score SEO global, compteurs produits/issues |
| **Issues** | Liste filtrée des problèmes détectés |
| **Appliquer** | Mise à jour des méta-titres et descriptions |
| **Aide** | FAQ et documentation |

### Badge plan

Le badge dans l'en-tête (FREE / PRO / AGENCY) indique votre plan actif. Il est résolu depuis `LEONIE_API_KEY` dans votre `.env`.

---

## Référence des commandes CLI

```
leonie-seo
├── audit
│   ├── crawl          Snapshot catalogue Shopify
│   ├── gsc            Données Google Search Console 90 jours
│   ├── pagespeed      Core Web Vitals (mobile + desktop)
│   ├── detect         Détection problèmes SEO
│   └── screaming      Parser export CSV Screaming Frog
├── apply
│   ├── meta           Mettre à jour méta-titres et descriptions
│   ├── alt            Mettre à jour alt text des images
│   ├── redirects      Créer des redirections 301 en bulk
│   ├── schema         Ajouter JSON-LD Product sur les fiches
│   └── rollback       Annuler les N dernières modifications
├── report
│   ├── weekly         Rapport hebdomadaire Markdown
│   ├── delta          Comparaison avant/après par page
│   ├── hreflang       Balises hreflang (expansion BE/CH)
│   ├── alerts         Détecter régressions et envoyer email
│   └── dashboard      Rapport de tableau de bord
├── setup
│   ├── init           Initialiser une nouvelle boutique/tenant
│   ├── list           Lister les tenants configurés
│   └── check          Vérifier la configuration active
└── license
    ├── issue          Générer une clé de licence signée
    └── check          Valider la licence active
```

---

## Les plans

| Fonctionnalité | Free | Pro | Agency |
|---|:---:|:---:|:---:|
| Audit (crawl, GSC, PageSpeed) | ✅ | ✅ | ✅ |
| Détection d'issues | ✅ | ✅ | ✅ |
| Score SEO | ✅ | ✅ | ✅ |
| Rapport Markdown | ❌ | ✅ | ✅ |
| Mise à jour méta / alt text | ❌ | ✅ | ✅ |
| Hreflang (expansion BE/CH) | ❌ | ✅ | ✅ |
| Alertes email | ❌ | ✅ | ✅ |
| Nombre de boutiques | 1 | 1 | Illimité |
| Rollback SQLite | ❌ | ✅ | ✅ |

### Générer une clé de licence

```bash
# Plan Pro pour une boutique, valide 1 an
leonie-seo license issue --tenant ma-boutique --plan pro --days 365

# Plan Agency pour une agence
leonie-seo license issue --tenant mon-agence --plan agency --days 365
```

Ajoutez la clé dans le `.env` du client :

```env
LEONIE_API_KEY=LEO-<clé générée>
```

---

## FAQ

**Q : L'outil modifie-t-il mon site sans confirmation ?**
Non. Tous les scripts `apply` fonctionnent en `--dry-run` par défaut. Vous devez explicitement passer `--apply` pour écrire sur Shopify.

**Q : Mes données Shopify restent-elles sur mon serveur ?**
Oui. Léonie SEO est un outil auto-hébergé. Vos tokens d'accès et données produits ne quittent jamais votre environnement (CLI local ou serveur Docker).

**Q : Que se passe-t-il si ma licence expire ?**
Le plan bascule automatiquement en Free. Vous conservez l'accès aux fonctions d'audit. Les fonctions d'écriture (apply, alertes, rapports) sont désactivées.

**Q : Puis-je utiliser l'outil pour plusieurs boutiques ?**
Oui, avec le plan Agency. Chaque boutique a son propre fichier `config/tenants/XXX.yaml`.

**Q : Comment annuler une modification appliquée ?**
```bash
leonie-seo apply rollback --last 5   # annule les 5 dernières modifications
```
Toutes les modifications sont tracées dans `data/history.db`.

**Q : L'app est-elle compatible avec tous les thèmes Shopify ?**
Les fonctions d'audit et de mise à jour meta/alt sont universelles. Le snippet Liquid hreflang doit être intégré manuellement dans `theme.liquid`.

**Q : Comment contacter le support ?**
Ouvrez une issue sur le dépôt GitHub ou envoyez un email à `support@leonie-seo.com`.
