# ARCHIVE — AUDIT INFRA HISTORIQUE

> Rapport d'audit conservé pour traçabilité. Les règles actives Codex sont dans `AGENTS.md`.

# AUDIT INFRA — Lot 3 du grand audit (2026-05-12)

> Audit infrastructure : `scripts/` (8 103 lignes), `shopify-app/` (1 234 LOC Remix + Liquid), `tests/` (11 487 lignes), `frontend/` (vérif décommission), `config/` (14 YAML).
> 3 agents `general-purpose` parallèles. **Lecture seule, aucune modification.**

---

## TL;DR

1. **`scripts/` n'est pas du legacy à supprimer** — c'est l'implémentation du moteur SEO que `app/` enveloppe. **35 fichiers, 17 ✅ canon, 12 🟡 mode CLI à garder pour agences, 2 ❌ vraiment désalignés** (`apply/rewrite_descriptions.py`, `apply/generate_suggestions.py`). Cependant : 10 endroits contiennent du **hardcoded business "Léonie/petfood"** dont 1 fuite d'email perso (`send_alerts.py:216` → `adrien.leredde@outlook.com`).
2. **`shopify-app/` est solide mais incomplet** — Remix 2.9 + Polaris + App Bridge v4 + GDPR webhooks ✅, mais **2 bloqueurs App Store** (CSP frame-ancestors absent, application_url = tunnel temporaire) et **surface UI minimale** (4 routes : dashboard/jobs/billing/webhooks — aucune UI pour review LLM, niche, onboarding, settings, privacy).
3. **`tests/` est large mais sous-couvert sur le multi-tenant** — 88 fichiers, 960 tests, structure miroir propre. Mais 5 fichiers `test_api/` hardcodent `287c4a-bb.myshopify.com` et **aucun test cross-shop** sur les endpoints critiques → un bug d'isolation passerait inaperçu.
4. **`frontend/` est suppressible** — mais il reste **un seul bloqueur** : le `Dockerfile` (stage `frontend-build`).
5. **`config/`** : 100% cohérent inter-fichiers pour niches et prompts. **Mais `TenantConfig` manque `ga4_property_id`, `gsc_property`, `locale`** → impossible d'avoir 2 boutiques avec 2 GA4 properties (confirme la fuite mono-tenant Lot 2).
6. **Important : corrections au Lot 2** — les modules `app/api/plans.py`, `app/niche/intent.py`, `app/niche/signals/*` que j'avais marqués comme "code mort" sont **en réalité utilisés**. Voir section dédiée plus bas.

---

## 1. `scripts/` (CLI legacy — toujours moteur SEO)

### Verdict global

**35 fichiers / ~8 103 LOC.** Reste cœur du moteur SEO. Réutilisé par :
- `app/api/audit.py` → importe `detect_issues.py` et `calculate_score`
- `app/api/apply.py` → importe `update_product_seo` et `ShopifyUserError` depuis `scripts/apply/update_meta.py`
- `app/api/plans.py` → utilise `scripts/license.py`
- `.github/workflows/weekly_audit.yml` (CI hebdo)

**Problème structurel** : `app/api/apply.py` dépend de `scripts/apply/update_meta.py`. Sens de dépendance inversé — `app/` doit être autonome.

### Modules à conserver tels quels

`_config.py`, `_paths.py`, `models.py`, `cli.py`, `setup.py`, toute `audit/` (sauf `crawl_shopify.py` à découpler du license check), `generate_report.py`, `generate_delta_report.py`, `ice_matrix.py`, `generate_faq.py`.

### Modules à décommissionner / refactor

