# PROGRESS — SEO Leoniedelacroix.com

## État global
- Phase actuelle : Phase 4 — Productisation (tâche 44)
- Dernière session : 2026-05-08
- Phase 1 : **15/15 complètes** ✅
- Phase 2 : **14/14 complètes** ✅
- Phase 3 : **10/10 complètes** ✅
- Tests : **389/389** ✅ — ruff clean ✅

## ✅ Terminé

### Infrastructure
- Initialisation repo Git + structure dossiers
- CLAUDE.md réorganisé avec protocole début de session + ordre des tâches
- Setup credentials API : Shopify token, Google OAuth, PageSpeed key, GA4 Property ID
- `.env`, `.env.example`, `.gitignore` configurés
- `pyproject.toml` avec `[tool.setuptools]` pour discovery correcte

### Phase 1 — Fondations & Audit (tâches 1–15) ✅
- `scripts/audit/crawl_shopify.py` — GraphQL paginé, snapshot JSON + SQLite
- `scripts/audit/fetch_gsc.py` — OAuth navigateur, export 90j par URL + query×page
- `scripts/audit/fetch_pagespeed.py` — score mobile/desktop + CWV (timeout 600s, retry)
- `scripts/audit/parse_screaming_frog.py` — parser overview/images/redirects CSV
- `scripts/audit/detect_issues.py` — 5 détecteurs (titles, descriptions, alt, duplicates, redirects/404)
- `scripts/report/generate_report.py` — score /100 pondéré + rapport Markdown horodaté
- `scripts/apply/update_meta.py` — mutation GraphQL, dry-run par défaut, logging SQLite

### Phase 2 — Application supervisée (tâches 16–29) ✅
- **16** `scripts/report/ice_matrix.py` — Matrice ICE pondérée GSC
- **17–21** `generate_suggestions.py` + `update_alt_text.py` — **26 méta + 17 alt texts poussés** sur Shopify
- **22** `scripts/apply/create_redirects.py` — import 301 bulk depuis CSV
- **23** `scripts/apply/add_schema.py` — JSON-LD schema.org/Product via metafield custom.json_ld
- **24** `scripts/apply/rollback.py` — CLI rollback SQLite (`--list`, `--revert-ids`, `--revert-since`)
- **25** `scripts/audit/detect_gsc_opportunities.py` — 3 zones ; **17 opportunités, +148 clics estimés**
- **26** `scripts/audit/analyze_longtail.py` — gap analysis mots-clés vs GSC + Shopify
- **27** `scripts/report/generate_delta_report.py` — **score 56.3 → 83.9 (+27.6 pts), 62/68 issues résolues**
- **28** `.github/workflows/weekly_audit.yml` — pipeline CI complet, 6 secrets GitHub
- **29** `scripts/report/send_alerts.py` — alertes email CWV + positions + CTR, SMTP Gmail

### Phase 3 — Contenu SEO & Intelligence niche (tâches 30–39) ✅
- **30** `scripts/report/generate_blog_briefs.py` — 10 briefs H1/H2/E-E-A-T par requête cible
- **31** `scripts/apply/rewrite_descriptions.py` — 18 descriptions longue traîne, classification title-priority
- **32** `scripts/report/detect_internal_links.py` — 120 opportunités, 5 pages orphelines
- **33** `scripts/report/analyze_semantics.py` — scoring 4 dimensions vs benchmark Miacara/Zooplus
- **34** `scripts/report/generate_faq.py` — 21 Q/R × 5 catégories, JSON-LD FAQPage
- **35** `scripts/audit/detect_cannibalization.py` — query×page GSC, score sévérité 0–1, canonical/consolidation
- **36** `scripts/report/score_eeat.py` — 4 dimensions (Exp 20%, Expert 30%, Auth 25%, Trust 25%)
- **37** `scripts/report/generate_hreflang.py` — Liquid snippet + sitemap XML, fr-FR/fr-BE/fr-CH/x-default
- **38** `scripts/report/generate_monthly_report.py` — rapport HTML print-ready (Ctrl+P → PDF)
- **39** `scripts/report/dashboard.py` — dashboard `rich` snapshot + `--watch` 30s

### Données réelles
- **50 URLs GSC** · 90 jours · 245 clics · 3 736 impressions · position moyenne 6.0
- **69 changements** loggés dans `data/history.db`
- **Score SEO avant : 56.3 → après : 83.9 (+27.6 pts)**
- **Pipeline CI GitHub Actions** validé : tests + audit + tous les rapports Phase 3

### Phase 4 — Productisation (tâches 40–42) ✅
- **40** `config/tenants/leoniedelacroix.yaml` + `scripts/_config.py` — abstraction multi-tenant complète
  - Pydantic v1 `TenantConfig` : base_url, brand, categories, product_categories, hreflang_locales, seo_rules, alert_thresholds
  - 16 scripts migrés : domaine, brand, thresholds SEO → tous via `get_config(tenant_id)`
  - Option `--tenant` ajoutée à tous les CLI
  - 319 tests verts · ruff clean
