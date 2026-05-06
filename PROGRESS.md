# PROGRESS — SEO Leoniedelacroix.com

## État global
- Phase actuelle : Phase 2 — Application supervisée (tâches 16–29)
- Dernière session : 2026-05-05 → 2026-05-06
- Tâches Phase 2 complètes : 16, 17, 18, 19, 20, 21, 22, 23, 24 (9/14)
- Prochain objectif : Tâche 25 — Détecteur opportunités GSC (positions 11–20)

## ✅ Terminé

### Infrastructure
- Initialisation repo Git + structure dossiers
- Création CLAUDE.md — réorganisé avec PROJECT_BRIEF.md comme ligne directrice (protocole début de session, ordre des tâches, règles non négociables)
- Setup credentials API : Shopify token, Google OAuth, PageSpeed key, GA4 Property ID
- `.env`, `.env.example`, `.gitignore` configurés
- `pyproject.toml` avec `[tool.setuptools]` pour discovery correcte

### Phase 1 — Fondations & Audit (tâches 1–15) ✅
- `config/seo_rules.yaml` — règles métier (longueurs, poids scoring)
- `config/keywords.yaml` — 25 mots-clés cibles par catégorie
- `scripts/models.py` — modèles Pydantic partagés (`Issue`, `SEOScore`, `Severity`)
- `scripts/audit/crawl_shopify.py` — GraphQL paginé, snapshot JSON + SQLite (ajout `status` + `variants.price`)
- `scripts/audit/fetch_gsc.py` — OAuth navigateur, export 90j par URL → CSV (+ `GSC_SITE_URL` env var)
- `scripts/audit/fetch_pagespeed.py` — score mobile/desktop + CWV → CSV
- `scripts/audit/parse_screaming_frog.py` — parser overview/images/redirects CSV
- `scripts/audit/detect_issues.py` — 5 détecteurs : titles, descriptions, alt text, duplicates, redirects/404
- `scripts/report/generate_report.py` — score /100 pondéré + rapport Markdown horodaté
- `scripts/apply/update_meta.py` — mutation GraphQL, dry-run par défaut, logging SQLite, garde-fou 429
- `data/history.db` initialisé via `init_db()` (tables : `snapshots`, `seo_changes`)

### Phase 2 — Application supervisée (tâches 16–24) 🔄
- **Tâche 16** `scripts/report/ice_matrix.py` — Matrice ICE : scores Impact×Confiance/Effort pondérés par données GSC (impressions + position), export JSON + table Rich
- **Tâche 17–21** `scripts/apply/generate_suggestions.py` + `update_alt_text.py` — générateur rule-based méta titres (50–65 chars), descriptions (120–155 chars), alt texts (≤125 chars) ; **26 méta + 17 alt texts poussés sur Shopify** (0 erreur) ; correction auto "Léonie de la Croix" → "Léonie Delacroix"
- **Tâche 22** `scripts/apply/create_redirects.py` — import 301 bulk depuis CSV, validation (slash, self-redirect, doublons, conflits handles), dry-run par défaut
- **Tâche 23** `scripts/apply/add_schema.py` — JSON-LD schema.org/Product via metafield `custom.json_ld` (name, url, brand, description, image, offers), snippet Liquid fourni
- **Tâche 24** `scripts/apply/rollback.py` — CLI rollback SQLite : `--list`, `--revert-ids`, `--revert-since` ; révertit seo.title/description/image.altText ; skip url_redirect + metafield avec instructions manuelles ; marque `'reverted'` dans history.db

### Données réelles collectées
- **50 URLs GSC** · 90 jours · 245 clics · 3 736 impressions · CTR 10.3% · position moyenne 6.0
- **69 changements** loggés dans `data/history.db` (seo_changes)
- **86 tests unitaires** — 86/86 ✅ — ruff clean ✅

## ⏳ À faire — Phase 2 (suite)

| # | Tâche | Priorité |
|---|---|---|
| 25 | Détecteur opportunités GSC — positions 11–20 à optimiser | 🔥 Court terme |
| 26 | Analyse concurrentielle longue traîne petfood FR | Moyen terme |
| 27 | Rapport comparaison avant/après par page (delta score SEO) | Moyen terme |
| 28 | GitHub Actions cron hebdomadaire — audit auto + commit rapport | Moyen terme |
| 29 | Alertes email — régression CWV, nouveaux 404, chute de position | Long terme |

## ⏳ Actions manuelles en attente

### Admin Shopify (à faire manuellement)
- [ ] **Re-crawler** (`python -m scripts.audit.crawl_shopify`) pour avoir les prix → relancer `add_schema --apply`
- [ ] **Snippet Liquid** à ajouter dans `product.liquid` ou `product.json` (avant `</head>`) :
  ```liquid
  {% if product.metafields.custom.json_ld %}
    <script type="application/ld+json">
      {{ product.metafields.custom.json_ld.value }}
    </script>
  {% endif %}
  ```
- [ ] **6 méta titres trop courts** à corriger dans l'admin :
  - Bol Félin Raffiné (42 chars)
  - L'abreuvoir (45 chars)
  - Griffoir Dimitrios (47 chars)
  - Distributeur Pet Feeder (48 chars)
  - La Fontaine Smart (mal formaté)
  - Le Harnais (à vérifier)
- [ ] **Collections courtes** : titres plus descriptifs pour Chien, Chat, Accessoires, Pour la maison, VENTES PRIVÉES, Un coup de cœur
- [ ] **2 produits en anglais** : traduire pour débloquer génération métas

### Opportunités GSC identifiées
- [ ] **L'abreuvoir** — 344 impressions, 18 clics, position 11 → pousser en page 1
- [ ] **Le Tour De Cou Pour Chien** — 210 impressions, 0 clic, position 6 → améliorer méta
- [ ] **Le Tour De Cou Pour Chat** — 271 impressions, 2 clics, position 4.7 → améliorer méta
- [ ] **Collection Chien** — 107 impressions, position 4.5 → titre plus descriptif

## 📋 Historique des sessions

### Session 2026-05-05 → 2026-05-06 (Phase 2 tâches 16–24)
- CLAUDE.md réorganisé avec protocole début de session + ordre des tâches
- Tâche 16 : ICE matrix (`ice_matrix.py` + 6 tests)
- Tâche 22 : create_redirects.py + 9 tests
- Tâche 23 : add_schema.py (JSON-LD structured data) + 9 tests
- Tâche 24 : rollback.py (CLI rollback SQLite) + 13 tests
- 86/86 tests verts, ruff clean, 4 commits atomiques

### Session 2026-05-05 (Phase 1 complète + Phase 2 tâches 17–21 + GSC)
- Phase 1 complète : 14 fichiers, 49 tests
- 26 méta + 17 alt texts poussés sur Shopify (0 erreur)
- Correction brand name "Léonie de la Croix" → "Léonie Delacroix"
- GSC connecté : OAuth, test user, GSC_SITE_URL, 50 URLs · 3 736 impressions
- Logging SQLite + garde-fou 429 ajoutés aux scripts apply

### Session 2026-04-28
- Setup Google Cloud : projet `leonie-seo`, 3 APIs activées, OAuth client créé
- Bascule service account → OAuth utilisateur (Search Console refusait le service account)
- GA4 Property ID récupéré

### Session 2026-04-22
- Custom App Shopify créée, token obtenu, .env configuré

### Session 2026-04-20
- Initialisation complète du projet