| Fichier | Problème | Action |
|---|---|---|
| `apply/rewrite_descriptions.py` (310 LOC) | 🔴 5 templates avec "Léonie Delacroix", catégories chien/chat/fontaine en dur (L28-152) | **Décommissionner Phase 7** : remplacer par `app/llm/briefs.py` |
| `apply/generate_suggestions.py` (375 LOC) | 🔴 `_ENGLISH_SIGNALS` + inférence `chien/chat` hardcodés (L15-37, L48-53) | **Décommissionner Phase 7** : remplacer par `app/llm/` |
| `apply/update_meta.py` (305 LOC) | 🗑️ Doublon `app/apply/shopify_writer.py`. Couplage `app/api/apply.py` à casser | Refactor : migrer vers `app/apply/` uniquement |
| `apply/update_alt_text.py` (193 LOC) | 🗑️ Idem | Refactor |
| `apply/add_schema.py` (273 LOC) | 🟡 Doublon `app/jsonld/builders.py` + Theme App Extension | Arbitrer après tâche 69 publiée |
| `report/detect_internal_links.py` (330 LOC) | 🔴 Handles produits `le-pardessus-pour-chien`, `labreuvoir`, `griffoir-dimitrios` codés en dur (L63-101) | Refactor : lire depuis `config/tenants/<id>.yaml` |
| `report/generate_blog_briefs.py` (244 LOC) | 🔴 `_CATEGORY_TO_URLS` hardcode handles leoniedelacroix (L22-49) | Refactor : externaliser vers tenant YAML |
| `report/generate_monthly_report.py` (306 LOC) | 🔴 L138 "niche petfood FR" hardcodé (viole renommage tâche 41) | Refactor (retirer "petfood FR") |
| `report/score_eeat.py` (245 LOC) | 🔴 L119 "Référence marché premium petfood FR : ~55–65%" hardcodé. L182-185 recommandations pet-specific | Refactor (benchmarks vers niche YAML) |
| `report/analyze_semantics.py` (208 LOC) | 🔴 L112 "Benchmark concurrent : Miacara ~65%, Zooplus ~55%, Wanimo ~50%" hardcodé | Refactor (benchmarks → niche YAML) |
| **`report/send_alerts.py` (226 LOC)** | 🔴 **L216 `fallback email = "adrien.leredde@outlook.com"` — donnée perso hardcodée publiée dans le repo** | **À retirer impérativement** |
| `license.py` (206 LOC) | 🟡 `_DEFAULT_SECRET = "leonie-seo-v1"` (secret publié, exploitable si déployé sans `LICENSE_SECRET`). Bloque même usage CLI local. Viole règle 12 (Shopify Billing API canon) | Découpler du moteur : conditionner par `SELF_HOSTED_MODE` |

### Bugs récurrents

- **12 occurrences `datetime.utcnow()` deprecated** (Python 3.12+) : `crawl_shopify`, `detect_cannibalization`, `dashboard`, `generate_monthly_report`, `analyze_semantics`, `generate_hreflang`, `generate_faq`, `score_eeat`, `generate_blog_briefs`, `detect_internal_links`, `send_alerts`. **Incohérent** avec `app/` qui utilise déjà `datetime.now(UTC)`.
- **7 modules ouvrent SQLite directement** (`update_meta`, `update_alt_text`, `add_schema`, `rewrite_descriptions`, `create_redirects`, `rollback`, via `app.db.init_db`) → race conditions Phase 6 queue, pas de pool, pas d'isolation tenant.
- `setup.py:48` : `except Exception: pass` masque erreurs YAML invalides.
- `crawl_shopify.py:165` : import `app.db` depuis `scripts/` → viole Clean Architecture.
- `generate_delta_report.py:26` : `_RULES_PATH = "config/seo_rules.yaml"` relatif au CWD au lieu de `scripts/_paths.SEO_RULES_PATH` → casse hors racine projet.
- `.github/workflows/weekly_audit.yml` L78-85 : URLs `https://www.leoniedelacroix.com/...` codées en dur dans le CI.

---

## 2. `shopify-app/` (Remix scaffold)

### Stack
- Remix 2.9 + Polaris 13.9 + App Bridge React 4.1 + `shopifyApp()` v3.3 + PostgreSQLSessionStorage
- 6 routes Remix utiles, 3 Liquid blocks Theme App Extension
- ~1 234 LOC total (hors `node_modules`)

### App Store readiness

