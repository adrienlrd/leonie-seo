# AI_HANDOFF.md — Léonie SEO

## Current project state

- **Summary:** Léonie SEO est une app Shopify embedded + moteur Python/FastAPI/CLI pour audit SEO, recommandations supervisées, contenus, données structurées, jobs async, intégrations Shopify/Google/LLM et garde-fous dry-run.
- **Main stack:** Python 3.11+, FastAPI, Click, pytest, ruff, Remix, React, TypeScript, Shopify App Bridge, Shopify Polaris, npm.
- **Main working areas:** `app/`, `scripts/`, `shopify-app/`, `config/`, `docs/`, `tests/`.
- **Current roadmap:** Phase 10 clôturée. Phase 11 terminée. Phase 11.5 complète. Phase 11.6 complète (tâche 126 ✅). **Phase 11.7 documentée (GEO Autopilot Simplification before Public Launch, tâches 127-138, ⏳ à implémenter)**. Phase 12 renumérotée en tâches 139-140 (go/no-go + soumission publique Shopify App Store).
- **Known limitations:** Les workflows GEO restent majoritairement read-only. La mesure pilote garde des lacunes historiques sur IDs/durées de jobs, compteurs exacts, coût LLM et suivi fin de certains jobs. Les snapshots V1 ne capturent pas encore GA4 ni JSON-LD détaillé. Le dashboard Impact V1 est livré avec courbes sparklines SVG + score de confiance par optimisation. Le rapport before/after (122) et la détection Win/Neutral/Risk (124) restent à faire.

