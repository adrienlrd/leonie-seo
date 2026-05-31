# PROGRESS — SEO Leoniedelacroix.com

## État global
- Session 2026-05-31 : **Blog SEO+GEO Sprint 2 livré** — les brouillons blog réutilisent le maillage interne d'Analyse marché (`internal_links` éditables + bloc « À lire aussi » publié dans Shopify) et la page Crawlabilité IA fournit un template `robots.txt.liquid` manuel avec bouton copier. Validations : `ruff check` ciblé ✅, `pytest tests/test_blog tests/test_geo/test_crawlability.py tests/test_api/test_geo.py` **51 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅, `git diff --check` ✅.
- Dernière session : **2026-05-29** (Fiabilisation algo Analyse produit : pipeline « données réelles d'abord », pool de mots-clés GSC/DataForSEO/Suggest/Trends avant l'IA, mode JSON déterministe, transparence des sources en UI ; `pytest` 1583 ✅, typecheck/build ✅)
- Session 2026-05-25 (DataForSEO 5 APIs actives + migration infra prod planifiée Phase 12)
- Phase 1 : **15/15** ✅
- Phase 2 : **14/14** ✅
- Phase 3 : **10/10** ✅
- Phase 4 : **5/5** ✅
- Phase 5 : **5/6** ✅ (tâche 49 supersédée par la tâche 75)
- Phase 6 : **7/7** ✅ (terminée 2026-05-10)
- Phase 7 : **11/11** ✅ (terminée 2026-05-11)
- Phase 8 : **7/7** ✅ (tâches 69-75 terminées côté repo ; soumission publique différée après Phase 10)
- Phase 9 : **7/7** ✅ (pilote réel terminé ; pass avec lacunes de mesure)
- Phase 10 : **21/21** ✅ (tâches 83-103 clôturées le 2026-05-17)
- Phase 11 : **10/10** ✅ (GEO / Revenue-Aware Shopify intelligence, tâches 106-115)
- Phase 11.5 : **10/10** ✅ (GEO Impact Validation & Retention Loop, tâches 116-125)
- Phase 11.6 : **1/1** ✅ (GEO FAQ & Buying Guide Automation, tâche 126)
- Phase 11.7 : **12/12** ✅ (cadrage GEO Autopilot Simplification, tâches 127-138)
- Phase 11.8 : **11/11** ✅ (implémentation GEO Autopilot Simplification, tâches 139-149, terminée 2026-05-21)
- Phase 11.9 : **12/12** ✅ (Merchant Journey Unification & Friction Reduction, tâches 152-163 terminées le 2026-05-21)
- Phase 11.10 : **0/5** ⏳ (Market Analysis Improvements, tâches 164-168, parallèle aux tests marchands pilotes)
- Phase 12 : **0/5** ⏳ (go/no-go + soumission publique Shopify App Store + migration infra prod, tâches 150-151 + 169-171, démarre après test 3 marchands pilotes)
- **Audit post-Phase 8** : 4 livrables + corrections TDD le 2026-05-12 (Vagues 1 à 5)
- Tests : dernière validation complète tâches 155-163 — `npm run typecheck` ✅, `npm run build` ✅, `git diff --check` ✅.

## Phase 12 — tâches planifiées (à venir)

### Tâches App Store (existantes)
- **150** — Décision go/no-go Shopify App Store (après 3 tests marchands pilotes)
- **151** — Finaliser et soumettre l'app au Shopify App Store

### Tâches migration infra prod (nouvelles)
- **169** — Migrer le stockage JSON vers Supabase (PostgreSQL JSONB)
  Remplacer toutes les fonctions `save_*` / `load_*` dans `app/market_analysis/jobs.py` et équivalents par des requêtes Supabase. Zéro impact sur l'API publique.
- **170** — Déployer le backend FastAPI sur Railway (remplace Render)
  Adapter `Dockerfile` si nécessaire, configurer les variables d'env Railway, vérifier les endpoints.
- **171** — Déployer le frontend Remix sur Vercel (remplace Render)
  Configurer `vercel.json`, variables d'env Shopify, domaine custom si applicable.

**Prérequis tâche 169** : créer le projet Supabase, récupérer `SUPABASE_URL` + `SUPABASE_ANON_KEY`, ajouter `supabase-py` aux dépendances.
**Coût cible prod** : ~$5/mois infra (Vercel free + Railway Hobby $5 + Supabase free).