| Exigence | Présence | Détails |
|---|---|---|
| App Bridge v4 | ✅ | `<AppProvider isEmbeddedApp apiKey={apiKey}>` + NavMenu |
| Polaris | ✅ | Page/Card/IndexTable/BlockStack utilisés |
| OAuth Shopify | ✅ | `authPathPrefix="/auth"`, `unstable_newEmbeddedAuthStrategy=true` (token exchange) |
| Sessions multi-tenant | ✅ | `PostgreSQLSessionStorage` + fallback in-memory dev |
| GDPR webhooks (3) | ✅ | Déclarés ET forwardés au Python qui re-vérifie HMAC |
| `app/uninstalled` | ✅ | Forwardé au Python |
| Billing API | 🟡 | Route Remix présente, toute logique côté Python |
| Auth interne `X-Internal-Secret` | ✅ | `api.server.ts` injecte les headers |
| Theme App Extension JSON-LD | ✅ | 3 blocks (Product/Collection/Org) target `head`, filtres `\| json` sécurisés |
| `AppDistribution.AppStore` | ✅ | Explicite |
| Routes UI | 🟡 | 4 routes : dashboard/jobs/billing/webhooks. **Manque : review LLM, niche, onboarding, settings, help, privacy/export marchand** |
| Tests / lint / CI | 🔴 | Aucun test, pas d'ESLint, pas de CI Node |
| i18n | 🔴 | UI 100% FR hardcodé (brief annonce FR+EN) |

### 🔴 Bloqueurs App Store

1. **`entry.server.tsx` n'appelle pas `addDocumentResponseHeaders`** → manque CSP `frame-ancestors` requis pour embedded apps. **Bloquant App Store.**
2. **`application_url` = `willow-bag-discuss-grid.trycloudflare.com`** (tunnel temporaire dans `shopify.app.toml`) — à remplacer par un domaine prod stable.

### ⚠️ Gaps secondaires

- `vite.config.ts` ET `vite.config.js` cohabitent → nettoyer.
- `app.billing.tsx` : `catch {}` silencieux sur erreur subscribe → marchand ne saura jamais.
- `InlineGrid columns={... as "3"}` : cast forcé qui casse si nombre de plans varie.
- `SHOPIFY_API_KEY` (client_id) committé dans `.env.example` et `shopify.app.toml` — à valider avant soumission.
- `shopify.server.ts:14` : cast `as unknown` / `as any` autour de `PostgreSQLSessionStorage` (skew peer-deps shopify-api v11/v12).

---

## 3. `tests/` (suite Python — 88 fichiers, 11 487 lignes)

### Verdict global

**Suite large et bien structurée**. Structure miroir `tests/<module>/` cohérente. Couverture quasi-complète sur les modules critiques App Store (OAuth ✅, GDPR ✅, Billing ✅, LLM router/review ✅, jobs worker ✅, niche engine ✅).

### 🔴 Faiblesse multi-tenant majeure

- `287c4a-bb.myshopify.com` hardcodé dans **5 fichiers** `test_api/` (`test_apply.py`, `test_audit.py`, `test_plans.py`, `test_shops.py`, `test_impact/test_calculator.py`).
- **Aucun test endpoint ne fait varier le shop.** Un bug d'isolation cross-shop dans `get_shop_context` passerait inaperçu.
- **Recommandation** : paramétrer SHOP via fixture, ajouter au moins un test cross-shop par endpoint critique (`/apply`, `/billing`, `/jobs`, `/niche`).

### 🔴 Mocking trop systématique

Pattern dominant : `mocker.patch("app.api.deps.get_token", return_value=None)` court-circuite **systématiquement** le store de tokens chiffrés. **Aucun test bout-en-bout** `install → save_token (Fernet) → get_token → call endpoint`. Risque modéré qu'un bug dans la chaîne complète ne soit pas détecté.

### Modules sans test ou faibles

- `app/observability/costs.py` : non testé
- `app/observability/logging.py` : non testé
- `app/embeddings/encoder.py` : non testé (seul `store.py` testé)
- `app/niche/engine.py` : orchestrateur non testé directement
- `app/apply/shopify_writer.py` : testé seulement à travers les scripts legacy
- 10 routers API sans test direct : `embeddings`, `ga4`, `generate`, `impact`, `jsonld`, `multilingual`, `niche`, `observability`, `suggestions`, `web_graph`
- `tests/test_ga4/test_ga4.py` (272 LOC) regroupe client + funnel + queries → à splitter en 3