## Last completed task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 131 — Unified AI Search Readiness Audit (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/readiness-audit.md`. Décisions figées : un seul score `AI Search Readiness` 0-100 par produit, 6 sous-scores publics pondérés (facts 25 % / schema 20 % / answerability 20 % / trust 15 % / seo 10 % / commerce 10 %), 4 niveaux lisibles (excellent ≥80, bon ≥65, partiel ≥45, faible). Mapping exhaustif détecteurs → sous-score : `app/geo/facts.py:122` → Facts, `app/api/jsonld.py:179` + `app/jsonld/builders.py:20` → Schema, FAQ + `conversational_intents` niche → Answerability, NER `app/niche/ner.py` → Trust, `scripts/audit/detect_issues.py:19` + findings Crawl L3 → SEO, `app/geo/readiness.py:123` + Shopify status → Commerce. Intégration `niche_hypothesis` validée : `forbidden_promises` pénalise Trust (−10), `do_not_say` en alerte, `conversational_intents` alimente Answerability. Endpoint canonique `GET /api/shops/{shop}/audit/readiness?scope=active` (cf. `docs/product-scope.md`). Stratégie endpoints : `geo/readiness` redirigé, `audit/score` déprécié, `audit/issues` + `geo/facts` + `geo/crawlability` + `jsonld/status` conservés pour drill-down. UI : fusion `app.geo-readiness.tsx` + `app.geo-facts.tsx` + `app.audit.tsx` → `app.audit-readiness.tsx`, pages drill-down accessibles via liens uniquement. **CWV explicitement hors V1 du score** (déterminé par le thème Shopify, non actionnable depuis l'app) — reste signal séparé. Garde-fou : pondération publique, pas de double comptage, scope ≠ active annoté, snapshot > 7 jours alerté.
- **Files created:** `docs/readiness-audit.md`.
- **Files modified:** `ROADMAP.md` (statut 131 → ✅ 2026-05-19), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** Extension `app/geo/readiness.py` (sous-score Answerability, ajustements niche, findings Crawl L3), route canonique `GET /audit/readiness`, UI `app.audit-readiness.tsx`, et branchement des 22+ pages Remix au score unifié restent à porter par la tâche d'implémentation ultérieure et par 133 (Priority Engine consomme `recommended_actions`) + 137 (Dashboard).
- **Next recommended action:** Tâche 132 (Unified Opportunity Finder) — fusionne GSC, longue traîne, clusters, cannibalisation, maillage et competitor monitor en une seule logique répondant à "quelles pages produits actives méritent une action maintenant ?". Ou tâche 133 (Unified Priority Engine) qui consomme directement `recommended_actions` du score unifié.

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 130 — Merchant Niche Understanding Layer (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/niche-understanding.md`. Décisions figées : 1er vrai consommateur LLM tier `advanced`, 1 appel par shop avec cache 30 jours (invalidation sur ≥20 % changement catalogue / ≥10 nouvelles top queries GSC / demande marchand explicite). Schéma JSON contractuel détaillé (shop_summary, customer_segments, buying_motivations avec evidence obligatoire, objections, priority_products, marketing_angles, conversational_intents, probable_competitors, brand_voice, forbidden_promises, global_confidence, missing_inputs) — chaque hypothèse porte sa propre confiance. Workflow de correction marchand : UI éditable section par section, payload validé persisté dans `shop_config.niche_hypothesis` (table existante `app/shop_config_store.py`), historique N=5 versions, statut `validated_by_merchant` bloque tout module aval (131-134) tant que non confirmé. Propagation : 131 (forbidden_promises + do_not_say), 132 (intents + segments), 133 (priority_products + segments), 134 (brand_voice + angles + segments + motivations dans tous les prompts). Plan Free dégradé vers tier `medium` sans personas détaillés ni probable_competitors. Réutilisation : `app/niche/engine.py`, `app/niche/signals/aggregator.py:14`, `app/niche/ner.py`, `app/embeddings/store.py`, `app/llm/router.py:70`. Limitations V1 explicites : pas de scraping avis tiers, pas d'analyse image, max 4 personas, pas de localisation par marché Shopify Markets.
- **Files created:** `docs/niche-understanding.md`.
- **Files modified:** `ROADMAP.md` (statut 130 → ✅ 2026-05-19), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** `app/niche/understanding.py`, `config/prompts/niche_understanding.yaml`, route `POST /api/shops/{shop}/niche/understand` + `GET/PATCH /niche/hypothesis`, et UI Remix `app.niche-understanding.tsx` restent à créer. Les prompts existants (`product_description.yaml:5`, `collection_brief.yaml`, `blog_brief.yaml`) ont toujours leur contexte hardcodé "accessoires premium animaux" — mise à jour à porter par la tâche 134.
- **Next recommended action:** Tâche 131 (Unified AI Search Readiness Audit) — fusionne `app/geo/readiness.py:199` + `app/geo/facts.py` + SEO Issues + Crawl L3 + PageSpeed + status produit en un seul score lisible. Ou tâche 137 (Dashboard Simplification) qui consomme les 4 docs déjà produites (LLM, Product Scope, Crawl L3, Niche Understanding).

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 128 — Crawl Level 3 Replacement Strategy (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/crawl-strategy.md`. Décisions figées : Crawl L3 = (1) Shopify API snapshot étendu pages CMS + articles blog + redirects, (2) sitemap scan automatique via `robots.txt` puis `sitemap.xml`, (3) mini-crawl HTTP plafonné des URLs prioritaires (statut, canonical, hreflang, JSON-LD). Mapping détecteurs → source : 404, redirect chains, canonical, hreflang, JSON-LD parsing deviennent natifs Crawl L3 (aujourd'hui CSV-only). Plafonds par plan : Free 50 / Pro 200 / Agency 1 000 URLs/job. Throttling 1 req/s, respect strict robots.txt, pas de Chromium headless. Modules à créer (post-128) : `app/crawl/sitemap.py`, `robots.py`, `mini.py`, `findings.py`. Import CSV Screaming Frog (`app/api/crawl.py:21`) reste accessible en "Mode avancé" sans être prérequis. Observation clé : la totalité des détecteurs aujourd'hui CSV-only (404, redirect chains, canonical) deviennent natifs Crawl L3 — `app/crawl/client.py` continue de fonctionner pour le mode avancé.
- **Files created:** `docs/crawl-strategy.md`.
- **Files modified:** `ROADMAP.md` (statut 128 → ✅ 2026-05-19), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** Tous les modules cibles (`app/crawl/sitemap.py`, `robots.py`, `mini.py`, `findings.py`) restent à créer par la tâche d'implémentation Crawl L3 ultérieure. L'extension du snapshot Shopify (pages + articles + redirects) reste à porter. UI Audit continue de mettre l'upload CSV au même niveau que l'audit Shopify.
- **Next recommended action:** Tâche 130 (Merchant Niche Understanding Layer — premier vrai consommateur de la stratégie LLM cadrée en 129) ou tâche 131 (Unified AI Search Readiness Audit — fusionne les briques existantes facts/SEO issues/PageSpeed/Crawl L3).

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 127 — Product Scope Simplification (cadrage produit, Phase 11.7).
- **Summary:** Création de `docs/product-scope.md`, référence canonique du périmètre V1 public. Décisions figées : 4 vues (`Active Products`, `Pre-launch Drafts`, `Hidden/Unlisted`, `Cleanup/Archived`), règle de scope principal = `status=ACTIVE` ET visible Online Store, mapping module par module (`app/geo/readiness.py:199`, `app/geo/prioritization.py:167`, `app/geo/weekly.py:68`, `app/geo/next_best_actions.py`, `app/geo/faq_generator.py:441`), helper canonique `filter_products_by_scope` à créer par la première tâche consommatrice, pattern UI Polaris (Tabs/Select + bandeau "x produits inclus"), garde-fou "Apply" désactivé hors scope active, snapshot inchangé. Observation clé : deux pénalités individuelles existent déjà (`_commerce_score`, `_inventory_signal`) mais aucun filtrage global ; les scores agrègent actuellement ACTIVE+DRAFT+ARCHIVED.
- **Files created:** `docs/product-scope.md`.
- **Files modified:** `ROADMAP.md` (statut 127 → ✅ 2026-05-19), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** Helper canonique non implémenté ; modules `readiness`, `prioritization`, `weekly`, `next_best_actions`, `faq_generator` continuent d'agréger tous statuts jusqu'à ce que les tâches consommatrices 131-134 appliquent la stratégie. Sélecteur UI de vue à implémenter par tâche 137 ou par chaque page concernée.
- **Next recommended action:** Tâche 128 (Crawl Level 3 Replacement Strategy) ou tâche 130 (Merchant Niche Understanding Layer, premier vrai consommateur LLM).

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 129 — Low-Cost LLM Strategy & Provider Routing (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/llm-strategy.md`, référence canonique de l'usage LLM. Décisions figées : 3 tiers (`low-cost`/`medium`/`advanced`) avec providers mappés ; mapping tâches consommatrices existantes (`meta_title`, `briefs`, `multilingual`) et à venir (130-134) → tier ; clé de cache `(shop, task_name, prompt_version, content_hash)` + TTL par type ; quotas Free/Pro/Agency (appels max, budget USD) ; règle d'enforcement `check_budget` avant chaque `router.complete()` ; mode `low-cost only` global + par shop ; fallback sans escalade de tier ; checklist d'intégration bloquante. Réutilisation explicite de `app/llm/provider.py`, `app/llm/router.py`, `app/observability/metrics.py`, `app/observability/costs.py` et `config/prompts/*.yaml` — aucune réécriture de la couche LLM existante.
- **Files created:** `docs/llm-strategy.md`.
- **Files modified:** `ROADMAP.md` (statut 129 → ✅ 2026-05-19).
- **Validations run:** Aucune (documentation uniquement).

---

## Task before previous

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Phase 11.7 documentation — GEO Autopilot Simplification before Public Launch (tâches 127-138). Renumérotation Phase 12 → tâches 139-140. Cadrage produit explicite : phase de documentation stratégique avant codage, fusion en 6 modules, briques repoussées hors MVP public.
- **Files modified:** `ROADMAP.md` (nouvelle section Phase 11.7 complète + renumérotation Phase 12), `docs/AI_HANDOFF.md` (Current roadmap mis à jour).
- **Validations run:** Aucune (documentation uniquement).
- **Next recommended action:** Tâche 129 (cadrage LLM) avant 130-134.

---

## Task before previous (126)

- **Date:** 2026-05-19
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 126 — GEO FAQ & Buying Guide Automation. **Phase 11.6 complète.**
- **Summary:** Ajout de `app/geo/faq_generator.py` : génération template-based (sans LLM) de FAQ produits, FAQ collections, answer blocks, guides d'achat et JSON-LD FAQPage depuis les faits confirmés (analyze_product_facts) et les requêtes GSC réelles. Score qualité 0-100 avec 4 labels. Statut `draft/needs_review` automatique. Garde-fous : aucun fait inventé, faits manquants sensibles affichés en review, dry-run total. Endpoint `GET /api/shops/{shop}/geo/faq-content`. Page Remix interactive avec expand/collapse par produit, preview JSON-LD, banner faits manquants. Entrée ajoutée dans le hub Insights. 1357 tests.
- **Files created (task 126):**
  - `app/geo/faq_generator.py`
  - `tests/test_geo/test_faq_generator.py`
  - `shopify-app/app/routes/app.geo-faq-content.tsx`
- **Files modified (task 126):**
  - `app/api/geo.py` (route faq-content + import)
  - `tests/test_api/test_geo.py` (1 test intégration)
  - `shopify-app/app/routes/app.insights.tsx` (entrée FAQ & guides)
  - `shopify-app/app/lib/i18n.ts` (clés `faq*` FR/EN)
  - `ROADMAP.md` (statut 126 → ✅ 2026-05-19)
- **Validations run (task 126):** `ruff check` (clean), `pytest` (1357 passed), `npm run typecheck` (OK), `npm run build` (OK).
- **Known limitations (V1):** Génération template-based sans LLM. Pas d'export Markdown/CSV depuis l'UI (à ajouter V2). Pas d'application Shopify directe (dry-run only). Collections associées aux produits par overlap de titre — matching simple.
- **Next recommended action:** Implémenter la Phase 11.7 (GEO Autopilot Simplification) avant d'attaquer la Phase 12. Commencer par la tâche 129 (Low-Cost LLM Strategy & Provider Routing) ou 127 (Product Scope Simplification) selon les priorités produit.

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 125 — Next Best Action Loop. **Phase 11.5 complète.**
- **Summary:** Ajout de `app/geo/next_best_actions.py` qui transforme les verdicts du rapport avant/après en actions concrètes prioritisées (`répliquer` / `ajuster` / `rollback` / `attendre`) avec suggestions de produits similaires depuis le snapshot catalog. Garde-fous : `dry_run=True` toujours, jamais de write Shopify sans confirmation. Endpoint `GET /api/shops/{shop}/geo/next-best-actions`. Page Remix `app.next-best-actions.tsx` avec DataTable + badges priorité et action. Bouton "Prochaines actions →" (primary) ajouté dans la page Impact. 1342 tests.
- **Files created (task 125):**
  - `app/geo/next_best_actions.py`
  - `tests/test_geo/test_next_best_actions.py`
  - `shopify-app/app/routes/app.next-best-actions.tsx`
- **Files modified (task 125):**
  - `app/api/geo.py` (route next-best-actions + import)
  - `tests/test_api/test_geo.py` (1 test intégration)
  - `shopify-app/app/routes/app.impact.tsx` (bouton NBA primary)
  - `shopify-app/app/lib/i18n.ts` (clés `nba*` FR/EN)
  - `ROADMAP.md` (statut 125 → ✅ 2026-05-19)
- **Validations run (task 125):** `ruff check --fix` (1 fixé), `pytest` (1342 passed), `npm run typecheck` (OK), `npm run build` (OK).
- **Next recommended action:** Task 126 — GEO FAQ & Buying Guide Automation (Phase 11.6).

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 124 — Win/Neutral/Risk Detection widget.
- **Summary:** Ajout d'un widget "Bilan Win / Neutre / Risque" dans la page Impact, sans nouveau code backend. Le loader appelle maintenant `/geo/impact-report` en parallèle (3 appels `Promise.allSettled`) et extrait `summary.by_verdict`. Le widget affiche 4 cases colorées (Gain probable vert, Neutre jaune, Inconclusif gris, Risque rouge) avec compteur par catégorie, visible uniquement quand des optimisations existent. 1333 tests, typecheck + build OK.
- **Files modified (task 124):**
  - `shopify-app/app/routes/app.impact.tsx` (3e appel parallèle + interface VerdictSummary + widget)
  - `shopify-app/app/lib/i18n.ts` (clés `verdictWidget*` + `verdictLabel_*` FR/EN)
  - `ROADMAP.md` (statut 124 → ✅ 2026-05-19)
- **Validations run (task 124):** `pytest` (1333 passed), `npm run typecheck` (OK), `npm run build` (OK).
- **Next recommended action:** Task 125 — Next Best Action Loop (dernière tâche Phase 11.5).

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 123 — Retention Milestones.
- **Summary:** Ajout du module `app/geo/retention_milestones.py` qui calcule l'état J+7/J+30/J+60/J+90 à partir des dates d'application de tous les événements GEO. Chaque jalon indique `completed/active/upcoming`, le nombre d'optimisations ayant atteint la fenêtre, et un message pédagogique FR/EN. Endpoint `GET /api/shops/{shop}/geo/retention-milestones`. Page Remix `app.retention-milestones.tsx` avec ProgressBar Polaris par jalon et bannière de rétention. Lien ajouté dans `app.impact.tsx`. 1333 tests passent.
- **Files created (task 123):**
  - `app/geo/retention_milestones.py`
  - `tests/test_geo/test_retention_milestones.py`
  - `shopify-app/app/routes/app.retention-milestones.tsx`
- **Files modified (task 123):**
  - `app/api/geo.py` (route retention-milestones + import)
  - `tests/test_api/test_geo.py` (1 test intégration)
  - `shopify-app/app/routes/app.impact.tsx` (import InlineStack + boutons rapport et jalons)
  - `shopify-app/app/lib/i18n.ts` (clés `retention*` FR/EN)
  - `ROADMAP.md` (statut 123 → ✅ 2026-05-19)
- **Validations run (task 123):** `ruff check --fix` (3 fixés, 0 restants), `pytest` (1333 passed), `npm run typecheck` (OK), `npm run build` (OK).
- **Open issues:** Aucun.
- **Next recommended action:** Task 124 — Win/Neutral/Risk Detection (note : verdict déjà implémenté dans task 122, à valider si tâche fermable sans code).

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 122 — Before/After Impact Report.
- **Summary:** Ajout du module `app/geo/impact_report.py` qui produit un rapport par événement GEO avec scores avant/après (GEO, SEO, GSC, GA4), verdict (`positif_probable` / `neutre` / `inconclusif` / `négatif_possible`) et recommandation suivante (`répliquer` / `ajuster` / `rollback` / `attendre`). Export Markdown intégré via `render_markdown`. Endpoint `GET /api/shops/{shop}/geo/impact-report`. Page Remix `app.impact-report.tsx` avec DataTable, badges verdict colorés et bouton téléchargement Markdown (`data:` URI, sans dépendance). Lien "Voir le rapport complet" ajouté dans `app.impact.tsx`. 1325 tests passent.
- **Files created (task 122):**
  - `app/geo/impact_report.py`
  - `tests/test_geo/test_impact_report.py`
  - `shopify-app/app/routes/app.impact-report.tsx`
- **Files modified (task 122):**
  - `app/api/geo.py` (route impact-report + import)
  - `tests/test_api/test_geo.py` (1 test intégration)
  - `shopify-app/app/routes/app.impact.tsx` (import Button + lien rapport)
  - `shopify-app/app/lib/i18n.ts` (clés `impactReport*` FR/EN)
  - `ROADMAP.md` (statut 122 → ✅ 2026-05-19)
- **Validations run (task 122):** `ruff check --fix` (1 fixé, 0 restants), `pytest` (1325 passed), `npm run typecheck` (OK).
- **Open issues:** Drill-down par page non implémenté (exclu V1). Score de confiance n'incorpore pas encore le groupe contrôle.
- **Next recommended action:** Task 123 — Retention Milestones.

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 121 — Impact Confidence Score.
- **Summary:** Ajout du module `app/geo/confidence.py` qui calcule un score 0-100 par événement GEO à partir de 6 facteurs pondérés (délai écoulé, volume impressions, delta score GEO, évolution GSC impressions, revenu observé, stabilité stock/prix) avec 4 labels (`données_insuffisantes`, `signal_faible`, `impact_probable`, `impact_fort`). Garde-fous : score 0 si rolled_back ou applied_at introuvable. Endpoint `GET /api/shops/{shop}/geo/confidence-scores`. Page Impact mise à jour avec appel parallèle + colonne Confiance en DataTable (badge Polaris coloré). 1315 tests passent.
- **Files created (task 121):**
  - `app/geo/confidence.py`
  - `tests/test_geo/test_confidence.py`
- **Files modified (task 121):**
  - `app/api/geo.py` (route confidence-scores + import)
  - `tests/test_api/test_geo.py` (1 test intégration)
  - `shopify-app/app/routes/app.impact.tsx` (appel parallèle + colonne Confiance)
  - `shopify-app/app/lib/i18n.ts` (clé `impactColConfidence` FR/EN)
  - `ROADMAP.md` (statut 121 → ✅ 2026-05-19)
- **Validations run (task 121):** `ruff check --fix` (2 fixés, 0 restants), `pytest` (1315 passed), `npm run typecheck`, `npm run build` (OK).
- **Open issues:** Drill-down par page reporté (tâche 122). Score de confiance n'incorpore pas encore le groupe contrôle (tâche 118 données) — à enrichir dans une V2 si demandé.
- **Next recommended action:** Task 122 — Before/After Impact Report.

---

## Previous task

- **Date:** 2026-05-19
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 120 — Progress Curve Dashboard (V1).
- **Summary:** Ajout d'un agrégateur `build_progress_curve` qui produit les séries temporelles (score GEO/SEO, GSC impressions/clics/CTR/position depuis snapshots, GA4 sessions/conversions/revenu via nouvelle requête `get_organic_daily`, impact estimé vs observé par event) + flags qualité (low_volume, incomplete_tracking, out_of_stock_pages, price_changed_pages). Exposé via `GET /api/shops/{shop}/geo/progress-curve?days=90` avec dégradation gracieuse si GA4/GSC absents. Page Remix `app.impact.tsx` avec sparklines SVG inline (pas de polaris-viz pour éviter une dépendance lourde), entrée sur le hub Insights, i18n FR/EN. 1304 tests passent, ruff clean, typecheck + build TS OK.
- **Files created (task 120):**
  - `app/geo/progress_curve.py`
  - `tests/test_geo/test_progress_curve.py`
  - `shopify-app/app/components/Sparkline.tsx`
  - `shopify-app/app/routes/app.impact.tsx`
- **Files modified (task 120):**
  - `app/ga4/queries.py` (ajout `get_organic_daily`)
  - `app/api/geo.py` (route progress-curve + helper `_load_ga4_daily`)
  - `tests/test_api/test_geo.py` (2 tests d'intégration)
  - `shopify-app/app/routes/app.insights.tsx` (entrée Impact GEO sur le hub)
  - `shopify-app/app/lib/i18n.ts` (clés `impact*` FR/EN)
  - `ROADMAP.md` (statut 120 → ✅ 2026-05-19)
- **Validations run (task 120):** `ruff check` (clean), `pytest` (1304 passed), `cd shopify-app && npm run typecheck`, `cd shopify-app && npm run build` (OK).
- **Open issues:** Pas de drill-down par page (volontairement exclu V1) ; à traiter via tâche 122. Sparklines SVG = pas de tooltip interactif ; upgrade vers polaris-viz possible si demande marchand.
- **Next recommended action:** Task 121 — Impact Confidence Score (0-100 selon durée, volume, groupe contrôle, stabilité stock/prix, cohérence GSC/GA4).

---

## Previous task

- **Date:** 2026-05-18
- **Agent:** Codex
- **Goal:** Task 119 — Validation Timeline J+7/J+30/J+60/J+90.
- **Summary:** Added validation windows for applied/measured GEO optimization events, with pending/measuring/ready/inconclusive statuses, time-based messages, baseline volume safeguards, API, tests and a Remix timeline page.
- **Files created:**
  - `app/geo/__init__.py`
  - `app/geo/facts.py`
  - `app/geo/readiness.py`
  - `app/geo/prioritization.py`
  - `app/geo/weekly.py`
  - `app/geo/ledger.py`
  - `app/geo/risk_guard.py`
  - `app/geo/collections.py`
  - `app/geo/answers.py`
  - `app/geo/crawlability.py`
  - `app/geo/competitors.py`
  - `app/geo/optimization_snapshots.py`
  - `app/geo/event_tracking.py`
  - `app/geo/control_groups.py`
  - `app/geo/validation_timeline.py`
  - `app/api/geo.py`
  - `tests/test_geo/__init__.py`
  - `tests/test_geo/test_facts.py`
  - `tests/test_geo/test_readiness.py`
  - `tests/test_geo/test_prioritization.py`
  - `tests/test_geo/test_weekly.py`
  - `tests/test_geo/test_ledger.py`
  - `tests/test_geo/test_risk_guard.py`
  - `tests/test_geo/test_collections.py`
  - `tests/test_geo/test_answers.py`
  - `tests/test_geo/test_crawlability.py`
  - `tests/test_geo/test_competitors.py`
  - `tests/test_geo/test_optimization_snapshots.py`
  - `tests/test_geo/test_event_tracking.py`
  - `tests/test_geo/test_control_groups.py`
  - `tests/test_geo/test_validation_timeline.py`
  - `tests/test_api/test_geo.py`
  - `shopify-app/app/routes/app.geo-facts.tsx`
  - `shopify-app/app/routes/app.geo-readiness.tsx`
  - `shopify-app/app/routes/app.geo-priorities.tsx`
  - `shopify-app/app/routes/app.geo-weekly.tsx`
  - `shopify-app/app/routes/app.geo-ledger.tsx`
  - `shopify-app/app/routes/app.geo-risk-guard.tsx`
  - `shopify-app/app/routes/app.geo-collections.tsx`
  - `shopify-app/app/routes/app.geo-answer-blocks.tsx`
  - `shopify-app/app/routes/app.geo-crawlability.tsx`
  - `shopify-app/app/routes/app.geo-competitors.tsx`
  - `shopify-app/app/routes/app.geo-snapshots.tsx`
  - `shopify-app/app/routes/app.geo-control-groups.tsx`
  - `shopify-app/app/routes/app.geo-validation-timeline.tsx`
- **Files modified:**
  - `app/db.py`
  - `app/main.py`
  - `shopify-app/app/lib/i18n.ts`
  - `shopify-app/app/routes/app.content-hub.tsx`
  - `PROGRESS.md`
  - `ROADMAP.md`
  - `docs/AI_HANDOFF.md`
- **Decisions made:**
  - Facts Layer V1 and Readiness Score V1 are read-only and use only existing Shopify snapshot data.
  - Sensitive facts such as material, origin, certification, warranty, dimensions and compatibility are never invented; missing values become merchant verification prompts.
  - Existing `app.niche.ner` is reused for product entities instead of creating a duplicate extractor.
  - AI Search Readiness is explicitly an internal diagnostic score, not a ranking or AI citation guarantee.
  - Revenue estimates use GSC, CTR curve assumptions, conversion rate and AOV/price fallback; they are priority signals, not promises.
  - The endpoint does not call GA4 live in V1, to keep the workflow fast and available when GA4 is not connected.
  - Weekly actions are a read-only selection layer, not an automatic scheduler or Shopify write workflow.
  - GEO ledger uses a dedicated `geo_impact_events` table instead of overloading `seo_changes`, because the ledger tracks plans, previews and measurements as well as applied writes.
  - Risk Guard V1 is diagnostic-only; future write workflows should consult it before live Shopify mutations.
  - AI Search Collection Builder V1 is read-only: it returns previews and warnings but never creates Shopify collections.
  - Collection suggestions use catalog clustering and query-token matching first; embeddings are deferred to a later version to avoid adding dependencies and keep recommendations explainable.
  - Existing collection handles and thin candidates are flagged for merchant review.
  - FAQ/answer blocks only use confirmed facts with explicit sources; vague topic signals and missing sensitive facts are kept as review prompts.
  - Answer Block Generator V1 is dry-run and does not call an LLM or write to Shopify.
  - llms.txt Advisor V1 is preview-only and does not publish files; it treats llms.txt as emerging AI crawl guidance, not as a ranking or citation guarantee.
  - Thin product pages and missing handles are excluded or marked for review rather than included in the llms.txt preview.
  - Competitor Monitor V1 avoids live scraping; competitor domains are treated as manual review candidates, not verified AI answer captures.
  - Competitor review output includes an anti-copy policy and recommends internal Léonie actions from confirmed facts and catalog readiness.
  - Optimization snapshots use a dedicated `geo_optimization_snapshots` table instead of overloading `geo_impact_events`.
  - Snapshot V1 captures GSC baseline and product/catalog facts now; GA4 and deeper JSON-LD baselines are deferred to follow-up impact tasks.
  - Optimization events now reference snapshot IDs instead of duplicating snapshot ownership; snapshots remain the baseline source, ledger events remain the action/status history.
  - Event status changes append to `status_history` for auditability instead of overwriting previous states.
  - Control groups are computed on demand in V1 instead of persisted; persistence should wait until automatic measurement windows need stable cohorts.
  - Already optimized pages are excluded from controls, and weak/missing matches are surfaced with warnings rather than hidden.
  - Control groups are explicitly comparison aids, not causal proof.
  - Validation timelines are computed from the ledger for now; J+7 is weak, J+30 is first serious review, J+60 is more reliable and J+90 is full conclusion.
  - Low-volume elapsed windows become `inconclusive` rather than forcing a positive/negative reading.
  - Existing `measurement_status`, `metrics_after` or `observed_impact` can mark a due window as ready.
- **Validations run:**
  - `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — 75/75 ✅
  - `pytest tests/test_geo/test_validation_timeline.py tests/test_api/test_geo.py` — 30/30 ✅
  - `pytest tests/test_geo/test_control_groups.py tests/test_api/test_geo.py` — 27/27 ✅
  - `pytest tests/test_geo/test_ledger.py tests/test_geo/test_event_tracking.py tests/test_geo/test_optimization_snapshots.py tests/test_api/test_geo.py` — 31/31 ✅
  - `ruff check app/geo app/api/geo.py app/db.py tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` ✅
  - `ruff check .` ✅
  - `cd shopify-app && npm run typecheck` ✅
  - `cd shopify-app && npm run build` ✅
  - `ruff check .` ✅
  - `cd shopify-app && npm run typecheck` ✅
  - `cd shopify-app && npm run build` ✅
  - `ruff check .` ✅
  - `cd shopify-app && npm run typecheck` ✅
  - `cd shopify-app && npm run build` ✅
- **Validations skipped:** Full `pytest` was not run; the change was covered by targeted backend/API tests plus global ruff and TypeScript build validation.
- **Next recommended step:** Task 120 — Progress Curve Dashboard: display GEO score, impressions, clicks, CTR, position, conversions, revenue and estimated vs observed impact curves.

## Open decisions

| Decision | Status | Context | Recommended next step |
|---|---|---|---|
| Phase 11.5 placement | Closed | Phase 11.5 is now official in `PROGRESS.md`, with tasks 116-119 done. | Continue with task 120. |
| Add a shared Claude Bash validation hook | Open | `.claude/settings.json` is intentionally minimal because no safe shared script was confirmed. | Add a repo-owned script such as `scripts/validate-command.sh` only if it is non-destructive and works for all contributors. |
| Exact validation matrix for every task | Open | Full validation exists but can be long. | Define task-specific validation groups in `docs/COMMANDS.md` over time. |

## Known risks

| Risk | Impact | Mitigation |
|---|---|---|
| Shopify writes during pilot or production work | Can mutate merchant data. | Keep dry-run default, require explicit confirmation and respect `LEONIE_PILOT_SAFE_MODE`. |
| GEO content hallucination | Can publish false product claims. | Use confirmed facts only, separate merchant suggestions from confirmed facts, and keep review mandatory before any future write. |
| OAuth, billing, webhooks or scopes changed casually | Can break install, billing, compliance or App Store readiness. | Require a plan and targeted validation before changes. |
| Long roadmap history hides current state | Agents may work on stale tasks. | Read `PROGRESS.md`, `ROADMAP.md` and this file before meaningful work. |

## Useful commands

| Purpose | Command |
|---|---|
| Install Python package | `pip install -e .` |
| Install Python dev dependencies | `pip install -e .[dev]` |
| CLI help | `leonie-seo --help` |
| Backend dev server | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Python lint | `ruff check .` |
| Python tests | `pytest` |
| Shopify app install | `cd shopify-app && npm install` |
| Shopify app dev | `cd shopify-app && npm run dev` |
| Shopify Remix dev | `cd shopify-app && npm run web` |
| Shopify typecheck | `cd shopify-app && npm run typecheck` |
| Shopify build | `cd shopify-app && npm run build` |
| Docker build | `docker build -t leonie-seo .` |
