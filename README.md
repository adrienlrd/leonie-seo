# SEO Tool — Leoniedelacroix.com

Outil CLI Python d'audit et d'optimisation SEO pour boutique Shopify.
Audite le site chaque semaine, génère un rapport Markdown avec les problèmes priorisés et les corrections prêtes à appliquer.

---

## Prérequis

- Python 3.11+
- Compte Google Cloud avec Search Console, GA4 et PageSpeed activés
- Token Shopify Admin API (Custom App)
- Screaming Frog Free (pour le crawl local)

## Installation

```bash
git clone <repo>
cd leonie-seo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Remplir les variables dans .env
```

## Configuration `.env`

```
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_STORE_DOMAIN=287c4a-bb.myshopify.com
GOOGLE_PAGESPEED_API_KEY=...
GA4_PROPERTY_ID=properties/459014688
```

Le fichier `oauth_client.json` (Google OAuth) doit être à la racine.
Au premier run de `fetch_gsc.py`, une fenêtre navigateur s'ouvre pour autorisation.

---

## Commandes

### Audit (lecture seule — sans risque)

```bash
# Crawl complet du catalogue Shopify
python -m scripts.audit.crawl_shopify

# Export 90 jours Google Search Console
python -m scripts.audit.fetch_gsc

# Core Web Vitals via PageSpeed
python -m scripts.audit.fetch_pagespeed

# Détecter les problèmes SEO
python -m scripts.audit.detect_issues

# Parser un export CSV Screaming Frog
python -m scripts.audit.crawl_shopify --screaming-frog data/raw/crawl.csv
```

### Rapport

```bash
# Générer le rapport de la semaine
python -m scripts.report.generate_report --week

# Rapport pour une date précise
python -m scripts.report.generate_report --date 2026-05-01
```

### Application des corrections (écriture Shopify)

**Par défaut : dry-run. Rien n'est modifié sans `--apply`.**

```bash
# Voir les corrections meta sans les appliquer
python -m scripts.apply.update_meta --dry-run --collection=croquettes-chien

# Appliquer les corrections meta (confirmation demandée)
python -m scripts.apply.update_meta --apply --collection=croquettes-chien

# Mettre à jour les alt texts
python -m scripts.apply.update_alt_text --dry-run
python -m scripts.apply.update_alt_text --apply

# Créer des redirections 301 depuis un CSV validé
python -m scripts.apply.create_redirects --dry-run --file=data/raw/redirects.csv
python -m scripts.apply.create_redirects --apply --file=data/raw/redirects.csv
```

---

## Structure

```
scripts/audit/    ← lecture seule, sans risque
scripts/apply/    ← écriture Shopify, dry-run par défaut
scripts/report/   ← génération rapports Markdown
config/           ← règles métier et mots-clés (YAML)
data/raw/         ← exports bruts (gitignored)
data/history.db   ← SQLite, historique et rollback
reports/          ← rapports Markdown horodatés
skills/           ← règles d'audit SEO, patterns GraphQL, niche petfood
```

---

## Workflow hebdomadaire recommandé

1. Lancer Screaming Frog sur le site → exporter CSV dans `data/raw/`
2. `python -m scripts.audit.crawl_shopify`
3. `python -m scripts.audit.fetch_gsc`
4. `python -m scripts.audit.fetch_pagespeed`
5. `python -m scripts.audit.detect_issues`
6. `python -m scripts.report.generate_report --week`
7. Lire le rapport dans `reports/YYYY-MM-DD/`
8. Valider les corrections, puis `--apply`