### Tests à étoffer (LOC trop faibles)

- `tests/test_oauth/test_hmac_validator.py` (36 LOC)
- `tests/audit/test_fetch_gsc.py` (37 LOC)
- `tests/audit/test_fetch_pagespeed.py` (33 LOC)
- `tests/apply/test_update_alt_text.py` (54 LOC)

### Tests redondants

- `tests/report/test_generate_blog_briefs.py` (177 LOC) vs `tests/test_llm/test_briefs.py` (269 LOC) — angles légitimes différents (rendu Markdown vs génération LLM) mais à clarifier dans les noms.

---

## 4. `frontend/` (décommission)

### Inventaire

- **Poids total : 145 Mo** (dont 144 Mo `node_modules/` non commités)
- Aucun `.env*` dans le dossier (vérifié) — pas de risque secret
- `dist/` ignoré par `.gitignore` — pas dans git

### Imports vivants

| Source | Résultat |
|---|---|
| `app/**/*.py` | 2 hits dans `app/api/suggestions.py` — **commentaires/docstrings seulement** |
| `app/main.py:125` | 1 hit — **commentaire de décommission** (aucun `StaticFiles.mount`) |
| `shopify-app/**` | 0 hit |
| `scripts/**` | 0 hit |
| `tests/**` | 0 hit — **aucun test ne dépend de `frontend/dist/`** |
| `.github/workflows/` | 0 hit |
| **`Dockerfile`** | **3 hits actifs** — stage `frontend-build` (lignes 1-7, 23) — **seul blocker à la suppression** |

### Verdict

**Suppressible** après nettoyage du `Dockerfile` (retirer le stage `frontend-build` et la ligne `COPY --from=frontend-build`). Sans ça, `docker build` cassera.

---

## 5. `config/` (14 YAML)

### Cohérence des schémas

| Catégorie | Cohérence | Détails |
|---|---|---|
| **Niches** (4 fichiers) | ✅ 100% | Tous ont `niche_id`, `label`, `language`, `market`, `signals`, `eeat_dimensions`, `faq_templates`, `blog_templates` |
| **Prompts** (7 fichiers) | ✅ 100% | Tous ont `version`, `system`, `user`, `max_tokens`, `temperature` |
| **Tenant** (1 fichier) | n/a | Voir gap multi-tenant ci-dessous |
| Globaux (2 fichiers) | 🟡 | `keywords.yaml` et `seo_rules.yaml` mal classés |

### 🔴 Gap multi-tenant critique

`TenantConfig` (Pydantic, `scripts/_config.py:55-83`) couvre `tenant_id`, `name`, `brand`, `niche`, `base_url`, `shopify_store_domain`, etc. **Mais manque** :
- `locale` (langue principale)
- `ga4_property_id` (analytics — actuellement env var globale)
- `gsc_property` / `gsc_site_url` (idem)
- `currency`

**Conséquence** : confirme le bloquant du Lot 2 — impossible d'avoir 2 boutiques avec 2 GA4 properties.

### Qualité du contenu des niches

| Niche | Statut | Détails |
|---|---|---|
| `pet_accessories_fr.yaml` | ✅ Production | 19 Ko, 43 premium / 23 eeat / 31 longtail, 5 sous-catégories, 5 FAQ, 5 blogs |
| `cosmetics_fr.yaml` | 🟡 Squelette | 4 Ko, **1 FAQ / 2 blogs** seulement |
| `mode_fr.yaml` | 🟡 Squelette | 4 Ko, idem |
| `jardinage_fr.yaml` | 🟡 Squelette | 4 Ko, idem |

**Risque produit** : si un marchand mode/cosmétique/jardinage installe l'app, la qualité Niche Intelligence sera très en-dessous de la promesse Léonie.

### YAML mal classés (à arbitrer)

