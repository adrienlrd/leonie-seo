# PROGRESS — SEO Leoniedelacroix.com

## État global
- Phase actuelle : Phase 3 — Contenu SEO & Intelligence niche (tâches 30–39)
- Dernière session : 2026-05-08
- Phase 2 : **14/14 complètes** ✅
- Prochain objectif : Tâche 30 — Générateur de briefs articles blog

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

### Phase 2 — Application supervisée (tâches 16–29) ✅
- **16** `scripts/report/ice_matrix.py` — Matrice ICE pondérée GSC
- **17–21** `generate_suggestions.py` + `update_alt_text.py` — **26 méta + 17 alt texts poussés** sur Shopify (0 erreur)
- **22** `scripts/apply/create_redirects.py` — import 301 bulk depuis CSV
- **23** `scripts/apply/add_schema.py` — JSON-LD schema.org/Product via metafield custom.json_ld
- **24** `scripts/apply/rollback.py` — CLI rollback SQLite (`--list`, `--revert-ids`, `--revert-since`)
- **25** `scripts/audit/detect_gsc_opportunities.py` — 3 zones (quick win, CTR faible, long terme) ; **17 opportunités, +148 clics estimés**
- **26** `scripts/audit/analyze_longtail.py` — gap analysis mots-clés vs GSC + Shopify ; correction keywords.yaml (petfood → accessoires animaux)
- **27** `scripts/report/generate_delta_report.py` — rapport avant/après : **56.3 → 83.9 (+27.6 pts), 62/68 issues résolues**
- **28** `.github/workflows/weekly_audit.yml` — pipeline CI complet, 6 secrets configurés sur GitHub
- **29** `scripts/report/send_alerts.py` — alertes email CWV + positions + CTR, SMTP Gmail, 15 tests

### Données réelles
- **50 URLs GSC** · 90 jours · 245 clics · 3 736 impressions · position moyenne 6.0
- **69 changements** loggés dans `data/history.db`
- **147 tests unitaires** — 147/147 ✅ — ruff clean ✅
- **Score SEO avant optimisations : 56.3 → après : 83.9 (+27.6 pts)**
- **Pipeline CI** validé manuellement : tests + audit + commit rapport + alertes email

## ⏳ À faire — Phase 3 (tâches 30–39)

| # | Tâche | Priorité |
|---|---|---|
| 30 | Générateur de briefs articles blog (H1/H2, mots-clés, angle E-E-A-T) | Haute |
| 31 | Réécriture descriptions produits longue traîne — ton premium FR | Haute |
| 32 | Maillage interne automatique — détection opportunités liens blog → produits | Moyenne |
| 33 | Analyse sémantique fiches produits vs concurrents (Zooplus, Wanimo) | Moyenne |
| 34 | Générateur de FAQ structurée par catégorie produit | Moyenne |
| 35 | Détecteur de cannibalisation — pages en compétition sur un même mot-clé | Moyenne |
| 36 | Score E-E-A-T par page | Basse |
| 37 | Générateur balises hreflang si extension BE/CH francophone | Basse |
| 38 | Rapport mensuel synthétique PDF | Basse |
| 39 | Dashboard CLI interactif `rich` — vue temps réel santé SEO du site | Basse |

## ⏳ Actions manuelles en attente

### Admin Shopify
- [ ] Re-crawler (`python -m scripts.audit.crawl_shopify`) + relancer `add_schema --apply` (pour avoir les prix dans le JSON-LD)
- [ ] Ajouter snippet Liquid dans `product.liquid` (avant `</head>`) pour activer le JSON-LD
- [ ] Corriger 6 méta titles trop courts dans l'admin (Bol Félin Raffiné, L'abreuvoir, Griffoir Dimitrios, Distributeur Pet Feeder, La Fontaine Smart, Le Harnais)
- [ ] Écrire titres descriptifs pour 6 collections courtes

### GitHub Actions — secrets alertes email
- [ ] Ajouter `GMAIL_SENDER` (adresse Gmail expéditeur)
- [ ] Ajouter `GMAIL_APP_PASSWORD` (mot de passe d'application Google)
- [ ] Ajouter `ALERT_EMAIL` = adrien.leredde@outlook.com

### Opportunités GSC prioritaires
- [ ] **L'abreuvoir** — pos 11.5, 344 impr → enrichir contenu + méta
- [ ] **Le Tour De Cou Pour Chat** — pos 4.7, 271 impr, CTR 0.4% → réécrire méta title
- [ ] **Le Tour De Cou Pour Chien** — pos 6.1, 210 impr, CTR 0% → réécrire méta

## 📋 Historique des sessions

### Session 2026-05-08 (Phase 2 tâche 29 + validation CI)
- Validation complète du pipeline GitHub Actions (nombreux fix : requirements.txt vide, PATH ruff, timeout pagespeed, permissions push)
- Tâche 29 : send_alerts.py — CWV + positions + CTR, SMTP Gmail, 15 tests
- 147/147 tests verts, ruff clean

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