### Checklist déploiement (à exécuter au déploiement Phase 12)
- **Re-consent marchand OBLIGATOIRE (`read_themes` + `write_themes`)** : la feature « Fichiers IA » (agents.md / llms.txt / llms-full.txt) écrit désormais des **templates de thème** (`templates/*.liquid`) sur le thème publié — Shopify sert ces routes nativement depuis le thème depuis le [changelog du 28 mai 2026](https://shopify.dev/changelog/customize-llmstxt-llms-fulltxt-and-agentsmd) ; l'ancienne approche Files API + URL Redirect est **silencieusement ignorée**. Scopes ajoutés dans les 3 tomls + `render.yaml`. Au déploiement : `shopify app deploy` **puis réinstallation/re-consent** de chaque boutique pour accorder les nouveaux scopes. Tant que ce n'est pas fait, `POST /llms-txt/publish` renvoie **403** avec un message « réinstaller l'app ».
- **`shopify app deploy` requis** aussi pour activer les abonnements webhook catalogue (`products/create|update|delete`, `collections/update|delete`) qui déclenchent la régénération automatique (debounce 5 min). Ces topics ne deviennent actifs qu'après mise à jour du manifest Shopify.

---

## Phase 11.9 — Merchant Journey Unification & Friction Reduction le 2026-05-21

### Objectif

Rendre l'app Léonie SEO compréhensible par un marchand non expert en moins de 5 minutes, sans explication préalable. Tâches 155-163 : 8 documents canoniques + ajustements UX/i18n dans 5 routes Remix.

### Tâches terminées

- **155 Dashboard as Single Command Center** — Zone 1 CTA primary si niche non validée, badge niveau i18n, tooltip marchand, Zone 6 masquée, lien safe-apply avec highlight.
- **156 One Primary CTA per Screen** — Matrice CTA documentée + application dans 5 routes : niche-understanding (Analyser→secondary), safe-apply (Valider/Publier→primary, pas tone critique), priorities (Préparer→primary), impact (Voir prochaines→primary).
- **157 Merchant Language Pass** — 22 nouvelles clés i18n FR+EN + mise à jour de 12 clés existantes : Valider, Prévisualiser, Publier, Refuser, statuts marchands, types de contenu, message rétention, gain estimé.
- **158 Advanced Tools Hiding Strategy** — doc canonique listant 14 routes avancées, confirmation que nav principale est déjà correcte.
- **159 Action Detail Unification** — gain estimé (revenue_estimate_eur) affiché en Badge success sur app.priorities + CTA "Préparer cette action" → safe-apply par carte.
- **160 Safe Apply Narrative Simplification** — bannière de sécurité permanente, StatusBadge i18n, CONTENT_TYPE_I18N_KEYS, erreurs techniques traduites, boutons restructurés (primary: Valider/Publier, secondary: Prévisualiser, plain: Refuser).
- **161 Impact Feedback Loop UX** — Banner rétention en haut de page, section jalons déplacée avant les courbes techniques, bouton NBA "Voir prochaines actions" primary.
- **162 Pilot Merchant Test Script** — protocole 6 tâches, grille de friction 0-5, seuils de passage.
- **163 Phase 12 Entry Criteria Update** — §0 prérequis Phase 11.9 dans launch-readiness.md, section gate Phase 11.9 dans DECISIONS.md.

### Validations

- `npm run typecheck` ✅ (0 erreur TypeScript)
- `npm run build` ✅ (74 modules SSR)
- `git diff --check` ✅

### Prochaine tâche recommandée

- **Phase 11.10 (tâche 164)** : filtrage et tri des résultats Analyse marché — première amélioration client-side, sans impact backend.
- **Phase 12 (tâches 150-151)** : planifier les 3 sessions test utilisateur marchands pilotes (`docs/pilot-merchant-test-script.md`). Dès les 5 critères atteints → tâche 150 décision go/no-go App Store.

## Phase 11.8 — Implémentation GEO Autopilot Simplification le 2026-05-20

### Objectif

Transformer le cadrage Phase 11.7 en fonctionnalités produit testées avant le go/no-go Shopify App Store.

### Décisions

- Phase 11.7 reste la phase de cadrage/documentation.
- Phase 11.8 devient la phase d'implémentation applicative bloquante avant Phase 12.
- Les tâches 139-149 couvrent les verticales runtime : Product Scope, Crawl L3, Niche Understanding, Readiness Audit, Opportunity Finder, Priority Engine, AI Content Actions, Safe Apply, Impact Tracker, Dashboard et Launch Readiness Evidence.
- Phase 12 est renumérotée en tâches 150-151.

### Prochaine tâche recommandée

- **149 — Launch Readiness Evidence Pass** : exécuter la checklist §3.1-§3.13, documenter le verdict dans `DECISIONS.md`.

## Tâche 149 — Launch Readiness Evidence Pass le 2026-05-21

### Objectif

Exécuter mécaniquement la checklist `docs/launch-readiness.md` §3.1 → §3.13 (13 catégories, ~50 critères), corriger les gaps identifiés et documenter la décision go/no-go dans `DECISIONS.md`.

### Réalisations

**Audit des 13 catégories §3 :**
- §3.1 Compréhension marchand : 4/5 ✅ (1 critère ⏳ : test utilisateur 3 marchands — exige validation humaine)
- §3.2 3 actions prioritaires : 5/5 ✅ (après fix `LEONIE_LLM_LOW_COST_ONLY`)
- §3.3 IA assistante : 5/5 ✅
- §3.4 Mesure d'impact : 7/7 ✅
- §3.5 Scope produit V1 : 4/4 ✅
- §3.6 Sans Screaming Frog : 5/5 ✅ (après correction CrawlCard.tsx)
- §3.7 Pas de promesse non prouvée : 4/4 ✅
- §3.8 Google/IA séparés : 3/3 ✅
- §3.9 Coût LLM maîtrisé : 10/10 ✅ (après fix `LEONIE_LLM_LOW_COST_ONLY`)
- §3.10 Rollback opérationnel : 4/4 ✅ (après fix TTL 90 jours)
- §3.11 Dry-run par défaut : 5/5 ✅
- §3.12 Dashboard impact lisible : 3/4 ✅ (1 critère ⏳ : test utilisateur)
- §3.13 Niche gating : 4/4 ✅

**Corrections intégrées (3 bugs réels trouvés) :**
1. `app/content_actions/runner.py` — ajout `_effective_tier()` avec `LEONIE_LLM_LOW_COST_ONLY` env var override
2. `app/api/rollback.py` — TTL 90 jours : `confirm_stale_revert` field, 409 sur revert stale, `stale_warning` en dry-run, `applied_at` ajouté à la SELECT query
3. `shopify-app/app/components/onboarding/CrawlCard.tsx` — "obligatoire" → "optionnel — mode avancé", description mise à jour, `required` retiré de l'input
4. `shopify-app/app/components/onboarding/InstallationChecklistCard.tsx` — libellé SF mis à jour

**Tests ajoutés :**
- `tests/test_content_actions/test_runner.py` — 3 tests `_effective_tier` (low-cost env, déterministe préservé, normal sans env)
- `tests/test_api/test_rollback.py` — 1 test TTL stale (dry-run + stale_warning, 409 sans confirm_stale, reverted avec confirm_stale)

**Décision dans `DECISIONS.md` :** NO-GO Phase 12 à ce jour — bloquant unique : test utilisateur 3 marchands pilotes (§3.1 + §3.12).

### Validations

- `ruff check .` ✅
- `pytest` **1520 passed** ✅ (+4 nouveaux)
- `npm run typecheck` ✅ (0 erreur TypeScript)

### Prochaine tâche recommandée

- **Phase 12** : Planifier les 3 sessions test utilisateur marchand (compréhension < 5 min + dashboard impact lisible). Dès validation humaine OK → tâche 150 go/no-go final.

## Roadmap — Ajout Phase 11.9 le 2026-05-21

### Note

Ajout documentaire de la **Phase 11.9 — Merchant Journey Unification & Friction Reduction** dans `ROADMAP.md`, avec les tâches 152-163 en attente. La Phase 12 démarre désormais seulement après validation de la Phase 11.9 et tests marchands pilotes.

## Tâche 152 — First-Run Journey Map le 2026-05-21

### Objectif

Transformer le cadrage Phase 11.9 en premier incrément concret : documenter le parcours marchand de première connexion jusqu'à la première action appliquée, puis retirer un détail technique visible du chemin standard.

### Réalisations

- `docs/first-run-merchant-journey.md` — parcours linéaire Connecter → Comprendre → Valider → Analyser → Proposer → Appliquer → Mesurer, avec écran attendu, CTA principal, état vide, état erreur et critère de passage par étape.
- `shopify-app/app/routes/app.niche-understanding.tsx` — le JSON brut de "Ce que l'IA a compris" passe derrière un bloc **Mode avancé** replié par défaut.
- `ROADMAP.md` — tâche 152 marquée terminée et liée au document canonique.

### Validations

- `npm run typecheck` ✅
- `npm run build` ✅
- `git diff --check` ✅

## Tâche 153 — Niche Understanding as Mandatory Gate le 2026-05-21

### Objectif

Faire de la compréhension IA validée un prérequis visible avant les recommandations principales, tout en gardant les réglages, la mesure et le mode avancé accessibles.

### Réalisations

- `docs/niche-understanding-gate.md` — règle produit canonique : statut bloquant, surfaces bloquées, surfaces accessibles, briques existantes, garde-fous et critères de validation.
- `shopify-app/app/routes/app._index.tsx` — la zone "Vos 3 actions prioritaires" affiche un CTA de validation si `zone1.niche_validated` est faux.
- `shopify-app/app/routes/app.priorities.tsx` — la page Top 3 Actions vérifie `/niche/hypothesis` avant de charger les priorités ; si non validé, elle affiche une gate vers `Compréhension boutique`.
- `shopify-app/app/lib/i18n.ts` — textes FR/EN pour le gate marchand.
- `ROADMAP.md` — tâche 153 marquée terminée et liée au document canonique.

### Validations

- `npm run typecheck` ✅
- `npm run build` ✅
- `git diff --check` ✅

## Tâche 154 — Unified Onboarding Flow le 2026-05-21

### Objectif

Réduire l'onboarding visible à 4 étapes maximum : connecter Google, lancer l'analyse IA, valider la compréhension IA, voir les 3 actions prioritaires.

### Réalisations

- `docs/unified-onboarding-flow.md` — séquence onboarding cible, règles d'écran, critères de fin d'étape, briques réutilisées et garde-fous.
- `shopify-app/app/routes/app.onboarding.tsx` — ajout d'un parcours guidé "Démarrer en 4 étapes" avec un seul prochain CTA actif.
- `shopify-app/app/routes/app.onboarding.tsx` — ajout de l'action `niche_understand` pour lancer `/api/shops/{shop}/niche/understand` depuis l'onboarding.
- `shopify-app/app/routes/app.onboarding.tsx` — l'ancienne checklist complète, PageSpeed, crawl, GSC détaillé et jobs passent derrière **Outils avancés**.
- `ROADMAP.md` — tâche 154 marquée terminée et liée au document canonique.

### Validations prévues

- `npm run typecheck` ✅
- `npm run build` ✅
- `git diff --check` ✅

## Tâche 145 — AI Content Actions Runtime le 2026-05-20

### Objectif

Créer l'orchestrateur unifié de génération de contenu LLM : remplace 7 générateurs disparates par un pipeline unique (schema Pydantic → bundle → LLM tier routing → generate → audit guardrails → persist → review).

### Réalisations

- `app/content_actions/__init__.py` — module vide.
- `app/content_actions/schema.py` — ContentType (10 types), ContentStatus (7 états), ContentActionRequest, ContentActionResult, ResourceInput, ConfirmedFact, MissingFact, NicheContext, GscSignals, Constraints, PreviousContent, ContentOutput, ConstraintsCheck, QualityResult, LLMMeta.
- `app/content_actions/audit.py` — 6 vérifications : longueurs (META_TITLE 30-60, META_DESCRIPTION 120-160, ALT_TEXT 8-12 mots), forbidden_promises, do_not_say (case-insensitive), language detection, quality score (0.40×facts + 0.30×queries + 0.20×constraints + 0.10×brand_voice), labels (excellent/bon/à_compléter/incomplet).
- `app/content_actions/runner.py` — `run_content_action` : validation niche (FACTUAL_CONTENT_TYPES requièrent `validated_by_merchant`), budget check, jsonld_faqpage déterministe, routing LLM tier (low-cost/medium/deterministic), audit guardrails, persist SQLite. `retry_content_action` : recharge depuis DB, injecte feedback, limite 3 retries.
- `app/api/content_actions.py` — 4 routes : POST `/run`, GET `/{id}`, POST `/{id}/retry`, POST `/{id}/export`.
- `app/db.py` — table `content_actions` (action_id PK, shop, content_type, resource_id, resource_handle, result_json, status, retry_count, created_at, updated_at).
- Prompts migrés v1.0 → v2.0 : `meta_title`, `meta_description`, `product_description`, `alt_text`, `collection_brief`, `meta_multilingual`. Toutes les variables niche sont optionnelles (`{% if var is defined and var %}`) pour préserver la compatibilité ascendante avec `batch.py`, `briefs.py`, `multilingual.py`.
- Nouveaux prompts : `faq_product.yaml` (JSON array), `answer_block.yaml`, `buying_guide.yaml` (JSON object).
- `shopify-app/app/routes/app.content-actions.tsx` — UI Remix : Select type, résultat avec quality bar, banners violations, export.
- `shopify-app/app/lib/i18n.ts` — 12 clés content_actions FR/EN.
- `shopify-app/app/routes/app.audit-hub.tsx` — entrée contentActions ajoutée.
- `app/main.py` — router content_actions enregistré.
- `tests/test_content_actions/` — 26 tests (schema, audit, runner). `tests/test_api/test_content_actions.py` — 6 tests API.

### Validations

- `ruff check .` ✅
- `pytest` : **1470 passed** ✅
- `npm run typecheck` ✅
- `npm run build` ✅

---

## Tâche 143 — Opportunity Finder Runtime le 2026-05-20

### Objectif

Agréger les signaux existants (GSC, keyword gaps, intent clusters, audit readiness, cannibalization, competitors) en une liste ordonnée d'opportunités par produit actif — sans LLM, sans nouveau détecteur.

### Réalisations

- `app/opportunities/__init__.py` — module vide.
- `app/opportunities/finder.py` — orchestrateur 7 signaux déterministes : `_gsc_signal_for_product` (classify_url → 1.0/0.7/0.5/0.0), `_keyword_gap_for_product` (cross-ref ProductCluster → KeywordGap), `_audit_pressure` ((100-readiness)/100), `_intent_match_boost` (token overlap + niche_hypothesis → 0.5/1.0), `_cannibalization_for_product` (detect_duplicate_content), `_competitor_pressure` (build_competitor_monitor), `_apply_niche_adjustments` (priority_products +10pts, forbidden_promise alert-only). Formule pondérée (0.30/0.20/0.15/0.10/0.10/0.10/0.05), `_tier` (≥70 high / ≥40 medium / <40 low), `_confidence` (≥3 signaux non-nuls → high).
- `app/api/opportunities.py` — `GET /api/shops/{shop}/opportunities?scope=active&top=20&intent=...`. Charge snapshot, niche hypothesis, crawl findings, GSC page-level (CSV) et query-level (JSON). Filtre par intent si fourni.
- `app/main.py` — router opportunities enregistré.
- `shopify-app/app/lib/i18n.ts` — 11 nouvelles clés FR/EN (opportunities, opportunityScore, tiers, primaryReason, matchedQueries, matchedIntents, opportunitiesEmpty/Total).
- `shopify-app/app/routes/app.opportunities.tsx` — page Remix : summary bar badges, Tabs intent, liste Cards avec ProgressBar, primary_reason, niche_alerts, matched_queries, recommended_actions.
- `shopify-app/app/routes/app.audit-hub.tsx` — entrée "Opportunity Finder" ajoutée en tête de hub.
- `tests/test_opportunities/test_finder.py` — 9 tests : schema, score 0-100, tier, scope, niche priority +10, forbidden alert, confidence, gsc zero, tri desc.
- `tests/test_api/test_opportunities.py` — 3 tests : schema, scope active, filtre intent.

## Tâche 142 — Unified Readiness Audit Runtime le 2026-05-20

### Objectif

Exposer le score AI Search Readiness unifié consommant les signaux produit, les findings Crawl L3 et l'hypothèse niche validée. Route canonique `/audit/readiness`, UI Remix `app.audit-readiness`, redirection 301 de `/geo/readiness`.

### Réalisations

- `app/geo/readiness.py` — score 4 niveaux (`excellent/bon/partiel/faible`), nouveaux champs `reasons[]`, `recommended_actions[]`, `niche_alerts[]`, intégration hypothèse niche (forbidden_promises → malus Trust, brand_voice.do_not_say → alerte, conversational_intents → delta Answerability), intégration Crawl L3 (page_404/server_error → malus SEO, redirect_chain → -10, missing_canonical → -5). Catalog expose `global_score`, `global_level`, `crawl_health`, `niche_alerts` agrégées.
- `app/api/audit.py` — endpoint `GET /api/shops/{shop}/audit/readiness` (scope, top, freshness warning, snapshot_age_days, generated_at).
- `app/api/geo.py` — `GET /api/shops/{shop}/geo/readiness` → 301 redirect vers `/audit/readiness`.
- `app/geo/prioritization.py` — compatible nouveau format `components[key]["score"]`.
- `shopify-app/app/routes/app.audit-readiness.tsx` — page Remix : score global badge, crawl health, niche alerts, top 3 actions (impact/effort badges), tableau produits.
- `shopify-app/app/routes/app.audit-hub.tsx` — entrée "AI Search Readiness" ajoutée en tête de hub.
- `shopify-app/app/lib/i18n.ts` — 18 nouvelles clés FR/EN (auditReadiness, levels, crawlHealth, nicheAlerts, etc.).

### Validation

- `ruff check .` — ✅
- `pytest tests/test_geo/test_readiness.py tests/test_api/test_audit_readiness.py` — **18 passed** ✅
- `pytest` — **1407 passed** ✅ (+14 nouveaux)
- `npm run typecheck` — ✅
- `npm run build` — ✅

### Prochaine tâche recommandée

- **143 — Opportunity Finder Runtime** : agréger les signaux existants en opportunités par produit actif, route `/opportunities`, UI dédiée et tests de scoring déterministe.

## Tâche 141 — Niche Understanding Runtime le 2026-05-20

### Objectif

Transformer les signaux Shopify/GSC/niche existants en hypothèses marketing validables par le marchand avant utilisation par les modules aval.

### Réalisations

- `app/niche/understanding.py` — orchestrateur qui prépare un signal bundle compact, charge `config/prompts/niche_understanding.yaml`, vérifie le budget LLM, appelle `LLMRouter`, parse/normalise le JSON, cache 30 jours et persiste l'hypothèse.
- `app/db.py` — table `llm_cache` SQLite/Postgres pour la clé `(shop, task_name, prompt_version, content_hash)`.
- `app/api/niche.py` — endpoints `POST /niche/understand`, `GET /niche/hypothesis`, `PATCH /niche/hypothesis`.
- Persistance `shop_config.niche_hypothesis` et historique `niche_hypothesis_history` limité aux 5 versions précédentes.
- Helper `get_validated_niche_hypothesis()` : les modules aval peuvent refuser les hypothèses tant que `status != "validated_by_merchant"`.
- `shopify-app/app/routes/app.niche-understanding.tsx` — page Remix pour générer, éditer le JSON et valider les hypothèses marchand.
- Entrée `Compréhension boutique` ajoutée au hub Contenu.

### Décisions

- Le LLM reçoit un payload compact, jamais le snapshot brut complet.
- Le plan Free dégrade la tâche vers le tier logique `medium`; Pro/Agency restent en `advanced`.
- Un fallback déterministe existe pour tests et mode sans LLM explicite, mais le flux UI standard appelle le LLM.
- Les prompts de génération existants ne consomment pas encore ces hypothèses ; ce branchement reste porté par la tâche 145.

### Validation

- `ruff check app/niche/understanding.py app/api/niche.py app/db.py tests/test_niche/test_understanding.py tests/test_api/test_niche_understanding.py` — ✅
- `pytest tests/test_niche/test_understanding.py tests/test_api/test_niche_understanding.py tests/test_api/test_niche_loaders.py tests/test_niche/test_engine.py tests/test_llm/test_prompts.py tests/test_shop_config_store.py tests/test_db_adapter.py` — **56 passed** ✅
- `ruff check .` — ✅
- `pytest` — **1393 passed** ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **142 — Unified Readiness Audit Runtime** : créer la route et l'UI du score AI Search Readiness unifié en consommant scope produit, Crawl L3 et hypothèses niche validées.

## Tâche 140 — Crawl L3 Native Runtime le 2026-05-20

### Objectif

Implémenter le Crawl L3 natif pour ne plus rendre Screaming Frog obligatoire : robots.txt, sitemap, mini-crawl HTTP plafonné, findings persistés et snapshot Shopify étendu.

### Réalisations

- `app/crawl/robots.py` — lecture/parsing robots.txt, extraction `Sitemap:` et vérification `can_fetch()`.
- `app/crawl/sitemap.py` — parsing sitemap XML / sitemap index, découverte récursive et diff sitemap ↔ snapshot.
- `app/crawl/mini.py` — mini-crawl HTTP avec user-agent Léonie, throttling, statut HTTP, chaîne de redirection, canonical, hreflang, title, meta description et validation JSON-LD.
- `app/crawl/findings.py` — agrégation des findings Crawl L3 et persistance dans `crawl_findings`.
- `app/db.py` — table `crawl_findings` SQLite/Postgres.
- `scripts/audit/crawl_shopify.py` et `app/jobs/audit_snapshot.py` — snapshot étendu aux pages CMS, articles de blog, redirects et métadonnées shop.
- `app/api/crawl.py` — endpoint `POST /api/shops/{shop}/crawl/l3` qui combine snapshot, robots, sitemap, mini-crawl, persistance findings et rapport crawl.

### Décisions

- Screaming Frog reste disponible via l'endpoint CSV existant, mais le nouveau chemin backend n'en dépend plus.
- Le mini-crawl reste volontairement HTTP-only : pas de Chromium headless ni stockage HTML brut.
- Les URLs candidates sont limitées au domaine primaire détecté depuis `primaryDomain.url`, puis dédupliquées depuis snapshot + sitemap.

### Validation

- `ruff check app/crawl app/api/crawl.py app/api/snapshot_store.py app/jobs/audit_snapshot.py scripts/audit/crawl_shopify.py app/db.py tests/test_crawl tests/test_api/test_crawl.py tests/audit/test_crawl_shopify.py tests/test_jobs/test_audit_snapshot.py` — ✅
- `pytest tests/test_crawl tests/test_api/test_crawl.py tests/audit/test_crawl_shopify.py tests/test_jobs/test_audit_snapshot.py tests/test_db_adapter.py` — **53 passed** ✅
- `ruff check .` — ✅
- `pytest` — **1385 passed** ✅

### Prochaine tâche recommandée

- **141 — Niche Understanding Runtime** : porter le cadrage niche en runtime LLM + validation marchand.

## Tâche 139 — Product Scope Runtime le 2026-05-20

### Objectif

Implémenter le helper canonique de filtrage produits `ACTIVE` visibles Online Store, puis l'utiliser dans les modules GEO qui calculent scores, priorités, actions et contenus produits.

### Réalisations

- `app/snapshot/scope.py` — helper canonique `filter_products_by_scope()` avec scopes `active`, `draft`, `unlisted`, `archived`, `all`.
- Compatibilité anciens snapshots : un produit sans signal explicite `onlineStoreUrl` / `publishedAt` reste inclus dans `active` pour éviter de vider les catalogues historiques.
- `scripts/audit/crawl_shopify.py` — le crawl Shopify récupère maintenant `publishedAt` et `onlineStoreUrl` en plus de `status`.
- `score_catalog_readiness()`, `prioritize_catalog()`, `build_weekly_actions()`, `build_next_best_actions()` et `generate_catalog_content()` acceptent `scope="active"` par défaut.
- Endpoints GEO `readiness`, `priorities`, `weekly-actions`, `next-best-actions` et `faq-content` acceptent un query param `scope`.
- Les réponses retournent un résumé `scope` avec le scope demandé, les produits inclus et les compteurs par vue.

### Décisions

- Le snapshot continue à capturer tous les produits ; le filtrage est appliqué en aval.
- `onlineStoreUrl = null` est traité comme non publié Online Store, conformément à la documentation Shopify Admin GraphQL.
- Les produits `DRAFT`, `ARCHIVED` et `ACTIVE` non Online Store restent accessibles via scopes dédiés, mais ne polluent plus le scope principal.

### Validation

- `ruff check app/snapshot app/geo/readiness.py app/geo/prioritization.py app/geo/weekly.py app/geo/next_best_actions.py app/geo/faq_generator.py app/api/geo.py scripts/audit/crawl_shopify.py tests/test_snapshot/test_scope.py tests/test_geo/test_readiness.py tests/test_geo/test_prioritization.py tests/test_geo/test_weekly.py tests/test_geo/test_next_best_actions.py tests/test_geo/test_faq_generator.py tests/test_api/test_geo.py tests/audit/test_crawl_shopify.py` — ✅
- `pytest tests/test_snapshot/test_scope.py tests/test_geo/test_readiness.py tests/test_geo/test_prioritization.py tests/test_geo/test_weekly.py tests/test_geo/test_next_best_actions.py tests/test_geo/test_faq_generator.py tests/test_api/test_geo.py tests/audit/test_crawl_shopify.py` — **80 passed** ✅
- `ruff check .` — ✅
- `pytest` — **1369 passed** ✅

### Prochaine tâche recommandée

- **140 — Crawl L3 Native Runtime** : créer les modules natifs sitemap/robots/mini-crawl/findings et brancher le crawl sans rendre Screaming Frog obligatoire.

## Tâche 119 — Validation Timeline J+7/J+30/J+60/J+90 le 2026-05-18

### Objectif

Planifier les fenêtres de mesure après application d'une optimisation et afficher clairement quand les signaux sont trop précoces, mesurables, prêts à relire ou inconclusifs.

### Réalisations

- `app/geo/validation_timeline.py` — génération des fenêtres J+0/J+7/J+30/J+60/J+90 pour les événements `applied`, `measured` et `rolled_back`.
- Statuts par fenêtre : `pending`, `measuring`, `ready`, `inconclusive`.
- Prise en compte de `status_history`, `measurement_status`, `metrics_before`, `metrics_after`, `observed_impact` et volume GSC baseline minimal.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/validation-timeline?event_id=&min_impressions=`.
- `shopify-app/app/routes/app.geo-validation-timeline.tsx` — page Remix avec jalons, dates dues, messages d'interprétation et résumé des fenêtres.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_validation_timeline.py` et `tests/test_api/test_geo.py`.

### Décisions

- V1 calcule la timeline à la demande depuis le ledger au lieu de persister des jobs de mesure ; la persistance peut arriver avec les tâches de dashboard/confiance.
- J+7 reste explicitement un signal faible, J+30 la première vraie lecture, J+60 un signal plus fiable et J+90 la conclusion complète.
- Les fenêtres écoulées sans volume baseline suffisant deviennent `inconclusive` pour éviter les conclusions forcées.
- Une mesure déjà enregistrée via `measurement_status`, `metrics_after` ou `observed_impact` rend la fenêtre correspondante `ready`.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **75/75** ✅
- `pytest tests/test_geo/test_validation_timeline.py tests/test_api/test_geo.py` — **30/30** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **120 — Progress Curve Dashboard** : afficher les courbes score GEO, impressions, clics, CTR, position, conversions, revenu et impact estimé vs observé.

## Tâche 118 — Control Group Builder le 2026-05-18

### Objectif

Sélectionner des pages témoins similaires non modifiées pour comparer l'évolution des pages optimisées à une baseline crédible sans présenter la comparaison comme une preuve causale.

### Réalisations

- `app/geo/control_groups.py` — builder de groupes contrôle par événement appliqué/mesuré avec exclusion des pages déjà optimisées.
- Matching par type de page, catégorie, tags, impressions GSC, position moyenne, prix et score GEO initial.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/control-groups?event_id=&top_events=&controls_per_event=`.
- `shopify-app/app/routes/app.geo-control-groups.tsx` — page Remix listant les pages optimisées, les témoins candidats, score de similarité, métriques baseline et avertissements.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_control_groups.py` et `tests/test_api/test_geo.py`.

### Décisions

- V1 read-only et calculée à la demande : aucun groupe contrôle n'est persisté tant que les fenêtres de mesure automatiques ne sont pas implémentées.
- Les pages avec événements `applied`, `measured` ou `rolled_back` sont exclues comme témoins pour éviter de comparer deux pages modifiées.
- Chaque groupe expose un `causality_note` : les témoins structurent la comparaison, mais ne prouvent pas seuls l'impact.
- Les matches faibles restent visibles avec warning plutôt que masqués, pour éviter une fausse impression de certitude.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **70/70** ✅
- `pytest tests/test_geo/test_control_groups.py tests/test_api/test_geo.py` — **27/27** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **119 — Validation Timeline J+7/J+30/J+60/J+90** : planifier les fenêtres de mesure et afficher quand les signaux seront interprétables.

## Tâche 117 — Optimization Event Tracking le 2026-05-18

### Objectif

Relier chaque optimisation à un événement traçable avec snapshot source, page, type d'action, job ID, scores avant/après, hypothèse, statut et état de mesure.

### Réalisations

- `app/db.py` — extension idempotente de `geo_impact_events` avec `snapshot_id`, `score_before`, `score_after`, `measurement_status` et `status_history` pour SQLite/Postgres.
- `app/geo/ledger.py` — création d'événements enrichis, historique de statut et mise à jour de statut mesurable.
- `app/geo/event_tracking.py` — création d'un événement depuis un snapshot d'optimisation et helper de mise à jour.
- `app/geo/optimization_snapshots.py` — lecture ciblée d'un snapshot par ID.
- `app/api/geo.py` — endpoints :
  - `POST /api/shops/{shop}/geo/ledger/events/from-snapshot`
  - `PATCH /api/shops/{shop}/geo/ledger/events/{event_id}/status`
- `shopify-app/app/routes/app.geo-ledger.tsx` — affichage des snapshots liés, job IDs, scores avant/après, statut de mesure et historique.
- Tests unitaires et API dans `tests/test_geo/test_event_tracking.py`, `tests/test_geo/test_ledger.py` et `tests/test_api/test_geo.py`.

### Décisions

- Le ledger reste la source des événements, tandis que `geo_optimization_snapshots` reste la source de vérité du baseline avant optimisation.
- La création depuis snapshot démarre avec `measurement_status="baseline_captured"` pour distinguer un événement traçable d'un simple événement manuel.
- Les changements de statut ajoutent une entrée horodatée dans `status_history` au lieu d'écraser l'audit trail.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **67/67** ✅
- `pytest tests/test_geo/test_ledger.py tests/test_geo/test_event_tracking.py tests/test_geo/test_optimization_snapshots.py tests/test_api/test_geo.py` — **31/31** ✅
- `ruff check app/geo app/api/geo.py app/db.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **118 — Control Group Builder** : sélectionner des pages témoins similaires non modifiées pour comparer l'évolution des pages optimisées à une baseline crédible.

## Tâche 116 — Optimization Snapshot le 2026-05-18

### Objectif

Capturer l'état exact d'une page avant optimisation afin de préparer la preuve d'impact avant/après, les fenêtres J+7/J+30/J+60 et le futur rollback.

### Réalisations

- `app/db.py` — table `geo_optimization_snapshots` SQLite/Postgres.
- `app/geo/optimization_snapshots.py` — builder et stockage des snapshots avant optimisation : scores GEO/SEO, contenu, faits, commerce, GSC baseline, hash de contenu et hypothèse.
- `app/api/geo.py` — endpoints :
  - `GET /api/shops/{shop}/geo/optimization-snapshots`
  - `POST /api/shops/{shop}/geo/optimization-snapshots`
- `shopify-app/app/routes/app.geo-snapshots.tsx` — page Remix pour créer un snapshot par ressource et lister les captures existantes.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_optimization_snapshots.py` et `tests/test_api/test_geo.py`.

### Décisions

- Les snapshots sont stockés dans une table dédiée plutôt que dans le ledger : le snapshot est l'état source, le ledger reste l'historique des événements.
- V1 couvre produits et collections ; les métriques GA4 et JSON-LD détaillées restent à enrichir dans les tâches suivantes.
- Chaque snapshot capture un `content_hash` pour détecter les changements ultérieurs sans comparer tout le contenu à la main.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **63/63** ✅
- `ruff check app/geo app/api/geo.py app/db.py tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **117 — Optimization Event Tracking** : relier les snapshots aux événements appliqués, jobs, statuts et hypothèses de mesure.

## Tâche 115 — AI Answer Competitor Monitor le 2026-05-18

### Objectif

Comparer les concurrents visibles ou à auditer sur les requêtes conversationnelles prioritaires, avec une approche légère par GSC/import manuel et sans scraping agressif ni copie de contenu.

### Réalisations

- `app/geo/competitors.py` — monitor dry-run : requêtes conversationnelles prioritaires, domaines concurrents fournis, pages Léonie candidates, checklist d'audit et action recommandée.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/competitors?competitors=&top=`.
- `shopify-app/app/routes/app.geo-competitors.tsx` — page Remix `Concurrents AI Search` avec saisie des domaines, cartes par requête, concurrents à auditer et politique anti-copie.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_competitors.py` et `tests/test_api/test_geo.py`.

### Décisions

- V1 sans scraping live : l'outil utilise `gsc_query_page.csv` si disponible, fallback catalogue sinon, et des domaines concurrents fournis par l'utilisateur.
- Les URLs concurrentes sont des candidates de revue manuelle, pas des pages scrapées ni des assertions de visibilité AI Search.
- Chaque requête inclut une politique anti-copie et une action Léonie recommandée : collection/guide, enrichissement facts, FAQ/blocs de réponse ou maillage.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **59/59** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **Phase 11.5 — Optimization Snapshot** : officialiser la boucle de validation d'impact avant de reprendre les tâches 116+.

## Tâche 114 — llms.txt & AI Crawlability Advisor le 2026-05-18

### Objectif

Prévisualiser un `llms.txt` et recommander les pages produits, collections et politiques à rendre lisibles pour les moteurs IA, sans promettre de ranking, citation ou trafic.

### Réalisations

- `app/geo/crawlability.py` — advisor dry-run : pages incluses, pages à revoir/exclure, raisons, priorités et contenu `llms.txt` preview.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/crawlability?top_products=&top_collections=`.
- `shopify-app/app/routes/app.geo-crawlability.tsx` — page Remix `llms.txt & crawl IA` avec preview, warnings et listes de pages.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_crawlability.py` et `tests/test_api/test_geo.py`.

### Décisions

- V1 preview uniquement : aucun fichier `llms.txt` n'est écrit ou publié automatiquement.
- Les produits trop pauvres en texte ou sans handle sont exclus/revus plutôt qu'inclus.
- Le texte généré rappelle explicitement que `llms.txt` est un guidage émergent, pas une garantie de visibilité IA.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **55/55** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **115 — AI Answer Competitor Monitor** : comparer les concurrents visibles sur les requêtes conversationnelles prioritaires via import/manuel ou SERP léger, sans copie de contenu.

## Tâche 113 — FAQ & Answer Block Generator le 2026-05-18

### Objectif

Générer des FAQ et blocs de réponse orientés moteurs IA à partir des faits produits confirmés, avec sources factuelles, prompts de revue humaine et aucune écriture Shopify.

### Réalisations

- `app/geo/answers.py` — génération de blocs de réponse confirmés, prompts marchands pour faits manquants ou signaux imprécis, et JSON-LD `FAQPage` en preview.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/answer-blocks?top=&max_blocks=`.
- `shopify-app/app/routes/app.geo-answer-blocks.tsx` — page Remix `FAQ & réponses GEO` avec blocs confirmés, sources, prompts de revue et JSON-LD.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_answers.py` et `tests/test_api/test_geo.py`.

### Décisions

- Seules les valeurs factuelles confirmées (`description`, type produit, matières, origine, certifications, cibles, propriétés, prix, statut) alimentent les réponses publiables.
- Les signaux vagues comme garantie, livraison, entretien, dimensions ou compatibilité restent des prompts de revue si le contenu ne donne pas une réponse exacte.
- V1 dry-run : pas d'application Shopify et pas de génération LLM, afin de minimiser le risque d'hallucination.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **51/51** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **114 — llms.txt & AI Crawlability Advisor** : proposer un fichier de guidage IA et auditer les pages à inclure/exclure sans promettre de ranking.

## Tâche 112 — AI Search Collection Builder le 2026-05-18

### Objectif

Détecter des opportunités de collections Shopify pensées pour les intentions conversationnelles et les moteurs IA, avec preview complète et aucune création Shopify automatique.

### Réalisations

- `app/geo/collections.py` — builder de collections GEO en dry-run : clustering catalogue, matching requêtes GSC query-page, détection d'intention, score d'opportunité, produits inclus, warnings et preview.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/collections?top=&min_products=`.
- `shopify-app/app/routes/app.geo-collections.tsx` — page Remix `Collections GEO` avec scores, requêtes sources, produits inclus, preview SEO/FAQ et avertissements.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_collections.py` et `tests/test_api/test_geo.py`.

### Décisions

- V1 lecture seule : aucune collection Shopify n'est créée, même si une opportunité est forte.
- La détection utilise les clusters catalogue existants et `gsc_query_page.csv` si disponible ; un fallback catalogue permet de rester utile sans GSC.
- Les embeddings restent différés en V2 : la V1 privilégie un matching lexical explicable et sans nouvelle dépendance.
- Les handles existants et collections trop fines sont signalés comme warnings à revue marchande.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **46/46** ✅
- `ruff check app/geo app/api/geo.py app/db.py tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **113 — FAQ & Answer Block Generator** : générer des FAQ et blocs de réponses depuis les faits produits confirmés, avec sources factuelles, preview et revue humaine.

## Tâche 111 — GEO Risk Guard le 2026-05-18

### Objectif

Identifier les pages produit à protéger avant optimisation GEO, notamment les pages déjà performantes en SEO, prêtes pour l'AI Search, business-critiques, en rupture ou nécessitant une confirmation forte.

### Réalisations

- `app/geo/risk_guard.py` — diagnostic `protected` / `review_required` / `safe`, score de risque, raisons, signaux et politique recommandée.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/risk-guard`.
- `shopify-app/app/routes/app.geo-risk-guard.tsx` — page Remix `GEO Risk Guard`.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests unitaires et API dans `tests/test_geo/test_risk_guard.py` et `tests/test_api/test_geo.py`.

### Décisions

- V1 diagnostic uniquement : le garde-fou n'est pas encore injecté dans tous les workflows d'écriture Shopify.
- Une page est protégée si elle cumule visibilité GSC, position élevée, readiness forte, potentiel business ou risque commerce/stock.
- Les pages `protected` et `review_required` exigent une revue manuelle et une confirmation forte avant de futures écritures GEO.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **41/41** ✅
- `ruff check app/geo app/api/geo.py app/db.py tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **112 — AI Search Collection Builder** : détecter des opportunités de collections Shopify adaptées aux intentions conversationnelles, avec preview et dry-run.

## Tâche 110 — GEO Impact Ledger le 2026-05-18

### Objectif

Créer une mémoire d'impact GEO pour historiser les optimisations, leurs snapshots avant/après, métriques, hypothèses et impact estimé vs observé.

### Réalisations

- `app/db.py` — nouvelle table `geo_impact_events` SQLite/Postgres.
- `app/geo/ledger.py` — création, liste et résumé des événements GEO.
- `app/api/geo.py` — endpoints :
  - `GET /api/shops/{shop}/geo/ledger`
  - `POST /api/shops/{shop}/geo/ledger/events`
- `shopify-app/app/routes/app.geo-ledger.tsx` — page Remix `GEO Impact Ledger`.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- Tests de stockage/API dans `tests/test_geo/test_ledger.py` et `tests/test_api/test_geo.py`.

### Décisions

- Le ledger GEO est séparé de `seo_changes` : `seo_changes` reste dédié au rollback des écritures Shopify, tandis que `geo_impact_events` peut stocker plans, previews, applications, mesures et observations futures.
- V1 lecture seule côté Shopify : créer un événement ledger ne mute aucune donnée marchand.
- Les impacts observés restent optionnels et préparent les fenêtres J+7/J+30/J+60 prévues plus tard.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — **36/36** ✅
- `ruff check app/geo app/api/geo.py app/db.py tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **111 — GEO Risk Guard** : protéger les pages déjà performantes ou business-critiques contre les optimisations excessives, avec blocage des écritures automatiques et confirmation forte.

## Tâche 109 — Weekly GEO Action Assistant le 2026-05-18

### Objectif

Transformer la priorisation revenue-aware en une liste courte de 3 actions GEO hebdomadaires, lisibles par un marchand, avec gain estimé, effort, risque, confiance et prochaines étapes.

### Réalisations

- `app/geo/weekly.py` — sélection des meilleures actions depuis les priorités 108, avec message hebdomadaire et étapes proposées.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/weekly-actions?limit=N`.
- `shopify-app/app/routes/app.geo-weekly.tsx` — page Remix `Actions GEO semaine`.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée placée en haut du hub Contenu & visibilité.
- `tests/test_geo/test_weekly.py` et extension de `tests/test_api/test_geo.py`.

### Décisions

- V1 lecture seule : pas de planification automatique, pas de job récurrent, pas d'écriture Shopify.
- L'assistant hebdo réutilise les priorités revenue-aware et ajoute une couche de sélection/explication plutôt qu'un nouveau scoring concurrent.
- Les messages rappellent que les gains sont estimés et que les actions doivent être revues avant application.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py` — **20/20** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **110 — GEO Impact Ledger** : historiser les optimisations GEO avec snapshot avant/après, facts ajoutés, FAQ, JSON-LD, requêtes ciblées, utilisateur/job ID, métriques GSC/GA4 et impact estimé vs observé.

## Tâche 108 — Revenue-Aware GEO Prioritization le 2026-05-18

### Objectif

Prioriser les actions GEO selon leur utilité business probable, en combinant score AI Search Readiness, impressions GSC, estimation de clics gagnables, prix/AOV fallback, stock/statut, effort, risque et confiance.

### Réalisations

- `app/geo/prioritization.py` — moteur de priorisation produit par produit : action recommandée, score priorité 0-100, effort, risque, confiance, stock, clics gagnables et revenu estimé.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/priorities?top=N&conversion_rate=&average_order_value=&position_improvement=`.
- `shopify-app/app/routes/app.geo-priorities.tsx` — page Remix `Priorités GEO business` avec synthèse et cartes d'actions.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- `tests/test_geo/test_prioritization.py` et extension de `tests/test_api/test_geo.py`.

### Décisions

- V1 sans appel GA4 live dans l'endpoint : si GA4/marge ne sont pas disponibles, le score utilise GSC + prix Shopify + `average_order_value` fallback.
- Le potentiel revenu reste une estimation : courbe CTR, amélioration de position paramétrable, conversion rate et AOV configurables.
- Les produits sans GSC restent scorés avec une confiance basse afin de ne pas disparaître de la priorisation.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py` — **16/16** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **109 — Weekly GEO Action Assistant** : condenser la priorisation en 3 actions hebdomadaires marchandes avec gain potentiel, effort, risque et preview.

## Tâche 107 — AI Search Readiness Score le 2026-05-18

### Objectif

Créer un score interne de préparation aux moteurs IA par produit, sans promettre de ranking ni de citation, en combinant faits produits, schema, capacité à répondre aux questions, confiance, SEO et signaux commerce.

### Réalisations

- `app/geo/readiness.py` — score 0-100 par produit avec sous-scores `facts`, `schema`, `answerability`, `trust`, `seo`, `commerce`, niveau `ready` / `partial` / `weak` et recommandations.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/readiness?top=N`.
- `shopify-app/app/routes/app.geo-readiness.tsx` — page Remix `AI Search Readiness` avec synthèse, score par produit, barres de composants et recommandations.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dédiée dans le hub Contenu & visibilité.
- `tests/test_geo/test_readiness.py` et extension de `tests/test_api/test_geo.py`.

### Décisions

- Le score est présenté comme diagnostic interne, jamais comme garantie de visibilité dans ChatGPT, Perplexity, Gemini ou Google AI Overviews.
- La pondération V1 est volontairement simple : facts 25 %, schema 20 %, answerability 20 %, trust 15 %, SEO 10 %, commerce 10 %.
- La tâche reste lecture seule : aucune génération LLM et aucune écriture Shopify.

### Validation

- `pytest tests/test_geo tests/test_api/test_geo.py` — **11/11** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **108 — Revenue-Aware GEO Prioritization** : croiser score GEO, GSC, GA4, Shopify, stock, marge ou fallback panier moyen, risque et effort pour prioriser les actions business.

## Tâche 106 — GEO Product Facts Layer le 2026-05-18

### Objectif

Créer un socle de faits produits fiables pour les futurs scores GEO, FAQ, JSON-LD, snippets et recommandations AI Search, sans halluciner de matière, origine, certification, garantie ou preuve.

### Réalisations

- `app/geo/facts.py` — extraction lecture seule depuis le snapshot Shopify : faits confirmés, faits manquants sensibles, suggestions à vérifier par le marchand, score de complétude factuelle.
- `app/api/geo.py` — endpoint `GET /api/shops/{shop}/geo/facts?top=N`.
- `shopify-app/app/routes/app.geo-facts.tsx` — page Remix `Faits produits GEO` avec synthèse, score de complétude, faits confirmés et manques à vérifier.
- `shopify-app/app/routes/app.content-hub.tsx` + `i18n.ts` — entrée dans le hub Contenu & visibilité et libellés FR/EN.
- Tests unitaires et API dédiés dans `tests/test_geo/test_facts.py` et `tests/test_api/test_geo.py`.

### Décisions

- La V1 est volontairement conservative : elle utilise uniquement les faits déjà présents dans Shopify et marque les informations sensibles absentes comme suggestions à vérifier.
- Aucune écriture Shopify, aucun LLM, aucune génération automatique dans cette tâche.
- Les faits confirmés réutilisent le NER existant (`app.niche.ner`) pour matières, origines, certifications, cibles et propriétés.

### Validation

- `pytest tests/test_geo/test_facts.py tests/test_api/test_geo.py` — **6/6** ✅
- `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` — ✅
- `cd shopify-app && npm run typecheck` — ✅
- `cd shopify-app && npm run build` — ✅

### Prochaine tâche recommandée

- **107 — AI Search Readiness Score** : calculer un score GEO produit/boutique à partir des faits produits, JSON-LD, FAQ, requêtes conversationnelles, preuves de confiance, maillage, stock, performance et crawlabilité.

## Tâches 101-103 — Phase 10 clôturée le 2026-05-17

### Tâche 101 — Hreflang / SEO international

- `app/api/hreflang.py` — 4 endpoints : status, settings (POST/DELETE), preview. Validation BCP-47, détection 7 types d'issues, génération balises `<link rel="alternate">` + x-default.
- `tests/test_api/test_hreflang.py` — 12 tests.
- `shopify-app/app/routes/app.hreflang.tsx` — tabs Config / Prévisualisation / Problèmes.
- i18n FR/EN + lien NavMenu.

### Tâche 102 — Alertes marchand

- `app/api/alerts.py` — endpoint `/alerts/summary` agrégeant CWV/PageSpeed, crawl 404, CTR faible GSC, budget LLM, jobs échoués.
- `tests/test_api/test_alerts.py` — 8 tests.
- `shopify-app/app/routes/app.alerts.tsx` — dashboard alertes avec DataTable et badges par sévérité.
- i18n FR/EN + lien NavMenu.

### Tâche 103 — Nettoyage scripts transitoires

- `scripts/README.md` mis à jour : tableau CLI-only, tableau équivalents app, notes de migration.
- Notes `App equivalent:` ajoutées dans les docstrings CLI : `generate_faq.py`, `generate_hreflang.py`, `generate_blog_briefs.py`, `send_alerts.py`.
- Aucun script supprimé : tous restent utiles pour les usages batch/CLI/self-hosted.

### Validation
- `pytest` — **1229/1229** ✅
- `ruff check .` — ✅
- `cd shopify-app && npm run typecheck` — ✅

---

## Tâche 100 — FAQ produits et briefs blog le 2026-05-17

### Objectif
Générer des FAQ par produit avec JSON-LD Schema.org (FAQPage) et des briefs blog depuis les requêtes GSC informationnelles, avec interface Remix à deux onglets.

### Livraisons
- `app/api/content.py` — `GET /content/faq` (5 templates génériques × produits) + `GET /content/briefs` (requêtes informationnelles GSC triées par impressions)
- `tests/test_api/test_content.py` — 10 tests : structure FAQ, JSON-LD, filtrage informationnel, tri, fallback no-GSC, liens internes
- `shopify-app/app/routes/app.content.tsx` — tabs FAQ/Briefs, cartes dépliables, bouton copie JSON-LD
- `shopify-app/app/lib/i18n.ts` + `app.tsx` — clés i18n FR/EN + lien NavMenu

### Validation
- `pytest tests/test_api/test_content.py` — **10/10** ✅
- `npm run typecheck` — ✅
- `ruff check && ruff format` — ✅

### Commit
`2fe8033` feat(content): add FAQ suggestions and blog brief generation endpoints

---

## Tâche 94 — Redirections 301 supervisées le 2026-05-16

## Tâche 95 — JSON-LD Structured Data Dashboard le 2026-05-16

### Objectif
Tableau de bord JSON-LD : validation Schema.org et prévisualisation des balises pour Organisation, Produits et Collections.

### Réalisations
- Endpoint  — génère et valide JSON-LD pour toutes les ressources du snapshot GraphQL
- Helpers , , 
- Validation Schema.org avec champs requis par type (, , ,  pour Product)
- Route Remix  — tabs Organisation/Produits/Collections, badge valid/invalid, prévisualisation JSON-LD expandable
- Lien NavMenu + clés i18n FR/EN 
- 7 tests unitaires, ruff clean, TypeScript typecheck clean

### Fichiers modifiés
-  — endpoint  + helpers GraphQL-format
-  — 7 tests
-  — route Remix
-  — NavMenu
-  — clé 

### Validations
- ============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-7.4.0, pluggy-1.0.0 -- /Users/adrienleredde/anaconda3/bin/python
cachedir: .pytest_cache
rootdir: /Users/adrienleredde/leonie-seo
configfile: pyproject.toml
plugins: mock-3.15.1, anyio-4.13.0
collecting ... collected 7 items

tests/test_api/test_jsonld_status.py::test_jsonld_status_returns_organization PASSED [ 14%]
tests/test_api/test_jsonld_status.py::test_jsonld_status_products_included PASSED [ 28%]
tests/test_api/test_jsonld_status.py::test_jsonld_status_collections_included PASSED [ 42%]
tests/test_api/test_jsonld_status.py::test_jsonld_status_valid_counts PASSED [ 57%]
tests/test_api/test_jsonld_status.py::test_jsonld_status_product_has_offers PASSED [ 71%]
tests/test_api/test_jsonld_status.py::test_jsonld_status_no_snapshot_still_returns_org PASSED [ 85%]
tests/test_api/test_jsonld_status.py::test_jsonld_status_extension_note_present PASSED [100%]

============================== 7 passed in 1.16s =============================== : 7/7 ✅
- All checks passed! : clean ✅
-  : clean ✅

- Ajout de `apply_redirect()` dans `app/apply/shopify_writer.py` (mutation `urlRedirectCreate`).
- Ajout de `app/api/redirects.py` :
  - `POST /api/shops/{shop}/audit/redirects/validate` : valide format des chemins (doit commencer par `/`), self-redirects, duplicates, conflits avec handles live du snapshot ; retourne `{total_valid, warnings, valid}`.
  - `POST /api/shops/{shop}/audit/redirects/apply` : valide d'abord, puis dry-run ou écriture Shopify ; `confirm_live_write=true` requis pour les écriture réelles.
- Nouvelle route Remix `shopify-app/app/routes/app.redirects.tsx` :
  - Tableau éditable from/to avec validation inline (chemin invalide → erreur par champ) ;
  - bouton "Valider" (appel validate seulement) ;
  - bouton "Prévisualiser" (dry-run apply) ;
  - bouton "Appliquer" avec confirmation forte avant écriture Shopify ;
  - badges de résultat par ligne (À créer / Créé / Erreur).
- Ajout NavMenu "Redirections 301" et clés i18n FR/EN.
- 7 tests dans `tests/test_api/test_redirects.py`.
- Vérification : **7 passed** · ruff OK · typecheck OK.
- Prochaine tâche : **95 — JSON-LD**.

## Tâche 93 — Réécriture descriptions produits le 2026-05-16

- Ajout de `apply_product_description()` dans `app/apply/shopify_writer.py` (mutation `productUpdate` avec `descriptionHtml`).
- Ajout de `app/api/descriptions.py` :
  - `GET /api/shops/{shop}/audit/descriptions` : charge le snapshot, classifie chaque produit via `classify_product()` CLI existant, génère la description via `build_description()`, retourne `{title, category, old_description, suggested_description, word_count, quality_ok}` par produit.
  - `POST .../apply` : valide la plage de mots (50-400), convertit `\n\n` → `<br><br>` avant push Shopify ; dry-run par défaut, `confirm_live_write=true` requis pour écriture réelle.
- Nouveau route Remix `shopify-app/app/routes/app.descriptions.tsx` :
  - Liste des produits avec catégorie, nombre de mots, badge hors-plage ;
  - Vue "Éditer" par produit : description actuelle (fond gris) vs nouvelle description (textarea éditable) ;
  - Approuver/rejeter par produit + "Tout approuver" ;
  - Prévisualisation dry-run et confirmation forte avant écriture Shopify.
- Ajout NavMenu "Descriptions produits" et clés i18n FR/EN.
- 7 tests dans `tests/test_api/test_descriptions.py`.
- Vérification : **7 passed** · ruff OK · typecheck OK.
- Prochaine tâche : **94 — Redirects 301 supervisés**.

## Tâche 92 — Alt text IA dans l'app le 2026-05-16

- Ajout de `apply_image_alt()` dans `app/apply/shopify_writer.py` (mutation `productImageUpdate`) avec retry rate-limit.
- Ajout de `app/api/alt_text.py` :
  - `GET /api/shops/{shop}/audit/alt-text` : parcourt le snapshot, retourne les images sans alt text avec une suggestion (titre produit + vue N, max 125 chars), `quality_ok` et `char_count` par ligne.
  - `POST /api/shops/{shop}/audit/alt-text/apply` : body `{dry_run: bool, confirm_live_write: bool, items: [...]}` ; valide longueur et non-vide avant d'appeler `ShopifyWriter.apply_image_alt` ; retourne preview en dry-run, résultats réels sinon.
- Sécurité : `require_shopify_write_allowed` bloque les écritures live sans `confirm_live_write`.
- Nouveau route Remix `shopify-app/app/routes/app.alt-text.tsx` :
  - Loader : GET suggestions.
  - Action : POST apply (dry-run ou live).
  - UI : liste par image avec miniature, old alt, `TextField` éditable + compteur de caractères, toggle approuver/rejeter, bouton "Tout approuver", prévisualisation dry-run, confirmation avant écriture live.
- Ajout du lien NavMenu et des clés i18n `altText` FR/EN.
- 7 tests dans `tests/test_api/test_alt_text.py`.
- Vérification : **7 passed** · ruff OK · typecheck OK.
- Prochaine tâche : **93 — Réécriture descriptions produits**.

## Tâche 91 — Maillage interne dans l'app le 2026-05-16

- Ajout de `app/api/internal_links.py` : `GET /api/shops/{shop}/audit/internal-links?top=N` ;
  - matcher générique par chevauchement de tokens (sans handles hardcodés) → fonctionne pour tout tenant ;
  - catégorie `brand` exclue du matching ;
  - détection pages orphelines si `gsc_performance.csv` disponible (produits sans impressions GSC) ;
  - retourne `{available, total_opportunities, total_orphans, gsc_connected, summary, opportunities, orphans}`.
- Mise à jour de `app/main.py` : inclusion de `internal_links_router`.
- Nouvelle route Remix `shopify-app/app/routes/app.internal-links.tsx` :
  - résumé 3 compteurs (opportunités / orphelines / statut GSC) ;
  - deux onglets : "Opportunités" et "Pages orphelines" ;
  - onglet opportunités : badge type (produit/collection), mot-clé source, cible, ancre suggérée, score ;
  - onglet orphelines : titre, chemin, recommandation d'action ;
  - message d'invitation à connecter GSC si non connectée.
- Ajout du lien "Maillage interne" dans le NavMenu après "Cannibalisation".
- Ajout des clés i18n `internalLinks` FR/EN.
- 7 tests dans `tests/test_api/test_internal_links.py`.
- Vérification : **7 passed** · ruff OK · typecheck OK.
- Prochaine tâche : **92 — Alt text IA**.

## Tâche 90 — Détection cannibalisation dans l'app le 2026-05-16

- Ajout de `app/api/cannibalization.py` : `GET /api/shops/{shop}/audit/cannibalization?min_impressions=10&top=50` ;
  - lit `gsc_query_page.csv` depuis `data/raw/{shop}/` ;
  - retourne `available: false` avec message si fichier absent ;
  - appelle `detect_cannibal_pairs()` + `_recommendation()` du module CLI existant ;
  - summary {high / medium / low} selon seuils severity 0.6 / 0.3 ;
  - rows triés par sévérité décroissante.
- Mise à jour de `app/main.py` : inclusion du `cannibalization_router`.
- Nouvelle route Remix `shopify-app/app/routes/app.cannibalization.tsx` :
  - résumé 3 compteurs (haute / moyenne / faible sévérité) ;
  - filtres par niveau de sévérité ;
  - liste de paires : badge sévérité, requête, URL principale vs cannibale (path court), positions, types de page, écart de positions, recommandation lisible.
- Ajout du lien "Cannibalisation" dans le NavMenu après "Longue traîne".
- Ajout des clés i18n `cannibalization` FR/EN.
- 4 tests dans `tests/test_api/test_cannibalization.py`.
- Vérification : `pytest` **1124 passed** · ruff OK · typecheck OK.
- Prochaine tâche : **91 — Maillage interne**.

## Tâche 89 — Analyse longue traîne dans l'app le 2026-05-16

- Ajout de `app/api/longtail.py` : `GET /api/shops/{shop}/audit/longtail?top=N` (défaut 50) ;
  - charge `config/keywords.yaml` (404 si absent) ;
  - charge snapshot Shopify depuis DB/fichier (404 si absent) ;
  - charge `gsc_performance.csv` du shop (DataFrame vide avec colonnes correctes si absent) ;
  - appelle `build_gap_report()` du CLI existant sans duplication de logique ;
  - retourne summary (ranking / on_site / gap) + rows triés par statut et score.
- Ajout de `app/main.py` : inclusion du `longtail_router`.
- Nouvelle route Remix `shopify-app/app/routes/app.longtail.tsx` :
  - résumé 3 compteurs (ranking / sur site sans trafic / gaps) ;
  - filtres par statut et par catégorie de mots-clés ;
  - liste avec badge statut, position GSC, impressions, clics, recommandation lisible ;
  - message si GSC non connectée.
- Ajout du lien "Longue traîne" dans le NavMenu entre Audit et Review IA.
- Ajout des clés i18n `longtail` FR/EN.
- 5 tests dans `tests/test_api/test_longtail.py`.
- Vérification : `pytest` **1120 passed** · ruff OK · typecheck OK · build OK.
- Prochaine tâche : **90 — Détection cannibalisation**.

## Tâche 88 — Matrice ICE dans l'app le 2026-05-16

- Ajout de `app/api/ice.py` :
  - `GET /api/shops/{shop}/audit/ice?top=N` (défaut 20) ;
  - charge le snapshot, appelle `build_ice_matrix()` du CLI sans duplication de code ;
  - charge et score les issues crawl via `_crawl_issue_to_model()` + `score_issue()` ;
  - tri décroissant par `ice_score`, retourne top N rows.
- Mise à jour de `app/main.py` : inclusion du `ice_router`.
- Mise à jour de `shopify-app/app/routes/app.audit.tsx` :
  - interface `IceRow` et champ `ice: IceRow[]` dans `LoaderData` ;
  - loader : fetch `/audit/ice?top=10` en parallèle avec les autres requêtes ;
  - carte "Priorités ICE (top 10)" affichant badge sévérité, label issue_type, titre ressource, score ICE, I/C/E individuels, impressions GSC, et détail ;
  - carte placée entre le score global et la liste d'issues.
- 4 nouveaux tests dans `tests/test_api/test_ice.py` (sorted list, top param, crawl issues, 404 sans snapshot).
- Vérification :
  - `pytest tests/test_api/test_ice.py` : **4 passed** ;
  - `ruff check app/api/ice.py` : OK ;
  - `pytest` : **1106 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **89 — Analyse long tail GSC**.

## Tâche 87 — Audit UI étendu dans l'app le 2026-05-16

- Ajout de `app/api/audit.py` : filtre `resource_type` sur `GET /api/shops/{shop}/audit/issues`.
- Nouvelle route Remix `shopify-app/app/routes/app.audit.tsx` :
  - loader : fetch issues Shopify (depuis snapshot), score SEO et issues crawl en parallèle ;
  - fusion et tri des issues Shopify + crawl par sévérité ;
  - filtres client-side par sévérité (critical / high / medium / low / info) et par type de ressource (produit / collection / image / page / redirect) avec compteurs ;
  - score global + composants + résumé sévérités en haut de page ;
  - liste des issues avec badge sévérité, badge type ressource, label lisible issue_type, titre ressource tronqué et détail lisible ;
  - état vide si aucune donnée ou backend hors-ligne ;
  - limite d'affichage à 200 issues avec message si dépassé.
- Ajout du lien "Audit" dans le NavMenu (`app.tsx`), entre Dashboard et Review IA.
- Ajout de la clé i18n `audit` FR/EN dans `i18n.ts`.
- 1 nouveau test `test_get_issues_resource_type_filter` dans `tests/test_api/test_audit.py`.
- Vérification :
  - `pytest tests/test_api/test_audit.py` : **11 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1102 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **88 — Ajouter la matrice ICE dans l'app**.

## Tâche 86 — Import crawl technique ajouté dans l'app le 2026-05-16

- Ajout du module `app/crawl/` :
  - parse CSV Screaming Frog overview + redirects depuis bytes uploadés ;
  - détection 404, chaînes de redirection, 302 temporaires, titres dupliqués, descriptions dupliquées, canonical manquant, canonical non-self ;
  - stockage shop-scopé `data/raw/{shop}/crawl_report.json` + horodaté ;
  - `latest_crawl_status(shop)` retourne disponibilité, url_count, issue_count, by_severity et liste d'issues.
- Ajout des endpoints :
  - `GET /api/shops/{shop}/crawl/status` ;
  - `POST /api/shops/{shop}/crawl/upload` (multipart CSV, traitement synchrone).
- Ajout de `callBackendMultipartForShop` dans `shopify-app/app/lib/api.server.ts` pour les uploads multipart sans Content-Type forcé.
- L'Onboarding Shopify affiche maintenant :
  - un Step `Crawl technique` dans la checklist d'installation ;
  - une card dédiée avec statut, compteurs par sévérité, top issues critiques, et formulaire d'upload CSV (overview obligatoire + redirects optionnel).
- `python-multipart` ajouté à `pyproject.toml` (dépendance standard FastAPI pour les uploads).
- Vérification :
  - ciblée : `pytest tests/test_crawl/ tests/test_api/test_crawl.py` : **17 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1101 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **87 — Étendre l'audit UI**.

## État courant pour Codex

- Fichier de règles actif : `AGENTS.md`
- Ancien fichier `CLAUDE.md` : archive legacy, ne pas l'utiliser comme source de vérité
- Gestion du contexte : Codex compacte automatiquement ; ne pas utiliser `/compact` ou `/clear`
- Tâche suivante : **88 — Ajouter la matrice ICE dans l'app**

## Checkpoint de pause — 2026-05-12

- La tâche **76** est terminée côté repo.
- La reprise a redémarré sur la tâche **77**, clôturée le 2026-05-15.
- Le repo est prêt à être checkpointé puis poussé sur Git.
- Historique des actions Shopify Partner prévues avant ou pendant la tâche 77, réalisées depuis :
  - créer l'app pilote distincte en **Custom distribution** ;
  - cibler `287c4a-bb.myshopify.com` ;
  - générer le lien d'installation marchand ;
  - relier la config CLI `pilot` avec `shopify app config link --config pilot` ;
  - déployer la config publique une fois l'URL HTTPS prête.

## Reprise 2026-05-13 → 2026-05-15 — Tâche 77 terminée

- L'app Shopify `Léonie SEO Pilot` a été créée dans l'organisation `Léonie Delacroix`.
- `shopify-app/shopify.app.pilot.toml` est lié à cette app et versionné dans le repo.
- L'origine stable retenue est `https://pilot.leoniedelacroix.com`.
- Un Blueprint Render `render.yaml` prépare deux services :
  - `leonie-seo-pilot-web` pour Remix ;
  - `leonie-seo-pilot-api` pour FastAPI.
- Les deux services Render sont déployés et répondent :
  - `https://leonie-seo-pilot-api.onrender.com/health` retourne `status=ok` ;
  - `https://leonie-seo-pilot-web.onrender.com/healthz` retourne `ok`.
- `PYTHON_BACKEND_URL` du service web pointe bien vers `https://leonie-seo-pilot-api.onrender.com`.
- Le domaine custom `https://pilot.leoniedelacroix.com` est vérifié dans Render.
- La configuration Shopify `pilot` a été déployée et publiée en version `leonie-seo-pilot-2`.
- L'app pilote a été retrouvée dans le Developer Dashboard via l'URL directe et installée sur la boutique réelle `Léonie Delacroix`.
- Point d'organisation à traiter plus tard : clarifier/supprimer l'organisation legacy `Léonie Delacroic` pour ne garder que `Léonie Delacroix` comme espace Partner opérationnel.
- Validation pilote réelle :
  - OAuth et chargement embedded dans l'Admin Shopify fonctionnent ;
  - la navigation entre Dashboard, Review IA, Niche, Onboarding, Jobs SEO, Facturation, Réglage et Confidentialité fonctionne ;
  - le plan Free remonte correctement ;
  - le lancement d'audit crée un job côté UI, mais la page Jobs SEO ne le listait pas à cause d'un endpoint backend qui exigeait un token OAuth Python pour lire la queue.
- Correctifs prêts à déployer :
  - `LEONIE_BILLING_MODE=disabled` bloque toute création d'abonnement pendant le pilote ;
  - `/api/shops/{shop}/jobs` vérifie l'appel interne Remix sans exiger de token Shopify stocké côté Python.
- À redéployer sur Render puis retester : relancer un audit, recharger Jobs SEO, vérifier que le job apparaît et passe `pending` → `completed` ou expose une erreur claire.
- Retest après redéploiement : les jobs d'audit apparaissent bien et passent `completed`.
- Nouveau bug pilote identifié : la navigation App Bridge sélectionnait parfois un onglet sans charger la route Remix, ou nécessitait plusieurs clics/rechargements.
- Correctif prêt à déployer : `NavMenu` utilise maintenant des ancres HTML `<a href=...>` au lieu de `Link` Remix, conformément à App Bridge v4.
- Retest navigation : amélioration confirmée.
- Nouveau bug pilote identifié : Review IA affichait `403`, Onboarding affichait Shopify en `TODO`, et Niche restait vide car le backend Python ne recevait pas le token OAuth géré par Remix.
- Correctif prêt à déployer : Remix relaie le token `authenticate.admin` au backend uniquement sur le canal interne protégé (`X-Leonie-Shop` + `X-Internal-Secret`), et Python accepte ce token comme contexte d'installation sans l'exposer au navigateur.
- Données attendues après correctif : Onboarding doit passer Shopify en `OK`; Review IA ne doit plus afficher `403` mais probablement `Aucune donnée disponible`; Niche restera vide tant qu'un vrai snapshot crawl/GSC n'est pas produit.
- Retest OAuth/backend : Onboarding affiche Shopify `OK`, Review IA n'affiche plus `403`, Niche reste vide faute de crawl réel.
- Correctif prêt à déployer : le job `seo_audit` exécute maintenant un crawl Shopify GraphQL en lecture seule, sauvegarde `data/raw/{shop}/shopify_snapshot.json`, `data/raw/{shop}/snapshot_<timestamp>.json`, et insère les lignes `snapshots` avec le shop.
- Sécurité pilote : le token Shopify transmis par Remix est sauvegardé via `token_store` chiffré, pas dans le payload persistant du job.
- À retester après redéploiement : lancer un audit SEO, attendre `completed`, puis vérifier Onboarding `Crawl OK` avec produits/collections et Niche avec clusters produits.
- Bug pilote après retest : le job `seo_audit` passait `completed`, mais Onboarding restait `Crawl TODO / 0 produits`.
- Correctif prêt à déployer : les endpoints Status, Audit et Niche lisent désormais le snapshot depuis `data/raw/{shop}/...` puis basculent sur la table durable `snapshots` si le fichier local manque.
- Retest crawl : Onboarding affiche les produits après audit.
- Correctif prêt à déployer : Review IA dispose d'un bouton `Générer suggestions IA` qui lance un job `meta_generation` depuis le dernier snapshot produit, sans écriture Shopify.
- À retester : cliquer `Générer suggestions IA`, attendre le job `completed`, puis recharger Review IA pour afficher les suggestions pending.
- Bug pilote identifié : un job `meta_generation` est resté en `running` plus de 12 minutes.
- Correctif prêt à déployer : le worker récupère les jobs `running` trop vieux après redémarrage/timeout, les remet en `pending` ou `failed` selon les retries, capture les erreurs LLM configurables, et Jobs SEO affiche maintenant le résultat ou l'erreur du job.
- À retester après redéploiement : recharger Jobs SEO, vérifier que l'ancien job n'est plus bloqué en `running`, puis relancer `Générer suggestions IA` si nécessaire.
- Retest génération IA : le job `meta_generation` est passé `completed` et a généré 21 suggestions, visibles dans Review IA.
- Bug UI pilote identifié : la colonne Produit de Review IA devenait trop large avec un titre produit long et masquait les colonnes à droite.
- Correctif prêt à déployer : Review IA contraint les largeurs Produit/Titre/Description et force le retour à la ligne des textes longs.
- Retest Review IA : approuver/rejeter une suggestion retire bien la ligne du tableau pending.
- Correctif prêt à déployer : Review IA affiche le nombre de suggestions approuvées prêtes, renomme l'action en `Prévisualiser l'application`, bloque l'action si rien n'est approuvé, et confirme qu'aucune modification Shopify n'est faite en mode prévisualisation.
- Retest prévisualisation : le job `bulk_apply` en dry-run passe `completed`.
- Correctif prêt à déployer : le rapport dry-run contient maintenant les produits concernés, le titre courant connu, les nouvelles meta proposées, et Jobs SEO affiche une carte de prévisualisation détaillée sans écriture Shopify.
- Correctif prêt à déployer : la prévisualisation dry-run lit désormais les champs SEO actuels du produit directement dans Shopify quand un token OAuth est disponible, sans mutation, et Jobs SEO indique si l'avant vient de Shopify ou du crawl.
- Correctif prêt à déployer : Review IA affiche désormais un panneau `Audit qualité` pour les suggestions visibles, avec nombre de suggestions OK, suggestions à relire, longueurs moyennes title/description, et principaux motifs de rejet qualité.
- Hotfix prêt à déployer : Review IA normalise les données reçues du backend avant rendu pour éviter une erreur serveur si une suggestion contient une valeur absente ou inattendue.
- Correctif prêt à déployer : les suggestions `À relire` sont maintenant visibles directement dans la colonne Qualité, et l'audit affiche un motif générique quand le backend ne fournit pas de détail technique.

### Clôture 2026-05-15 — Tâche 77

- La tâche **77** est clôturée côté repo et validation locale.
- L'app pilote est installée sur la boutique réelle et les flux critiques ont été validés :
  - OAuth embedded Shopify ;
  - appels internes Remix → Python avec `X-Leonie-Shop`, `X-Internal-Secret` et token Shopify relayé serveur-à-serveur ;
  - sessions et token store chiffré ;
  - Billing désactivable avec `LEONIE_BILLING_MODE=disabled` pour le pilote ;
  - webhooks GDPR/app uninstall présents ;
  - jobs `seo_audit`, `meta_generation` et `bulk_apply` visibles et scopés au shop ;
  - snapshot Shopify réel persisté en fichier et en table `snapshots` ;
  - récupération des jobs `running` obsolètes ;
  - génération IA, review, approbation/rejet et dry-run apply opérationnels.
- La roadmap a été réorganisée :
  - les anciennes tâches App Store finales ont été déplacées après la parité fonctionnelle ;
  - la Phase 10 porte les fonctionnalités restantes des scripts CLI vers l'app Shopify ;
  - la Phase 11 est Revenue-Aware SEO & Shopify-native intelligence (tâches 106-115) ; la Phase 12 est la soumission publique Shopify App Store (tâches 104-105).
- Vérifications locales du 2026-05-15 :
  - `ruff check .` : OK ;
  - `pytest` : **1050 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Suite immédiate après tâche 77 : **78 — mode pilot-safe strict**.

## Tâche 78 — Mode pilot-safe strict terminée le 2026-05-15

- Ajout de `app/safety.py` comme garde-fou central des mutations Shopify.
- Nouveau flag backend `LEONIE_PILOT_SAFE_MODE=true` :
  - bloque les écritures live Shopify pendant le pilote ;
  - autorise les dry-runs ;
  - autorise les lectures Shopify nécessaires aux prévisualisations ;
  - bloque aussi les mutations Shopify Billing pendant le pilote.
- Hors pilot-safe, les écritures live via API/apply ou job `bulk_apply` exigent désormais une confirmation explicite `confirm_live_write=true`.
- `bulk_apply` est protégé à deux niveaux :
  - au moment de l'enqueue API ;
  - au moment de l'exécution orchestrateur, pour empêcher un payload de job forgé.
- La page Settings affiche maintenant l'état du mode pilote.
- `render.yaml`, `.env.example` et `docs/pilot-real-store-setup.md` documentent/activent le mode pilote.
- Tests ciblés ajoutés pour :
  - dry-run autorisé en pilot-safe ;
  - live apply bloqué sans confirmation ;
  - live apply bloqué en pilot-safe même avec confirmation ;
  - `bulk_apply` bloqué côté API et côté orchestrateur ;
  - Billing subscribe/cancel bloqués en pilot-safe.
- Vérification ciblée :
  - `pytest tests/test_api/test_apply.py tests/test_apply/test_bulk_orchestrator.py tests/test_api/test_generate.py tests/test_billing/test_router.py` : **50 passed** ;
  - `ruff check app tests` : OK ;
  - `cd shopify-app && npm run typecheck` : OK.
- Vérification complète :
  - `ruff check .` : OK ;
  - `pytest` : **1060 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **79 — tester les parcours métier réels**.

## Tâche 79 — Parcours métier réels terminée le 2026-05-16

- Ajout de `docs/pilot-real-store-test-plan.md` :
  - checklist embedded Shopify Admin ;
  - critères de pass/fail ;
  - preuves à enregistrer ;
  - points de confiance autour du pilot-safe, Billing, Privacy, Review IA et Jobs SEO.
- Ajout de `docs/pilot-real-store-test-log.md` pour journaliser les passes réelles.
- Mise à jour du README : roadmap 11 phases / 105 tâches, Phase 9 à 4/7, liens vers setup + plan de test pilote.
- Ajout de `leonie-seo pilot smoke-public` pour relancer les smoke checks publics du pilote avec un timeout adapté aux cold starts Render Free.
- Smoke checks publics exécutés le 2026-05-15 :
  - `curl -fsS https://pilot.leoniedelacroix.com/healthz` → `ok` ;
  - `curl -fsS https://leonie-seo-pilot-api.onrender.com/health` → `{"status":"ok","missing_env":[]}` ;
  - `curl -fsS -o /dev/null -w '%{http_code}\n' https://leonie-seo-pilot-api.onrender.com/privacy` → `200`.
  - `python -m scripts.cli pilot smoke-public --timeout 90` → 3 checks OK.
- Note : `HEAD /privacy` retourne `405` avec `allow: GET`, comportement acceptable car la page privacy est servie en GET.
- Vérification locale :
  - `pytest tests/test_pilot_smoke.py tests/test_cli.py` : **45 passed** ;
  - `ruff check scripts/pilot_smoke.py scripts/cli.py tests/test_pilot_smoke.py tests/test_cli.py` : OK ;
  - `ruff check .` : OK ;
  - `pytest` : **1066 passed**.
- Parcours embedded Shopify Admin exécuté le 2026-05-16 depuis une session marchand connectée :
  - installation/session : pass ;
  - navigation : pass ;
  - Settings / pilot-safe : pass, avec une note UX car le libellé exact `Mode pilot-safe actif` n'était pas visible ;
  - audit job, crawl produits/collections, niche clusters : pass ;
  - génération meta, suggestions, approbation/rejet : pass ;
  - dry-run job et preview : pass ;
  - Billing bloqué et Privacy : pass ;
  - bugs/frictions : aucun blocage signalé.
- Journal mis à jour dans `docs/pilot-real-store-test-log.md`.
- Décision : **pass**.
- Prochaine tâche : **80 — capturer les retours d'usage et frictions UX/confiance du pilote**.

## Tâche 80 — Retours pilote consolidés le 2026-05-16

- Ajout de `docs/pilot-real-store-feedback.md` comme backlog de feedback pilote.
- Synthèse du passage réel :
  - aucun bug bloquant ;
  - parcours confiance validé : audit, crawl, niche clusters, génération IA, approbation/rejet, dry-run preview, Billing bloqué, Privacy ;
  - aucune écriture live Shopify observée ou demandée ;
  - un seul retour UX direct : le libellé Settings du mode pilot-safe doit être plus explicite/stable.
- Classement des éléments non bloquants :
  - IDs jobs et compteurs non copiés dans le log : amélioration de preuve de test, pas bug produit ;
  - zones dépendantes GSC/GA4/PageSpeed : manques attendus et déjà suivis en Phase 10.
- Décision : **task 80 pass**.
- Prochaine tâche : **81 — corriger la vague pilote prioritaire**, avec un périmètre initial volontairement réduit au wording pilot-safe Settings sauf nouveau retour.

## Tâche 81 — Vague pilote prioritaire terminée le 2026-05-16

- Correction ciblée du seul retour UX confirmé :
  - Settings affiche maintenant `Mode pilot-safe actif` quand le mode pilot-safe est activé ;
  - le badge indique `Écritures live bloquées` ;
  - le texte d'aide précise que les dry-runs restent autorisés et qu'aucune écriture Shopify live ne peut partir.
- Fichier modifié : `shopify-app/app/routes/app.settings.tsx`.
- `docs/pilot-real-store-feedback.md` documente la résolution de P80-001.
- Vérification :
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **82 — mesurer le pilote**.

## Tâche 82 — Mesure pilote terminée le 2026-05-16

- Ajout de `docs/pilot-real-store-measurement.md`.
- Décision : **pass avec lacunes de mesure**.
- Mesures consolidées :
  - public smoke checks : 3/3 ;
  - parcours embedded : 13/13 zones passées ;
  - bugs bloquants finaux : 0 ;
  - suggestion generation : 21 suggestions dans le retest documenté ;
  - écritures live observées : 0 ;
  - mutations Billing autorisées : 0 ;
  - retour UX direct : 1, corrigé en tâche 81.
- Lacunes à corriger dans les prochains passes :
  - IDs et durées des jobs ;
  - compteurs exacts produits/collections ;
  - compteurs generated/approved/rejected ;
  - coût LLM et tokens du shop pilote ;
  - métrique de récupération des jobs `running`.
- Conclusion : Phase 9 terminée ; le pilote réel est assez solide pour démarrer la Phase 10.
- Prochaine tâche : **83 — connecter Google Search Console dans l'app**.

## Tâche 83 — Google Search Console connecté dans l'app le 2026-05-16

- Ajout du module `app/gsc/` :
  - state OAuth Google signé et expirant ;
  - stockage chiffré des credentials Google par shop dans `google_tokens` ;
  - client Search Console `searchanalytics().query(...)` ;
  - import page et query×page en fichiers shop-scopés.
- Ajout des endpoints :
  - `GET /api/shops/{shop}/gsc/status` ;
  - `POST /api/shops/{shop}/gsc/authorize` ;
  - `POST /api/shops/{shop}/gsc/import` ;
  - `GET /api/google/gsc/callback`.
- Ajout du job async `gsc_import`.
- L'Onboarding Shopify affiche maintenant :
  - l'état de connexion GSC ;
  - la propriété GSC cible ;
  - le lien de consentement Google ;
  - l'action `Importer 90 jours` ;
  - la fraîcheur et le nombre de lignes du dernier import.
- Les exports créés alimentent les vues Niche existantes via `data/raw/{shop}/gsc_*.json`.
- Configuration pilote documentée :
  - `GOOGLE_OAUTH_CLIENT_CONFIG` ou `GOOGLE_OAUTH_CLIENT_PATH` ;
  - `GOOGLE_OAUTH_REDIRECT_URI` ;
  - `GOOGLE_OAUTH_STATE_SECRET`.
- Vérification :
  - ciblée : `pytest tests/test_gsc tests/test_api/test_gsc.py tests/test_jobs/test_worker.py tests/audit/test_fetch_gsc.py` : **22 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1075 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **84 — porter les opportunités GSC dans l'app**.

## Tâche 84 — Opportunités GSC portées dans l'app le 2026-05-16

- Ajout de `GET /api/shops/{shop}/gsc/opportunities`.
- L'endpoint réutilise le moteur CLI `scripts.audit.detect_gsc_opportunities` pour conserver une seule logique métier :
  - positions 11-20 comme quick wins ;
  - pages à CTR faible ;
  - opportunités long terme ;
  - estimation de clics gagnables ;
  - priorisation par score d'impact.
- La page Niche Shopify affiche maintenant une carte `Opportunités GSC` avec :
  - total des opportunités détectées ;
  - répartition quick wins / CTR faible ;
  - gain estimé total ;
  - tableau des pages, zones, positions, impressions, CTR et clics gagnables.
- L'état vide explique que Google Search Console doit être connecté et importé avant de calculer ces opportunités.
- Vérification :
  - ciblée : `pytest tests/test_api/test_gsc.py tests/audit/test_detect_gsc_opportunities.py` : **25 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1077 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **85 — ajouter PageSpeed / Core Web Vitals dans l'app**.

## Tâche 85 — PageSpeed / Core Web Vitals ajoutés dans l'app le 2026-05-16

- Ajout du module `app/pagespeed/` :
  - sélection d'URLs prioritaires par shop depuis la config tenant, puis fallback homepage + collections + produits du dernier snapshot ;
  - import PageSpeed mobile/desktop via le moteur CLI existant ;
  - exports shop-scopés `data/raw/{shop}/pagespeed.csv` et `pagespeed_*.csv` ;
  - résumé mobile/desktop, alertes CWV, recommandations non techniques et détection de régressions entre deux imports.
- Ajout des endpoints :
  - `GET /api/shops/{shop}/pagespeed/status` ;
  - `POST /api/shops/{shop}/pagespeed/import`.
- Ajout du job async `pagespeed_import`.
- L'Onboarding Shopify affiche maintenant :
  - l'état PageSpeed / Core Web Vitals ;
  - les moyennes mobile et desktop ;
  - le nombre d'alertes ;
  - un bouton `Analyser les URLs prioritaires` ;
  - les principales alertes avec une recommandation lisible marchand.
- La page Jobs SEO résume les résultats `pagespeed_import` avec nombre d'URLs, scores et régressions.
- La configuration backend bloque l'enqueue si `PAGESPEED_API_KEY` est absente.
- Correction opportuniste : `find_tenant_by_shop_domain` expose aussi `base_url`, `gsc_property` et `pagespeed_urls`, nécessaires aux workflows app GSC/PageSpeed.
- Vérification :
  - ciblée : `pytest tests/test_pagespeed tests/test_api/test_pagespeed.py tests/test_jobs/test_worker.py tests/audit/test_fetch_pagespeed.py` : **20 passed** ;
  - `ruff check .` : OK ;
  - `pytest` : **1084 passed** ;
  - `cd shopify-app && npm run typecheck` : OK ;
  - `cd shopify-app && npm run build` : OK.
- Prochaine tâche : **86 — ajouter un import crawl technique dans l'app**.

## ⚠️ Archive — audit vision gap initial (2026-05-10)

Un audit complet (`RAPPORT_AUDIT.md`) + analyse critique externe ont évalué la couverture vs. la vision App Store cible.
**Couverture évaluée à l'époque : 28 %** — 3 blockers critiques + 4 risques structurels identifiés.
Ces blockers ont été traités depuis dans les phases 6 à 8 et les vagues d'audit 1-2.

### Blockers critiques identifiés à l'époque (résolus depuis)
| Bloquant | État | Impact |
|---|---|---|
| GDPR webhooks (`customers/redact`, `shop/redact`, `data_request`) | ✅ Résolu tâche 51 | Rejet immédiat App Store évité |
| Shopify Billing API (`appSubscriptionCreate`) | ✅ Résolu tâche 52 | Monétisation App Store possible |
| App Bridge + Polaris | ✅ Résolu tâche 56 | App embedded Shopify Admin |
| Async job queue | ✅ Résolu tâche 55 | Jobs longs hors requêtes HTTP |

### Risques structurels identifiés
- **Architecture pivot** : **Option B retenue** — scaffold Remix propre via Shopify CLI (`shopify-app/`), moteur Python conservé (`scripts/`, `app/llm/`, `app/niche/`). `frontend/` React décommissionné après tâche 57. Voir `DECISIONS.md`.
- **Niche Intelligence** : le différenciateur principal — mais risque de générer des recommandations vagues si non cadré. Approche retenue : clusters produits réels + saturation SERP + keyword gaps (jamais "le marché est en croissance").
- **Common Crawl** : déféré en Phase 8 après validation des sources légères (Google Suggest, pytrends, Reddit). Évite un puits de complexité prématuré.
- **Coût LLM** : GPT-4o mini estimé ~4,5 $/1 000 produits si non optimisé. Maîtrisé par : prompts déterministes, templates versionnés, fallbacks gratuits, cost tracker par tenant (tâche 68).

### Axes manquants à l'époque (résolus depuis)
- **IA / LLM** : ✅ tâches 58-61
- **Niche Intelligence engine** : ✅ tâches 62-63
- **Semantic embeddings** : ✅ tâches 64 et 70
- **Theme App Extension** : ✅ tâche 69
- **Observabilité** : ✅ tâche 68
- **GA4 API** : ✅ tâche 73
- **SQLite → Postgres** : ✅ tâche 54

### Ce qui est solide (à conserver dans tous les scénarios)
- Moteur d'audit Python (`scripts/`) — crawl, GSC, PageSpeed, détection ✅
- OAuth Shopify + token store ✅
- FastAPI backend + CLI Click ✅
- Système de plans + licence HMAC ✅
- Multi-tenant YAML ✅
- 537 tests, ruff clean ✅

## ✅ Terminé

### Infrastructure
- Initialisation repo Git + structure dossiers
- Instructions agent réorganisées avec protocole début de session + ordre des tâches (`AGENTS.md` actif pour Codex)
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

### Phase 4 — Productisation (tâches 40–44) ✅
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
- **43** `scripts/license.py` — HMAC-SHA256, CLI `issue`/`check`, intégration 3 scripts
  - **389 tests verts** · ruff clean
- **44** `scripts/cli.py` + `pyproject.toml` + `Dockerfile` + `install.sh`
  - Point d'entrée `leonie-seo` avec 5 groupes : `setup`, `license`, `audit` (7 cmds), `report` (12 cmds), `apply` (7 cmds)
  - `pip install -e .` → `leonie-seo --help` opérationnel
  - `install.sh` : bootstrap en une commande (venv + pip + .env)
  - `Dockerfile` : Python 3.11-slim, volumes pour data/reports/config
  - **428 tests verts** · ruff clean

### Phase 5 — App Shopify publique (tâches 45–50) ✅ (5/6)
- **50** `app/api/help.py` + `frontend/src/components/HelpPanel.jsx` — FAQ bilingue FR/EN 11 entrées, accordéon + recherche
  - `docs/guide-utilisateur.fr.md`, `docs/user-guide.en.md`, `docs/plans.md`
  - `README.md` réécrit : plans, options install, workflow CLI, licences
  - **537/537 tests verts** · ruff clean
- **48** `app/api/plans.py` + `app/api/deps.py` — plans Free/Pro/Agency, `require_feature()` dependency FastAPI
  - `scripts/license.py` étendu : champ `plan` dans clé HMAC, `--plan` CLI option
  - Badge plan dans header React (`tag-plan-free/pro/agency`)
  - 17 tests plans + 10 tests licence
  - **537/537 tests verts** · ruff clean
- **49** Soumission App Store — supersédée par la tâche 75 (soumission finale après phases 6-8)
- **47** `frontend/` — Dashboard React (Vite + React)
  - 3 vues : Dashboard (score + détail composants), Issues (filtrables par sévérité), Appliquer (dry-run → confirm)
  - `api.js` : wrappers fetch vers FastAPI
  - CORS middleware + serve SPA depuis FastAPI en production
  - `npm run build` → `frontend/dist/` servi par FastAPI
  - **469 tests Python verts** · build Vite clean
- **46** `app/api/` — Backend FastAPI (REST → moteur Python)
  - `deps.py` : `ShopContext` — résolution token OAuth ou fallback `.env`
  - `shops.py` : `GET /api/shops` · `GET /api/shops/{shop}/status`
  - `audit.py` : `GET /api/shops/{shop}/audit/issues` · `/score` (depuis snapshot JSON)
  - `apply.py` : `POST /api/shops/{shop}/apply/meta` (`dry_run=true` par défaut)
  - **469 tests verts** · ruff clean
- **45** `app/main.py` + `app/oauth/` — OAuth Shopify complet
  - `hmac_validator.py` : validation HMAC-SHA256 des callbacks Shopify
  - `token_store.py` : SQLite `shop_tokens` (save/get/delete, `installed_at` préservé)
  - `router.py` : `GET /shopify/install` → redirect OAuth + `GET /shopify/callback` → échange code/token
  - Sécurité : HMAC validé, state UUID4 anti-CSRF (TTL 10 min), token jamais exposé en réponse
  - Nouvelles deps : `fastapi`, `uvicorn[standard]`, `httpx`
  - **449 tests verts** · ruff clean

## ✅ Phases 1-7 complètes — Phase 8 en finalisation

## ✅ Tâche 75 — Préparation App Store finale côté repo
Préparation repo terminée le **2026-05-12** :
- preview locale Shopify stabilisée pour tests réels en dev store ;
- frontend Remix déclaré via `shopify.web.toml` ;
- config `shopify.app.local.toml` dédiée au mode localhost ;
- fallback de session storage local corrigé ;
- route embedded `auth.$.tsx` ajoutée ;
- enregistrement des webhooks ignoré automatiquement en localhost ;
- checklist de soumission documentée dans `docs/app-store-submission-checklist.md`.

La publication publique est volontairement différée derrière une nouvelle séquence de pilote réel sur la boutique Shopify de production.

## ⏳ Phase 9 — Pilote marchand réel avant App Store

**Objectif** : installer et tester Léonie SEO sur la vraie boutique Shopify `leoniedelacroix.com`, observer les frictions réelles, adapter le produit, puis seulement soumettre l'app publiquement.

**Séquence ordonnée** :
- **76** ✅ Préparer l'environnement pilote hors App Store : stratégie pilote custom séparée, URL publique de test, callbacks, secrets et workflow d'installation directe documentés.
- **77** ✅ Installer l'app sur la boutique réelle et valider OAuth, sessions, webhooks et garde-fous d'environnement.
- **78** ✅ Mettre le pilote en mode lecture seule / dry-run strict pour éviter tout changement marchand involontaire.
- **79** ✅ Exécuter les parcours clés dans les vraies conditions métier.
- **80** ✅ Collecter les retours d'usage et les bugs terrain.
- **81** ✅ Corriger la vague prioritaire issue du pilote.
- **82** ✅ Mesurer la qualité réelle : valeur des suggestions, coûts, jobs, confiance marchande.
- **83-103** Porter les fonctionnalités scripts CLI restantes dans l'app Shopify embedded.
- **104** (Phase 12) Décider le go/no-go App Store public.
- **105** (Phase 12) Finaliser et soumettre l'app au Shopify App Store.

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

### Session 2026-05-12 (Vague 5 — App Store UI)

**Mission** : compléter l'expérience Remix avant la tâche 75, pour que l'app montre clairement le workflow marchand App Store au lieu d'un simple dashboard technique.

**UI Remix ajoutée** :
- Navigation App Bridge enrichie : Review IA, Niche, Onboarding, Jobs, Billing, Settings, Privacy.
- `app.review` : revue des suggestions LLM, qualité, approbation/rejet, auto-approve opt-in, lancement apply en dry-run uniquement.
- `app.niche` : clusters produits, keyword gaps, intents GSC et signaux légers Google Suggest.
- `app.onboarding` : checklist installation/backend/crawl/billing/GSC/GA4/permissions + lancement audit asynchrone.
- `app.settings` : santé backend, installation Shopify, snapshot, budget LLM, locales multilingues.
- `app.privacy` : lien policy + résumé export GDPR marchand.
- i18n minimal FR/EN sans nouvelle dépendance.

**Cadrage niche** :
- `pet_accessories_fr` marqué `production`.
- `cosmetics_fr`, `mode_fr`, `jardinage_fr` marqués `template-demo` avec note de périmètre, pour éviter toute promesse excessive App Store.

**Vérifications** :
- `cd shopify-app && npm run typecheck` : OK
- `cd shopify-app && npm run build` : OK
- `ruff format --check .` : OK
- `ruff check .` : clean
- `pytest` : **1033 passed**

**Reste avant tâche 75** :
- Validation manuelle Shopify Partner : URLs publiques/tunnel, captures App Store, privacy/billing/GDPR côté Partner Dashboard.
- Test navigateur embedded réel à faire avec `shopify app dev` et une boutique de test connectée.

### Session 2026-05-12 (Tâche 75 — testabilité App Store et handoff Partner)

**Mission** : rendre l'app réellement testable dans le dev store et clôturer le livrable de préparation App Store côté repo.

**Corrections de testabilité** :
- `shopify.web.toml` ajouté pour lancer Remix derrière `shopify app dev`.
- `shopify.app.local.toml` ajouté pour une preview localhost sans subscriptions webhook incompatibles.
- `auth.$.tsx` ajouté pour la route `/auth/session-token` de la stratégie embedded Shopify.
- `shopify.server.ts` utilise un session storage mémoire officiel en local si `DATABASE_URL` manque.
- `shopify.server.ts` n'enregistre plus les webhooks pendant les previews `localhost`.

**Documentation / clôture** :
- `docs/app-store-submission-checklist.md` documente le test réel en dev store et les tâches restantes dans le Partner Dashboard.
- `ROADMAP.md` clôt la tâche 75 côté repo.

**Vérifications** :
- `cd shopify-app && npm run typecheck` : OK
- `cd shopify-app && npm run build` : OK

### Session 2026-05-12 (replanification post-75 — pilote réel avant App Store)

**Décision produit** : ne pas publier immédiatement au Shopify App Store. Priorité donnée à un pilote réel sur la boutique `leoniedelacroix.com`, afin d'ajuster l'app sur des retours marchands concrets avant la publication publique.

**Roadmap ajoutée** :
- Phase 9 initiale ajoutée, puis réorganisée depuis en Phase 9 tâches **76 à 82**, Phase 10 tâches **83 à 103**, Phase 12 tâches **104 à 105** ; Phase 11 tâches **106 à 115** (Revenue-Aware SEO).
- Prochaine tâche ordonnée : **76**.
- Publication publique App Store repoussée à la tâche **105**, après le pilote, les retours, les corrections prioritaires et la parité scripts CLI → app Shopify.

### Session 2026-05-12 (Tâche 76 — préparation pilote marchand réel)

**Mission** : préparer le cadre repo et opératoire pour tester Léonie SEO sur la vraie boutique Shopify avant toute soumission publique App Store.

**Livrables** :
- `docs/pilot-real-store-setup.md` ajouté : architecture cible, app pilote custom séparée, lien d'installation direct, config `pilot`, secrets et checklist de readiness.
- `DECISIONS.md` enrichi : le pilote réel utilise une app Shopify distincte de la future app publique.
- `.env.example` et `shopify-app/.env.example` clarifiés pour une URL HTTPS publique stable, sessions persistantes et backend public/pilot.
- `README.md` et `docs/app-store-submission-checklist.md` alignés sur la nouvelle séquence Phase 9 avant publication App Store.
- `shopify-app/shopify.app.pilot.toml` est désormais versionné pour figer l'identité et les URLs du pilote réel.

**État à la sortie** :
- Tâche **76** terminée côté repo.
- Actions Shopify Partner encore manuelles avant **77** : créer l'app pilote custom, générer le lien d'installation ciblé sur `287c4a-bb.myshopify.com`, configurer l'URL publique réelle et déployer la config `pilot`.

### Session 2026-05-12 (audit closure Wave 3 & 4)

**Mission** : re-scanner `AUDIT_CODE.md` et `AUDIT_INFRA.md`, fermer les findings encore ouverts sur l'hygiène code, le cleanup legacy et les tests utiles avant la tâche 75.

**Vague 3 — hygiène code** :
- Remplacé les derniers `except Exception`, `datetime.utcnow()` et `asyncio.get_event_loop()` dans `app/`, `scripts/` et `tests/`.
- Ajouté des APIs publiques pour éviter les accès privés utiles (`LLMRouter.providers`, `CCIndexClient.current_crawl`, `classify_intent`).
- Durci les logs structurés : whitelist de champs `extra=` et test anti-fuite de secrets/tokens.
- `compute_cost()` log désormais un warning explicite pour les modèles LLM inconnus au lieu de sous-estimer silencieusement.

**Vague 4 — cleanup legacy** :
- `Dockerfile` ne build plus le dashboard React legacy.
- `frontend/` suivi par Git supprimé ; `.gitignore` ignore désormais le dossier legacy local complet.
- `app/api/apply.py` n'appelle plus `scripts/apply/update_meta.py` ; il utilise `app/apply/ShopifyWriter`.
- `app/api/plans.py` n'importe plus `scripts/license.py` ; validation self-hosted déplacée dans `app/billing/self_hosted_license.py`.
- Ajout de `app/tenant_config.py` pour les besoins app-layer brand/tenant, sans importer `scripts/_config.py`.
- Ajout de `scripts/README.md` pour clarifier les modules canoniques, legacy et transitoires.

**Tests ajoutés / renforcés** :
- Cross-shop mismatch sur endpoints `apply` et `audit`.
- Test route + vrai token store OAuth chiffré.
- Tests observabilité logging/costs.
- Tests signaux alignés sur erreurs réalistes (`requests.ConnectionError`, `RuntimeError`, `ImportError` non bloquant).

**Vérifications** :
- `pytest` : **1033 passed**
- `ruff check .` : clean
- Re-scan : aucun `except Exception`, `datetime.utcnow`, `asyncio.get_event_loop`, ni build Docker `frontend`.

**Reste avant tâche 75** :
- `app/api/audit.py -> scripts/audit + scripts/report` reste un pont transitoire assumé car `scripts/` est encore le moteur d'audit canonique.
- Tâche 75 toujours ⏳ : soumission App Store finale + checklist Partner.

### Session 2026-05-12 (audit complet + corrections Wave 1 & 2)

**Mission** : auditer chaque .md et chaque ligne de code, corriger en TDD les écarts vs l'objectif final (Shopify App Store SEO niche-first multi-tenant).

**Audits livrés** (read-only) :
- `AUDIT_DOCS.md` — 11 dérives doc + 4 contradictions internes
- `AUDIT_CODE.md` — 17 bugs critiques + 30+ secondaires sur 12 654 LOC `app/`
- `AUDIT_INFRA.md` — `scripts/`, `shopify-app/`, `tests/`, `frontend/`, `config/`

**Corrections D1-D3** (commit `cf2cf74`) : `CONTEXT.md` réécrit (accessoires premium vs petfood), guides utilisateurs ne pointent plus sur `frontend/` mort, plans repositionnent HMAC vs Shopify Billing.

**Vague 1 — 9 commits TDD bloquants App Store** :
- `24421e1` retrait email perso `send_alerts.py:216`
- `dbe745b` `TenantConfig` étendu (locale, ga4_property_id, gsc_property, currency)
- `7caed40` colonne `shop` sur `seo_changes` + `snapshots` + migration + isolation impact
- `f429388` auth sur `GET /api/shops` et `/api/jobs/*`
- `93ed3c7` `/billing/confirm` vérifie HMAC + charge_id + re-query Shopify
- `a518207` LLM router par-shop (plus de cache global cross-tenant)
- `eb83e99` brand-lock retiré de `batch.py` + `multilingual.py` (dynamique via tenant config)
- `24645aa` privacy + FAQ dual-mode (`LEONIE_MODE=app_store|self_hosted`)
- `348d34e` Remix `entry.server.tsx` appelle `addDocumentResponseHeaders` (CSP frame-ancestors)

**Vague 2 — 7 commits TDD bugs comportementaux** :
- `343008f` fuite multi-tenant `_load_snapshot/_load_gsc` (`api/niche.py`) + tuple `except` invalide
- `cf306cc` E5 prefix bug (`encode_texts` requiert `mode="query"|"passage"`) + thread-safety
- `a8ab42e` Cloudflare token tracking (estimation char-based + check `success=false`)
- `fc94a99` GA4 `run_report_async` (httpx.AsyncClient) + cache credentials
- `6816717` `ShopifyWriter` read-before-write, `old_value` persisté dans `seo_changes`
- `cdafc46` anti-hallucination `review.py` : keyword overlap + brand presence + suspicious claims
- `6fb6e1e` `niche/engine.py` câble enfin `intent.py` (intent_clusters) + `ner.py` (entity_summary)

**Tests** : 960 → 1028 (+68 nouveaux tests TDD), ruff clean, TypeScript clean (Remix).

**Bilan** : 30 bugs résolus depuis l'audit (17 Wave 1 + 7 Wave 2 + 6 doc D1-D3 + bonus fuite multi-tenant `api/niche.py`). Les Vagues 3, 4 et 5 ont ensuite fermé l'hygiène code, le cleanup legacy et l'UI Remix App Store. Reste : tâche 75 (soumission).

### Session 2026-05-08 (Tâche 44 — packaging)
- `scripts/cli.py` : agrégateur Click — 5 groupes, 26 commandes (setup/license/audit/report/apply)
- `pyproject.toml` : `[project.scripts]` → `leonie-seo = "scripts.cli:cli"` + description/classifiers
- `Dockerfile` : Python 3.11-slim, `VOLUME ["/app/data", "/app/reports", "/app/config/tenants"]`
- `install.sh` : bootstrap une commande — check Python 3.11+, venv, `pip install -e .[dev]`, .env
- `tests/test_cli.py` : 39 smoke tests (--help sur tous les groupes et sous-commandes)
- **428/428 tests verts** · ruff clean

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
- Instructions agent réorganisées
- Tâches 16, 22, 23, 24 (37 tests)

### Session 2026-05-05 (Phase 1 + tâches 17–21)
- Phase 1 complète : 14 fichiers, 49 tests
- 26 méta + 17 alt texts poussés sur Shopify
- GSC connecté : 50 URLs · 3 736 impressions

### Sessions précédentes
- 2026-04-28 : Setup Google Cloud OAuth
- 2026-04-22 : Custom App Shopify
- 2026-04-20 : Initialisation projet