- `config/keywords.yaml` (catalogue Léonie chien/chat) chargé en chemin dur depuis **7 scripts** — mais **spécifique Léonie**, devrait être dans `config/tenants/leoniedelacroix.keywords.yaml`.
- `config/seo_rules.yaml` : doublon avec `tenant.seo_rules` bloc — clarifier la précédence (override tenant > global).

---

## 6. Corrections au Lot 2 (`AUDIT_CODE.md`)

L'agent du Lot 2 sur `api/` + `oauth/` avait flaggé `app/api/plans.py` comme "router jamais monté → code mort". **L'audit Lot 3 a vérifié les imports cross-modules et invalidé cette affirmation.**

### Modules incorrectement flaggés "code mort" dans le Lot 2

| Module | Affirmation Lot 2 | Réalité Lot 3 |
|---|---|---|
| `app/api/plans.py` (77 LOC) | "Jamais monté dans main.py → code mort" | ❌ FAUX. Ce n'est pas un router à monter mais des **helpers** (`get_features`, `get_active_plan`, `plan_summary`, `PlanFeatures`) importés par `deps.py`, `shops.py`, `billing/router.py`. **À garder.** |
| `app/niche/intent.py` (360 LOC) | "Non importé par engine.py → zombie" | ❌ FAUX. Câblé via `app/api/niche.py:147` (`/api/shops/{shop}/niche/intent-clusters`) + importé par `app/llm/briefs.py:11`. **À garder.** |
| `app/niche/signals/*` (~390 LOC) | "Non câblés dans engine.py" | ❌ PARTIELLEMENT FAUX. Câblés via `app/api/niche.py:181` (`/api/shops/{shop}/niche/signals` POST). **À garder.** Critique de fond reste valable : `engine.py` orchestrateur ne les agrège pas dans `NicheReport`. |

### Conséquence

Le Lot 4 Vague 4 (cleanup code mort) est **plus light que prévu** :
- Pas de suppression de `app/api/plans.py`
- Pas de suppression de `niche/intent.py` ni `niche/signals/*`
- Reste : suppression de `frontend/` (après Dockerfile), refactor `engine.py` pour agréger les modules niche au lieu de les supprimer.

---

## 7. Vue consolidée Lot 1 + Lot 2 + Lot 3 → Plan Lot 4 révisé

### Bilan des 3 lots d'audit

| Lot | Périmètre | Findings clés |
|---|---|---|
| **1 — Docs** | 14 .md | 11 dérives (3 critiques corrigées au commit `cf2cf74`) |
| **2 — Code `app/`** | 12 654 LOC / 40 fichiers | 17 bugs bloquants (multi-tenant, billing bypass, brand-lock, E5 prefix), 30+ secondaires |
| **3 — Infra** | 8 103 + 1 234 + 11 487 + frontend + config | 10 hardcoded business `scripts/`, 2 bloqueurs Shopify Remix, fuite email perso, gap GA4 multi-tenant, 3/4 niches squelettiques |

### Nouveau plan Lot 4 (révisé après Lot 3)

#### Vague 1 — Bloquants App Store (critique, à faire avant tâche 75)

1. **Schéma DB multi-tenant** : ajouter `shop` à `seo_changes` + `snapshots` + migration (Lot 2)
2. **Auth manquantes** : `GET /api/shops`, `POST /api/jobs/*` (Lot 2)
3. **Bypass billing** : `/billing/confirm` doit vérifier HMAC + `charge_id` + re-query Shopify (Lot 2)
4. **CSP frame-ancestors** : appeler `addDocumentResponseHeaders` dans `entry.server.tsx` (Lot 3)
5. **`application_url`** : remplacer le tunnel cloudflare temporaire par un domaine prod (Lot 3)
6. **Privacy policy mensongère** : réécrire `api/privacy.py` + `api/help.py` (Lot 2)
7. **Cache LLM cross-tenant** : retirer `lru_cache(maxsize=1)` (Lot 2)
8. **Brand-lock** : externaliser `_BRAND_WORDS`, brand string, vocab NER, subreddits vers `config/tenants/<shop>.yaml` + `config/niches/<sector>.yaml` (Lot 2 + Lot 3 sur 10 endroits scripts/)
9. **`TenantConfig`** : ajouter `locale`, `ga4_property_id`, `gsc_property`, `currency` (Lot 3)
10. **Email perso hardcodé** : retirer `adrien.leredde@outlook.com` de `scripts/report/send_alerts.py:216` (Lot 3)

