# PROGRESS — SEO Leoniedelacroix.com

## État global
- Phase actuelle : Phase 2 — Application supervisée (tâches 16–29)
- Dernière session : 2026-05-06
- Tâches Phase 2 complètes : 16–28 (13/14)
- Prochain objectif : Tâche 29 — Alertes email (régression CWV, nouveaux 404, chute de position)

## ✅ Terminé

### Infrastructure
- Initialisation repo Git + structure dossiers
- CLAUDE.md réorganisé avec protocole début de session + ordre des tâches
- Setup credentials API : Shopify token, Google OAuth, PageSpeed key, GA4 Property ID
- `.env`, `.env.example`, `.gitignore` configurés
- `pyproject.toml` avec `[tool.setuptools]` pour discovery correcte

### Phase 1 — Fondations & Audit (tâches 1–15) ✅
- `scripts/audit/crawl_shopify.py` — GraphQL paginé, snapshot JSON + SQLite
- `scripts/audit/fetch_gsc.py` — OAuth navigateur, export 90j par URL
- `scripts/audit/fetch_pagespeed.py` — score mobile/desktop + CWV
- `scripts/audit/parse_screaming_frog.py` — parser overview/images/redirects CSV
- `scripts/audit/detect_issues.py` — 5 détecteurs (titles, descriptions, alt, duplicates, redirects/404)
- `scripts/report/generate_report.py` — score /100 pondéré + rapport Markdown horodaté
- `scripts/apply/update_meta.py` — mutation GraphQL, dry-run par défaut, logging SQLite

### Phase 2 — Application supervisée (tâches 16–28) ✅
- **16** `scripts/report/ice_matrix.py` — Matrice ICE pondérée GSC
- **17–21** `generate_suggestions.py` + `update_alt_text.py` — **26 méta + 17 alt texts poussés** sur Shopify (0 erreur)
- **22** `scripts/apply/create_redirects.py` — import 301 bulk depuis CSV
- **23** `scripts/apply/add_schema.py` — JSON-LD schema.org/Product via metafield custom.json_ld
- **24** `scripts/apply/rollback.py` — CLI rollback SQLite (`--list`, `--revert-ids`, `--revert-since`)
- **25** `scripts/audit/detect_gsc_opportunities.py` — 3 zones (quick win, CTR faible, long terme) ; **17 opportunités, +148 clics estimés**
- **26** `scripts/audit/analyze_longtail.py` — gap analysis mots-clés vs GSC + Shopify ; correction keywords.yaml (petfood → accessoires animaux)
- **27** `scripts/report/generate_delta_report.py` — rapport avant/après : **56.3 → 83.9 (+27.6 pts), 62/68 issues résolues**
- **28** `.github/workflows/weekly_audit.yml` — pipeline CI complet, 6 secrets configurés sur GitHub

### Données réelles
- **50 URLs GSC** · 90 jours · 245 clics · 3 736 impressions · position moyenne 6.0
- **69 changements** loggés dans `data/history.db`
- **132 tests unitaires** — 132/132 ✅ — ruff clean ✅
- **Score SEO avant optimisations : 56.3 → après : 83.9 (+27.6 pts)**

## ⏳ À faire — Tâche restante Phase 2

| # | Tâche | Priorité |
|---|---|---|
| 29 | Alertes email — régression CWV, nouveaux 404, chute de position | Moyen terme |

## ⏳ Actions manuelles en attente

### Admin Shopify
- [ ] Re-crawler (`python -m scripts.audit.crawl_shopify`) + relancer `add_schema --apply` (pour avoir les prix dans le JSON-LD)
- [ ] Ajouter snippet Liquid dans `product.liquid` (avant `</head>`) pour activer le JSON-LD
- [ ] Corriger 6 méta titles trop courts dans l'admin (Bol Félin Raffiné, L'abreuvoir, Griffoir Dimitrios, Distributeur Pet Feeder, La Fontaine Smart, Le Harnais)
- [ ] Écrire titres descriptifs pour 6 collections courtes

### GitHub Actions
- [ ] **🔴 PRIORITÉ PROCHAINE SESSION** — Tester le workflow manuellement pour valider les 6 secrets : aller sur GitHub → onglet Actions → "Audit SEO hebdomadaire" → "Run workflow" → vérifier que chaque étape passe sans erreur d'authentification

### Opportunités GSC prioritaires
- [ ] **L'abreuvoir** — pos 11.5, 344 impr → enrichir contenu + méta
- [ ] **Le Tour De Cou Pour Chat** — pos 4.7, 271 impr, CTR 0.4% → réécrire méta title
- [ ] **Le Tour De Cou Pour Chien** — pos 6.1, 210 impr, CTR 0% → réécrire méta

## 📋 Historique des sessions

### Session 2026-05-06 (Phase 2 tâches 25–28)
- Tâche 25 : detect_gsc_opportunities.py — 17 opportunités, +148 clics estimés (20 tests)
- Tâche 26 : analyze_longtail.py — gap analysis + correction keywords.yaml (petfood → accessoires) (15 tests)
- Tâche 27 : generate_delta_report.py — score 56.3→83.9, 62 issues résolues (11 tests)
- Tâche 28 : weekly_audit.yml reécrit — pipeline complet, 6 secrets GitHub configurés
- 132/132 tests verts, ruff clean

### Session 2026-05-05 → 2026-05-06 (Phase 2 tâches 16–24)
- CLAUDE.md réorganisé avec protocole début de session
- Tâches 16, 22, 23, 24 : ICE matrix, create_redirects, add_schema, rollback (37 tests)

### Session 2026-05-05 (Phase 1 + tâches 17–21 + GSC)
- Phase 1 complète : 14 fichiers, 49 tests
- 26 méta + 17 alt texts poussés sur Shopify
- GSC connecté : 50 URLs · 3 736 impressions

### Sessions précédentes
- 2026-04-28 : Setup Google Cloud OAuth
- 2026-04-22 : Custom App Shopify
- 2026-04-20 : Initialisation projet