- **41** `scripts/setup.py` — wizard CLI `init` / `list` / `check`
  - Renommage niche `petfood_fr` → `pet_accessories_fr` (plus fidèle au business)
  - `init` : wizard interactif → génère `config/tenants/<id>.yaml` + met à jour `.env`
  - `list` : tableau de tous les tenants avec marqueur tenant actif
  - `check` : validation config + secrets `.env` requis
  - 342 tests verts · ruff clean
- **42** `NicheConfig` + 4 YAML niches + migration 4 scripts
  - `scripts/_config.py` : modèles `NicheSignals`, `NicheEeatDimensions`, `NicheBlogTemplate`, `NicheConfig` + `load_niche()` lru_cache
  - `config/niches/pet_accessories_fr.yaml` : signals premium/eeat/longtail/category, dimensions EEAT, 21 FAQ Q/R, 5 blog templates
  - 3 nouveaux secteurs : `cosmetics_fr.yaml`, `mode_fr.yaml`, `jardinage_fr.yaml`
  - 4 scripts migrés : `analyze_semantics.py`, `score_eeat.py`, `generate_faq.py`, `generate_blog_briefs.py`
  - `tests/test_niche_config.py` : 23 nouveaux tests
  - **365 tests verts** · ruff clean

## ⏳ À faire — Phase 4 (tâche 44)

| # | Tâche | Priorité |
|---|---|---|
| 44 | Packaging PyPI ou Docker — installation en une commande | Moyenne |

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

### Session 2026-05-08 (Tâche 43 — licences API key)
- `scripts/license.py` : `issue_key`, `decode_key`, `validate_key`, `require_valid_license` + CLI `issue`/`check`
- Clé signée HMAC-SHA256, format `LEO-<base64(tenant_id+expiry+sig)>`, sans dépendance externe
- Intégration dans `crawl_shopify.py`, `update_meta.py`, `generate_report.py` — check non-bloquant si clé absente
- `scripts/setup.py cmd check` affiche désormais le statut de licence
- `.env.example` mis à jour avec `LICENSE_SECRET` et `LEONIE_API_KEY`
- `tests/test_license.py` : 24 tests
- **389/389 tests verts** · ruff clean

### Session 2026-05-08 (Tâche 42 — bibliothèque niches)
- `scripts/_config.py` : modèles Pydantic `NicheConfig` + `load_niche()` lru_cache + `reset_config_cache()` étendu aux deux caches
- `config/niches/pet_accessories_fr.yaml` : signals (premium × 43, eeat × 23, longtail × 30, category × 5), EEAT dimensions × 4, 21 FAQ Q/R, 5 blog templates
- 3 nouveaux secteurs : `cosmetics_fr.yaml`, `mode_fr.yaml`, `jardinage_fr.yaml`
- 4 scripts migrés (constantes Python → YAML) : `analyze_semantics.py`, `score_eeat.py`, `generate_faq.py`, `generate_blog_briefs.py`
- `tests/test_niche_config.py` : 23 tests
- **365/365 tests verts** · ruff clean

### Session 2026-05-08 (Tâche 40 — multi-tenant)
- `scripts/_config.py` : TenantConfig Pydantic v1, lru_cache, `get_config(tenant_id)`
- `config/tenants/leoniedelacroix.yaml` : YAML complet (brand, product_categories, hreflang, seo_rules, alert_thresholds)
- Migration complète des 16 scripts : `--tenant` CLI sur tous, domaine/brand/thresholds depuis config
- Fix `seo_rules.title_min_chars = 50` (était 30) pour matcher les contraintes generate_suggestions
- **319/319 tests verts** · ruff clean

### Session 2026-05-08 (Phase 2 tâche 29 + Phase 3 complète)
- Fix pipeline CI GitHub Actions (requirements.txt, ruff PATH, pagespeed timeout, permissions)
- Tâche 29 : send_alerts.py (15 tests)
- Tâches 30–39 : Phase 3 complète — 156 nouveaux tests
- **303/303 tests verts** · ruff clean · toutes les tâches Phase 3 commitées et poussées

### Session 2026-05-06 (Phase 2 tâches 25–28)
- Tâche 25 : detect_gsc_opportunities.py (20 tests)
- Tâche 26 : analyze_longtail.py (15 tests)
- Tâche 27 : generate_delta_report.py (11 tests)
- Tâche 28 : weekly_audit.yml pipeline complet

### Session 2026-05-05 → 2026-05-06 (Phase 2 tâches 16–24)
- CLAUDE.md réorganisé
- Tâches 16, 22, 23, 24 (37 tests)

### Session 2026-05-05 (Phase 1 + tâches 17–21)
- Phase 1 complète : 14 fichiers, 49 tests
- 26 méta + 17 alt texts poussés sur Shopify
- GSC connecté : 50 URLs · 3 736 impressions

### Sessions précédentes
- 2026-04-28 : Setup Google Cloud OAuth
- 2026-04-22 : Custom App Shopify
- 2026-04-20 : Initialisation projet