#### Vague 2 — Bugs comportementaux

11. E5 prefix bug `encode_texts` (Lot 2)
12. Anti-hallucination LLM (Lot 2)
13. Cost tracking Cloudflare (Lot 2)
14. Jobs `shop` attribution (Lot 2)
15. **`niche/engine.py` orchestrateur** : agréger `intent.py`, `ner.py`, `signals/`, `brand_signals.py` dans `NicheReport` (Lot 2 corrigé Lot 3 — pas supprimer, câbler)
16. `bulk_orchestrator.py` `old_value=NULL` (Lot 2)
17. `api/niche.py` `except` tuple invalide (Lot 2)

#### Vague 3 — Hygiène code (règles `AGENTS.md` + deprecations)

18. 16 violations `except Exception:` (Lot 2) + 1 dans `setup.py:48` (Lot 3)
19. `asyncio.get_event_loop()` deprecated (Lot 2)
20. **12 occurrences `datetime.utcnow()` deprecated** dans `scripts/` (Lot 3)
21. Accès attributs privés (Lot 2)
22. Logs whitelist `extra=` (Lot 2)

#### Vague 4 — Cleanup

23. Suppression `frontend/` (après nettoyage Dockerfile) (Lot 3)
24. Décommissionnement `scripts/apply/rewrite_descriptions.py` + `generate_suggestions.py` (Lot 3)
25. Casser couplage `app/api/apply.py → scripts/apply/update_meta.py` (Lot 3)
26. Centraliser `_load_snapshot` dupliqué (Lot 2)
27. `scripts/license.py` : conditionner par `SELF_HOSTED_MODE` env flag (Lot 3)
28. Déplacer `config/keywords.yaml` dans tenant ou `config/defaults/` (Lot 3)
29. Splitter `tests/test_ga4/test_ga4.py` (Lot 3)
30. Combler tests manquants (Lot 3) : `costs.py`, `logging.py`, `encoder.py`, `engine.py`, routers API non testés
31. **Tests cross-shop** : ajouter au moins un test multi-tenant par endpoint critique (Lot 3)
32. **Test bout-en-bout token Fernet** : un test par groupe de routes qui passe par le vrai token store (Lot 3)

#### Vague 5 — Produit / contenu

33. Enrichir `cosmetics_fr.yaml`, `mode_fr.yaml`, `jardinage_fr.yaml` au niveau de `pet_accessories_fr.yaml` (ou marquer explicitement `status: template-demo`) (Lot 3)
34. Créer `config/niches/_TEMPLATE.yaml` officiel + JSON-Schema validation CI (Lot 3)
35. Étoffer surface UI Remix : review LLM, niche intelligence, onboarding, settings, privacy/export marchand, i18n FR+EN (Lot 3)

### Volumétrie

- **Vague 1 (10 items)** : 5-7 commits TDD atomiques, ~1.5j de travail focus
- **Vague 2 (7 items)** : 5-6 commits, ~1j
- **Vague 3 (5 items)** : 2-3 commits batch (ruff/lint-driven), ~0.5j
- **Vague 4 (10 items)** : 6-8 commits, ~1.5j
- **Vague 5 (3 items)** : 2-3 commits + contenu, ~1j

**Total** : **20-27 commits TDD**, ~5.5j de travail focus pour fermer toutes les vagues. La Vague 1 seule (~1.5j) suffit pour passer App Store review.

---

*Lot 3 terminé. 3 agents parallèles, 5 sous-arbres audités (~21 000 LOC + 14 YAML). Lot 2 partiellement corrigé. Aucune modification appliquée. Audit prêt pour le Lot 4 (corrections TDD).*
