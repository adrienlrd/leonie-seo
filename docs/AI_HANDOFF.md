# AI_HANDOFF.md — Léonie SEO

## Current project state

- **Summary:** Léonie SEO est une app Shopify embedded + moteur Python/FastAPI/CLI pour audit SEO, recommandations supervisées, contenus, données structurées, jobs async, intégrations Shopify/Google/LLM et garde-fous dry-run.
- **Main stack:** Python 3.11+, FastAPI, Click, pytest, ruff, Remix, React, TypeScript, Shopify App Bridge, Shopify Polaris, npm.
- **Main working areas:** `app/`, `scripts/`, `shopify-app/`, `config/`, `docs/`, `tests/`.
- **Current roadmap:** Phase 10 clôturée. Phase 11 terminée. Phase 11.5-11.8 complètes. **Phase 11.9 complète (12/12 tâches 152-163 ✅, terminée 2026-05-21).** **Phase 12 (tâches 150-151) démarre seulement après test 3 marchands pilotes (critère humain — `docs/pilot-merchant-test-script.md`).**
- **Known limitations:** Les workflows GEO restent majoritairement read-only. La mesure pilote garde des lacunes historiques sur IDs/durées de jobs, compteurs exacts, coût LLM et suivi fin de certains jobs. Les snapshots V1 ne capturent pas encore GA4 ni JSON-LD détaillé. Crawl L3 existe côté backend/API, mais les plafonds Free/Pro/Agency ne sont pas encore appliqués par plan. Niche Understanding est disponible — les modules aval consomment l'hypothèse via gate UX (app._index.tsx + app.priorities.tsx) mais pas encore via appel backend automatique.

## Last completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** 3ᵉ run réel : le harnais reciblait le head term `harnais chien` (27 100/mois) car DataForSEO renvoyait `difficulty=0`/absente (difficulty_source=free_estimated) → le volume énorme gagnait faute de difficulté réelle.
- **Summary:** (1) Quand la difficulté réelle est absente, `_keyword_priority_score` l'**infère du volume** : demande ≥85 → −25, ≥75 → −12 (un head term à fort volume est forcément concurrentiel ; la faible concurrence Ads n'est pas un proxy de difficulté SEO). (2) Le cache ne stocke plus les payloads entièrement vides (None) → une difficulté temporairement omise n'est plus figée 60 j. Vérifié sur l'export réel : les primaries deviennent `harnais chien cuir`, `fontaine à eau inox sans fil pour chat`, `pull en cachemire pour chien`. Les correctifs fontaine du commit précédent sont confirmés (intent « filtre » rétrogradé, confidence normalisée).
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `app/market_analysis/providers/dataforseo_provider.py`, `tests/market_analysis/test_keyword_pool.py`, `tests/market_analysis/test_keyword_cache.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Inférer la difficulté du volume quand DataForSEO ne la fournit pas (robustesse). Ne jamais cacher un résultat all-None.
- **Validations run:** `pytest` complet — 1601 ✅ ; recomputation sur l'export réel confirmant les nouveaux primaries ; `ruff check` (fichiers modifiés) ✅.
- **Open issues:** DataForSEO renvoie souvent `difficulty` absente (difficulty_source=free_estimated) — la difficulté réelle serait préférable ; l'inférence par volume est un garde-fou. GSC toujours absent.
- **Next recommended action:** Re-exporter une analyse et confirmer en réel que les primaries sont bien les mid-tail spécifiques.
- **Suivi 2026-05-29 :** 4ᵉ run confirme les bons primaries (`harnais chien cuir`, `fontaine à eau inox sans fil pour chat`, `pull en cachemire pour chien`). Ajout d'un nettoyeur `_clean_keyword_query` (retire un préfixe parasite LLM type « new: » des requêtes) appliqué au coerce + à la fusion Pass 1. `pytest` 1604 ✅.

## Previous completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** Rendre les coûts DataForSEO soutenables en multi-shop (app publique) sans dépendance externe — abandon de l'idée Google Ads API (friction quotas/compliance/migrations, volumes en fourchettes) au profit d'un cache de mots-clés partagé entre shops.
- **Summary:** Nouveau cache partagé `keyword_data_cache` (clé `data_type+location+language+mot-clé`, **sans scope shop** car la donnée marché est identique pour tous les shops) avec TTL différencié (volume/difficulté 60 j, SERP/PAA 10 j). `DataForSEOProvider.enrich()` et `fetch_serp_intelligence()` consultent le cache d'abord et n'appellent l'API que pour les manques → le 1ᵉʳ shop d'une niche paie, les suivants/reruns lisent le cache. Accès cache « fail-open » (une erreur de cache ne casse jamais l'enrichissement). Décision : Google Ads API abandonnée (cf. analyse multi-tenant).
- **Files created:** `app/market_analysis/keyword_cache.py`, `tests/market_analysis/test_keyword_cache.py`.
- **Files modified:** `app/db.py` (table SQLite + Postgres), `app/market_analysis/providers/dataforseo_provider.py` (cache + `cache_db_path` pour isolation tests), `tests/market_analysis/test_dataforseo_cost.py` (isolation cache), `tests/market_analysis/test_keyword_pool.py` (tests qualité/trafic), `docs/AI_HANDOFF.md`.
- **Decisions made:** Cache partagé entre shops (pas par-shop) = vrai levier de coût multi-tenant. GSC reste par-shop (1ʳᵉ partie). Abandon Google Ads API. Cache best-effort (jamais bloquant).
- **Validations run:** `pytest` complet — 1599 ✅ (dont 6 tests cache : hit/miss, partage cross-shop, dédup mot-clé partagé entre produits, TTL expiré, fail-open, SERP caché ; + 2 tests qualité : réel > estimé IA, primary = réel) ; `ruff check` ✅.
- **Validations skipped:** Frontend inchangé ; pas de run live (cache vérifié uniquement par tests mockés).
- **Open issues:** GSC toujours absent des sources (à reconnecter/alimenter). Cache des idées DataForSEO et competitors_domain non mis en cache (variabilité plus forte) — possible si besoin. Pas encore de purge/éviction des entrées expirées (lecture filtrée par `expires_at`, suffisant).
- **Next recommended action:** Relancer plusieurs analyses (même niche, 2 shops) et vérifier la chute des appels DataForSEO + la cohérence des métriques entre runs/produits.

## Previous completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** Optimisation coût DataForSEO + correctifs issus d'un 2ᵉ run réel (la fontaine avait dérivé vers des mots-clés « filtre » = mauvaise intention).
- **Summary:** (1) Coupé l'endpoint coûteux `keywords_data/google_ads/search_volume/live` (~10x le coût des endpoints Labs, redondant avec `keyword_ideas` qui renvoie déjà le volume) — désactivé par défaut, réactivable via `DATAFORSEO_SEARCH_VOLUME_ENABLED=true` ; la difficulté Labs continue. (2) `_keyword_priority_score` : ne fait confiance à la difficulté que si réelle (`difficulty_source=dataforseo`), sinon neutre (50) — évite qu'une difficulté estimée fasse un faux bonus/pénalité. (3) Garde d'intention : pénalité (−20) si la requête contient un marqueur accessoire/consommable (`filtre`, `recharge`, `pièce`, `pompe`…) absent du produit → le primary reste sur le produit, pas sur une pièce détachée ; règle ajoutée au prompt Pass 1. (4) Identification produit en température 0 + json_mode → labels stables → seeds DataForSEO stables → moins de variance entre runs.
- **Files created:** `tests/market_analysis/test_dataforseo_cost.py`.
- **Files modified:** `app/market_analysis/providers/dataforseo_provider.py`, `app/market_analysis/engine.py`, `app/market_analysis/identifier.py`, `tests/market_analysis/test_keyword_pool.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder DataForSEO Labs (idées/difficulté/SERP) comme base pas chère ; le volume Google Ads exact devient opt-in. Pénalité accessoire plutôt que filtrage dur (le terme reste utile en contenu support).
- **Validations run:** `pytest` complet — 1591 ✅ ; `ruff check`/`format` ✅.
- **Validations skipped:** Frontend inchangé ; pas de run live (à vérifier sur prochaine analyse pilote).
- **Open issues:** Variance entre runs réduite mais à reconfirmer. Google Ads API (volume gratuit) non branchée (stub) — nécessite un developer token côté marchand. GSC toujours absent des sources.
- **Next recommended action:** Relancer l'analyse fontaine, vérifier que le primary cible la fontaine (pas « filtre ») et que les runs sont stables. Puis décider du branchement Google Ads API.

## Previous completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** Ajustements post-évaluation d'un run réel (3 produits, ~0,40 $ DataForSEO) : (1) le mot-clé principal visait des head terms ingagnables (ex. « harnais chien » diff 90, 27 100/mois) au lieu de mid-tail spécifiques gagnables ; (2) `confidence` GEO parfois en français (« élevée ») ; (3) clarifier le plafond produits et le score d'opportunité figé à 15.
- **Summary:** (1) `_keyword_priority_score` rééquilibré : difficulté plus pondérée (0.25), pénalité forte pour difficulté ≥85 (−25) et ≥70 (−12), bonus de spécificité pour les requêtes mid/longue-traîne qui collent au produit → le primary devient un mid-tail gagnable (ex. « harnais chien cuir », « fontaine eau chat sans fil »). (2) Nouveau `_normalize_confidence` (FR/variantes → high/medium/low) appliqué aux geo_questions et au confidence du content pack/produit. (3) Plafond : le job d'analyse complète tourne avec `max_products=0` (aucune limite) — les « 3 produits » = la taille réelle du catalogue actif, pas un cap. `total_opportunity_count` (34) = somme mots-clés+questions, pas un nombre de produits. Score d'opportunité figé à 15 = comportement attendu (balises SEO déjà correctes, GA4 sans trafic) ; ajout d'un bonus gradué selon le volume de sessions GA4 pour différencier les produits dès qu'il y a du trafic.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `tests/market_analysis/test_keyword_pool.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne pas toucher au plafond (non-problème). Garder les head terms dans la liste (notoriété/blog) mais hors du rôle primary. Normaliser la confidence côté code plutôt que de se fier au prompt.
- **Validations run:** `pytest` complet — 1586 ✅ ; `ruff check`/`format` sur fichiers modifiés ✅.
- **Validations skipped:** Frontend inchangé ce tour (pas de typecheck/build relancés).
- **Open issues:** Vérifier sur un prochain run réel que le primary bascule bien vers les mid-tail spécifiques. GSC toujours absent des sources (peu/pas de trafic organique appairé) — à reconfirmer côté connexion GSC.
- **Next recommended action:** Relancer l'analyse, ré-exporter et vérifier que « harnais chien cuir » / « fontaine eau chat sans fil » deviennent primary.

## Previous completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** Fiabiliser l'algo d'analyse produit (analyse complète/profil/produits) : trop de mots-clés estimés par l'IA, peu de données concrètes, forte variance entre runs/produits, et opacité sur les mots-clés réellement utilisés.
- **Summary:** Le moteur `app/market_analysis/engine.py` passe d'un pipeline « IA d'abord » à « données réelles d'abord ». Avant tout appel LLM, un pool de mots-clés candidats RÉELS est construit par produit depuis GSC (requêtes appariées + impressions/clics/position), idées DataForSEO (volumes FR réels), Google Suggest (autocomplétion réelle + formes questions pour le GEO) et Google Trends. Le Pass 1 LLM ne « invente » plus : il SÉLECTIONNE/qualifie (intent, product_fit, role) depuis ce pool et peut ajouter au plus 2 longues traînes clairement marquées `llm_proposed`. Un plancher garantit que les meilleurs candidats réels ne sont jamais écartés silencieusement (réduit la variance). Les appels LLM passent en mode JSON déterministe (`response_format=json_object`, température 0 pour le ciblage). Côté UI, un panneau « Mots-clés ciblés & sources » affiche pour chaque mot-clé sa source (badge GSC/DataForSEO/Suggest/Trends/IA), son volume/impressions et les champs de contenu où il est réellement utilisé.
- **Files created:** `tests/market_analysis/test_keyword_pool.py`.
- **Files modified:** `app/market_analysis/engine.py`, `app/market_analysis/providers/free_provider.py` (préservation de la provenance), `app/llm/provider.py`, `app/llm/router.py`, `app/llm/providers/openai.py`, `app/llm/providers/groq.py`, `app/llm/providers/cloudflare.py`, `shopify-app/app/lib/marketAnalysisShared.tsx` (badge mutualisé + nouvelles sources), `shopify-app/app/components/ProductContentProposals.tsx` (panneau transparence), `shopify-app/app/routes/app.market-analysis.tsx`, `shopify-app/app/lib/i18n.ts`, plusieurs fakes de tests LLM (`tests/test_llm/*`, `tests/market_analysis/test_two_pass_engine.py`).
- **Decisions made:** (1) Les vraies sources (GSC/DataForSEO) priment sur l'estimation IA ; Suggest/Trends conservent leur provenance si aucune donnée plus forte ne les écrase. (2) Maximiser les données réelles (choix marchand) : idées DataForSEO + Suggest récupérées par produit, seedées sur les termes produit réels. (3) Plancher de mots-clés réels pour stabiliser les résultats entre deux analyses. (4) Mode JSON + température 0 sur le ciblage pour réduire la variance et les échecs de parsing.
- **Validations run:** `pytest` complet — 1583 ✅ ; `ruff check` sur fichiers modifiés ✅ ; `ruff format` ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Vérification visuelle dans une boutique Shopify embedded authentifiée non effectuée (nécessite session Shopify) — à faire sur boutique pilote.
- **Open issues:** Google Suggest est appelé par produit (délai 0,5 s/seed) : latence accrue sur gros catalogues en job de fond ; envisager un cache. Les 6 erreurs ruff I001 préexistantes dans `tests/market_analysis/test_jobs.py` ne sont pas corrigées (hors périmètre).
- **Next recommended action:** Lancer une `Analyse complète` sur boutique pilote, vérifier que le panneau « Mots-clés ciblés & sources » montre une majorité de sources réelles (GSC/DataForSEO/Suggest) et comparer deux runs du même produit pour confirmer la stabilité.

## Previous completed task

- **Date:** 2026-05-28
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter des étapes intermédiaires de validation dans l'analyse complète du dashboard.
- **Summary:** Le dashboard ne fait plus d'analyse complète totalement automatique. `Analyse complète` génère d'abord un profil entreprise/niche en brouillon, affiche les hypothèses modifiables (marque, niche, voix, concurrents, thèmes, insights concurrents, manques de contenu), puis attend une validation marchande avant de sauvegarder le profil et de lancer l'identification produits. L'identification produits s'arrête elle aussi sur un écran de correction "quel est le produit concrètement ?" par fiche, puis lance seulement ensuite l'analyse produits profonde avec Google/DataForSEO. `Analyse profil` utilise aussi la validation profil intermédiaire, et `Analyse produits` utilise la validation des produits avant l'analyse profonde. Le bloc Profil entreprise existant permet maintenant aussi d'éditer le nom de marque et les concurrents.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/lib/i18n.ts`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) L'orchestration reste côté Remix et réutilise les endpoints existants pour éviter un backend job composite prématuré. (2) L'étape 1 Profil et l'étape 1 Produits deviennent explicitement validées par le marchand avant toute analyse profonde. (3) Les labels produits corrigés sont sauvegardés avant `/market-analysis/jobs`, afin que la passe Google/DataForSEO et les propositions de contenu repartent des hypothèses validées.
- **Validations run:** `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; serveur local `cd shopify-app && npm run web -- --host 127.0.0.1 --port 3000` démarré ✅ ; tentative navigateur intégré sur `http://127.0.0.1:3000/app` bloquée par la politique navigateur de la session.
- **Validations skipped:** Tests Python non lancés car le changement est limité au dashboard Remix et aux textes i18n frontend. Vérification visuelle Shopify embedded non finalisée : l'accès navigateur local a été refusé et la route requiert habituellement une session Shopify.
- **Open issues:** La relance future "modifier seulement les hypothèses de l'étape 1 puis relancer uniquement l'étape 2" est partiellement couverte par les pauses avant lancement et par la sauvegarde des labels, mais il manque encore un vrai panneau persistant d'hypothèses validées avec bouton "relancer étape 2" sans refaire l'identification. Le serveur local de vérification a été lancé sur le port 3000 ; son arrêt par `kill` a été refusé par le sandbox.
- **Next recommended action:** Tester dans une boutique pilote authentifiée : Analyse complète → correction profil/concurrents → identification produits → correction labels → analyse produits, puis décider si un panneau persistant "Hypothèses validées" doit être ajouté à l'accueil ou à Analyse marché.

## Previous completed task

- **Date:** 2026-05-28
- **Agent:** Codex (GPT-5)
- **Goal:** Restaurer le parcours complet d'identification produits avant l'analyse produits depuis le dashboard d'accueil.
- **Summary:** Les boutons `Analyse complète` et `Analyse produits` de l'accueil ne lancent plus directement le job d'analyse produits. Ils démarrent maintenant par `/market-analysis/identify`, pollent ce job, sauvegardent les labels d'identification dans `/market-analysis/identifications`, puis lancent seulement ensuite `/market-analysis/jobs`. Cela aligne le dashboard sur le flux fiable d'Analyse marché et évite que les propositions de contenu partent d'une compréhension produit plus pauvre avant l'enrichissement Google/DataForSEO.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/lib/i18n.ts`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) Garder les trois boutons distincts sur l'accueil, mais faire passer `Analyse complète` et `Analyse produits` par l'étape d'identification produits. (2) Ne pas ajouter un job composite backend pour cet incrément : l'orchestration Remix réutilise les endpoints existants et éprouvés. (3) Ajouter des statuts UI séparés pour distinguer l'analyse profil, l'identification produits et l'analyse produits.
- **Validations run:** `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Tests Python non lancés car le changement est limité à l'orchestration Remix du dashboard et aux libellés i18n frontend.
- **Open issues:** Le mode `Analyse complète` auto-sauvegarde toujours le profil généré avant l'analyse produits ; pour une correction manuelle avant validation, le bouton `Analyse profil` reste le chemin à utiliser. Un futur assistant "première analyse" pourrait afficher explicitement l'étape de vérification avant de lancer l'analyse produits.
- **Next recommended action:** Relancer une `Analyse complète` sur boutique pilote et comparer les propositions Analyse marché avec le flux manuel `Analyse marché` pour confirmer que les produits identifiés, mots-clés, PAA et signaux DataForSEO sont de nouveau cohérents.

## Previous completed task

- **Date:** 2026-05-28
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter trois actions explicites sur l'accueil : analyse complète, analyse profil et analyse produits.
- **Summary:** L'accueil dispose maintenant d'un panneau `Analyses` avec trois boutons distincts. `Analyse complète` lance l'analyse Profil entreprise, sauvegarde le profil généré comme profil validé pour que le contexte soit immédiatement utilisable, puis lance l'analyse de tous les produits. `Analyse profil` conserve le comportement séparé : génération d'un profil brouillon affiché dans le bloc Profil entreprise pour vérification/validation. `Analyse produits` lance uniquement l'analyse globale des produits avec le profil actuellement validé. Le panneau affiche les états de progression et les résultats sans recharger la page.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/lib/i18n.ts`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) L'analyse complète est volontairement orchestrée sur l'accueil pour éviter d'ajouter un nouveau backend job composite. (2) Le mode complet auto-sauvegarde le profil généré afin que l'analyse produits utilise réellement le nouveau contexte global. (3) Les boutons profil et produits restent séparés pour les relances quotidiennes ciblées.
- **Validations run:** `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Tests Python non lancés car le changement est limité à la route Remix d'accueil et aux libellés i18n frontend.
- **Open issues:** L'analyse complète n'inclut pas encore une étape intermédiaire d'ajustement manuel avant la sauvegarde automatique du profil ; le bouton profil séparé reste le chemin à utiliser quand le marchand veut corriger avant validation.
- **Next recommended action:** Valider visuellement dans une session Shopify embedded que les trois boutons sont compréhensibles et que les états de progression restent lisibles pendant les deux jobs enchaînés.

## Previous completed task

- **Date:** 2026-05-28
- **Agent:** Codex (GPT-5)
- **Goal:** Réduire le risque qu'une analyse produits reste invisible lorsqu'elle a été générée avec une ancienne version du Profil entreprise.
- **Summary:** Ajout d'un contexte business versionné pour Analyse marché. Le backend calcule maintenant un hash SHA-256 déterministe à partir des champs stratégiques du profil entreprise validé, sans inclure `generated_at`, puis stocke ce contexte au niveau de l'analyse globale et de chaque produit. L'API `/market-analysis/latest` compare le hash stocké au profil actuel et retourne un statut `current`, `stale`, `unknown` ou `missing_profile`, y compris produit par produit. L'interface Analyse marché affiche un badge de fraîcheur dans le résumé, un badge par carte produit en cas de contexte ancien/non versionné, et une bannière actionnable si le profil a changé ou si une ancienne analyse n'est pas versionnée.
- **Files created:** `app/business_profile/context.py`, `tests/business_profile/test_context.py`.
- **Files modified:** `app/api/market_analysis.py`, `app/market_analysis/engine.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/market_analysis/test_two_pass_engine.py`, `tests/test_api/test_market_analysis.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) Le hash ne couvre que les champs qui influencent vraiment l'analyse produit : marque, niche, voix, personas, style éditorial, thèmes, concurrents, insights, content gaps et maillage. (2) `generated_at` reste stocké en métadonnée mais exclu du hash pour éviter une alerte stale quand seul le timestamp change. (3) Les anciennes analyses sans hash sont signalées `unknown` plutôt que forcées en `stale`, afin d'indiquer que la version exacte n'est pas reconstructible. (4) Les analyses mono-produit portent aussi leur hash, mais l'état global reste stale si l'ensemble de l'analyse n'a pas été régénéré avec le profil actuel.
- **Validations run:** `ruff format app/business_profile/context.py app/market_analysis/engine.py app/api/market_analysis.py tests/business_profile/test_context.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py` ✅ ; `ruff check app/business_profile/context.py app/market_analysis/engine.py app/api/market_analysis.py tests/business_profile/test_context.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/business_profile/test_context.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py` **24 passed** ✅ ; `pytest` **1576 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Vérification visuelle embedded Shopify non lancée : nécessite une session Shopify authentifiée ; le build Remix valide le rendu typé de la bannière et du badge.
- **Open issues:** Le parcours "première analyse" n'est pas encore un assistant unifié complet ; les boutons restent distincts, mais la fraîcheur du contexte est maintenant visible et mesurable.
- **Next recommended action:** Définir l'orchestration UX du premier jour : prévisualisation/édition des données connues → validation profil global → analyse produits, en conservant ensuite les relances séparées pour profil global et produits.

## Previous completed task

- **Date:** 2026-05-28
- **Agent:** Codex (GPT-5)
- **Goal:** Fusionner les besoins et données entre Profil entreprise & niche et Analyse marché afin de créer une boucle stratégique : profil global → analyse produits → profil global enrichi.
- **Summary:** L'analyse produit consomme désormais le profil entreprise validé comme contexte stratégique officiel : marque, niche, voix, personas, style éditorial, thèmes, vocabulaire, concurrents, insights, content gaps et priorités de maillage sont injectés dans les prompts Pass 1 et Pass 2. En retour, la régénération du Profil entreprise lit la dernière Analyse marché pour remonter mots-clés, questions GEO/PAA, produits prioritaires, concurrents et manques de contenu/faits observés. L'UI Accueil signale cette boucle avec un message marchand et un badge quand le profil est enrichi par l'analyse produits. Aucun push Shopify n'est ajouté ; le flux reste lecture seule côté Analyse marché.
- **Files created:** `tests/business_profile/test_market_context.py`.
- **Files modified:** `app/api/market_analysis.py`, `app/business_profile/analyzer.py`, `app/market_analysis/engine.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app._index.tsx`, `tests/market_analysis/test_two_pass_engine.py`, `tests/test_api/test_market_analysis.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) L'analyse produit utilise uniquement le profil entreprise validé (`business_profile.json`) pour ne pas propager un brouillon non accepté. (2) Les signaux issus des produits enrichissent la prochaine analyse globale comme observations de marché, sans modifier automatiquement un profil validé. (3) Le contexte global peut orienter voix, angles, différenciation, maillage et sujets support, mais ne peut jamais créer des faits produit non confirmés. (4) Les boutons existants restent distincts : régénération globale pour recalibrer, analyse produits pour exploiter le profil validé et collecter de nouveaux signaux.
- **Validations run:** `ruff format app/market_analysis/engine.py app/api/market_analysis.py app/business_profile/analyzer.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py tests/business_profile/test_market_context.py` ✅ ; `ruff check app/market_analysis/engine.py app/api/market_analysis.py app/business_profile/analyzer.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py tests/business_profile/test_market_context.py` ✅ ; `pytest tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py tests/business_profile/test_market_context.py` **19 passed** ✅ ; `pytest` **1570 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Vérification visuelle embedded Shopify non lancée : nécessite une session Shopify authentifiée ; le changement UI est limité à une bannière, un badge et des textes i18n sur l'accueil / Analyse marché.
- **Open issues:** Le “premier jour” reste encore réparti entre les actions existantes ; l'orchestration UX complète Analyse globale → validation → analyse produits pourra être renforcée ensuite avec une action unifiée ou un état de parcours. Les signaux observés remontent dans le prompt global mais ne sont pas encore stockés comme objet versionné séparé avec diff d’évolution du profil.
- **Next recommended action:** Ajouter un objet `market_context_version` / `business_profile_context_hash` aux analyses produits pour afficher quand les propositions ont été générées avec un ancien profil global, puis proposer une réanalyse ciblée.

## Previous completed task

- **Date:** 2026-05-27
- **Agent:** Codex (GPT-5)
- **Goal:** Permettre au marchand de compléter rapidement les preuves manquantes afin de générer une FAQ ou un article support SEO/GEO auparavant bloqué.
- **Summary:** Lorsqu'une proposition n'a pas assez de faits ou d'intention pour générer FAQ/GEO/article, la carte affiche maintenant un avertissement avec l'action `Compléter pour générer`. Elle ouvre jusqu'à quatre questions simples fondées sur le mot-clé primaire et, lorsque disponible, la question PAA : garantie, compatibilité/dimensions/entretien, besoin utilisateur et critères de choix. Les réponses non vides sont enregistrées comme faits `merchant_confirmation`, relancent l'analyse uniquement pour le produit concerné et remplacent sa proposition persistée. Le moteur peut alors débloquer FAQ/GEO avec un fait confirmé marchand et l'article support avec un cas d'usage ou des critères confirmés ; la validation bloque désormais toute FAQ ou tout article généré qui ne couvre pas le mot-clé primaire. Aucun endpoint de ce parcours n'écrit vers Shopify.
- **Files created:** `tests/market_analysis/test_merchant_facts.py`.
- **Files modified:** `app/market_analysis/jobs.py`, `app/api/market_analysis.py`, `app/market_analysis/engine.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/market_analysis/test_two_pass_engine.py`, `tests/test_api/test_market_analysis.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) Les questions reprennent la cible keyword sélectionnée afin que la réponse serve réellement la FAQ ou l'article support. (2) Une réponse marchande explicite devient un fait confirmé de génération, mais elle ne constitue pas un push Shopify. (3) L'article support ne se débloque par questionnaire que si le marchand fournit un angle utile confirmé (`use_cases` ou `selection_criteria`). (4) La régénération déclenchée par questionnaire est persistée dans la dernière analyse pour ne pas imposer une seconde action au marchand. (5) Le bouton existant `Modifier` est conservé.
- **Validations run:** `ruff format app/market_analysis/jobs.py app/api/market_analysis.py app/market_analysis/engine.py tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_merchant_facts.py tests/test_api/test_market_analysis.py` ✅ ; `ruff check app/market_analysis/jobs.py app/api/market_analysis.py app/market_analysis/engine.py tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_merchant_facts.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_merchant_facts.py tests/test_api/test_market_analysis.py tests/test_geo/test_facts.py tests/test_content_actions/test_runner.py tests/apply/test_apply_faq.py` **36 passed** ✅ ; `pytest` **1554 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅ ; vérification locale tentée sur `/app/market-analysis`.
- **Validations skipped:** L'inspection visuelle complète de l'avertissement et du questionnaire n'a pas pu être réalisée : la route locale protégée redirige vers `/auth/login` sans session Shopify embarquée et affiche l'avertissement d'authentification déjà identifié. `ruff check .` a été exécuté mais échoue sur six erreurs préexistantes dans `tests/market_analysis/test_jobs.py`, non modifié pour cette fonctionnalité.
- **Open issues:** La vérité des réponses dépend toujours du marchand ; le moteur empêche l'invention automatique mais ne peut pas prouver une déclaration saisie sans document externe. Le mode de publication `manual` / `automatic`, les snapshots Shopify et le rollback restent à implémenter avant tout auto-push. L'avertissement local d'authentification Shopify limite le QA visuel hors boutique installée.
- **Next recommended action:** Brancher le futur `publication_mode` sur `content_quality.publish_ready` avec snapshot et rollback, puis valider le parcours questionnaire dans une boutique pilote authentifiée.

## Previous completed task

- **Date:** 2026-05-27
- **Agent:** Codex (GPT-5)
- **Goal:** Renforcer automatiquement la génération SEO/GEO d'Analyse marché à partir des recommandations Google récentes : preuves factuelles, abstention de contenu générique et prévention des conflits de ciblage.
- **Summary:** Le moteur réutilise désormais `app.geo.facts.analyze_product_facts()` pour injecter une liste fermée de faits Shopify confirmés dans le prompt de contenu. Le LLM doit retourner `claims_used` et chaque affirmation est résolue dans un `evidence_ledger` déterministe ; la publication future est bloquée si une preuve est absente, si une promesse sensible non supportée apparaît, si une formulation interdite de la niche est utilisée ou si le texte est trop générique. Un `surface_plan` décide automatiquement de générer ou non description, FAQ, réponse GEO et article support : une fiche pauvre ou sans PAA/intention informationnelle ne déclenche plus de contenu de remplissage. Enfin, le gate bloque les doublons de metadata, les descriptions quasi dupliquées et la seconde proposition visant une cible primaire déjà attribuée à une page plus prioritaire. L'UI expose preuves, surfaces volontairement non générées, avertissements non bloquants et nouvelles raisons de refus.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/market_analysis/test_two_pass_engine.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) La validation avant futur mode automatique est déterministe : les claims doivent référencer des faits Shopify confirmés et non la seule déclaration libre du LLM. (2) Les mots-clés orientent l'intention mais ne justifient jamais une affirmation produit. (3) FAQ, GEO et blog ne sont plus des sorties obligatoires ; le moteur s'abstient lorsque les faits ou l'intention ne suffisent pas. (4) Aucun push Shopify ni réglage `publication_mode` n'est ajouté dans cet incrément ; le gate est renforcé avant de brancher une publication complète et réversible.
- **Validations run:** `ruff check app/market_analysis/engine.py app/api/market_analysis.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/market_analysis tests/test_api/test_market_analysis.py tests/test_geo/test_facts.py tests/test_content_actions/test_runner.py tests/apply/test_apply_faq.py` **37 passed** ✅ ; `pytest` **1548 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅ ; navigation locale tentée sur `/app/market-analysis` et redirigée vers `/auth/login` sans session Shopify.
- **Validations skipped:** La vérification visuelle complète de la carte Analyse marché n'est pas possible sans session embedded Shopify authentifiée. Le lint élargi incluant `tests/market_analysis` échoue sur six violations préexistantes dans `tests/market_analysis/test_jobs.py`, fichier non modifié dans cette tâche.
- **Open issues:** La détection automatique des promesses non prouvées couvre les catégories sensibles explicites mais ne remplace pas une vérification sémantique exhaustive de toute phrase libre. La navigation locale révèle un avertissement Shopify sur `shopify.authenticate.admin()` depuis `/auth/login`, hors périmètre de ce changement. Le mode `manual` / `automatic`, la publication multi-surface, le snapshot et le rollback doivent encore être implémentés avant auto-push réel.
- **Next recommended action:** Implémenter la couche unique de publication `publication_mode` en exigeant `content_quality.publish_ready`, puis snapshot/appliquer/mesurer/rollback pour meta, description et blocs compatibles Shopify.

## Previous completed task

- **Date:** 2026-05-27
- **Agent:** Codex (GPT-5)
- **Goal:** Améliorer l'algorithme de création de contenu Analyse marché pour préparer les modes de publication manuel/automatique tout en conservant l'édition marchande.
- **Summary:** Le moteur classe désormais les keywords finaux après enrichissement et ajout des idées DataForSEO, attribue des rôles `primary` / `secondary` / `supporting`, puis collecte SERP/PAA sur les cibles réellement retenues. Le pack de contenu reçoit un gate déterministe `content_quality.publish_ready` couvrant meta title, meta description, description, FAQ/PAA, bloc GEO, trace de preuves et confiance. Le prompt interdit les bénéfices et angles concurrents non confirmés. L'UI conserve `Modifier`, affiche cibles, score, preuve SERP/PAA, couverture par champ et gate de publication, puis invalide le gate après édition. La synchronisation FAQ Shopify implicite a été supprimée lors de l'analyse et de la sauvegarde : aucun push n'a lieu sans une future politique de publication explicite.
- **Files created:** `tests/test_api/test_market_analysis.py`.
- **Files modified:** `app/api/market_analysis.py`, `app/market_analysis/engine.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/market_analysis/test_two_pass_engine.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** (1) Ne pas implémenter un mode `automatic` partiel limité à la FAQ ; le futur mode devra publier toutes les surfaces via une couche unique et vérifier `content_quality.publish_ready`. (2) Conserver le bouton `Modifier`, mais toute édition rend la proposition non éligible à publication automatique jusqu'à revalidation. (3) Utiliser le score `0.45 x demand + 0.20 x (100 - competition) + 0.35 x product_fit`, avec un léger bonus de preuve réelle.
- **Validations run:** `ruff check app/market_analysis/engine.py app/api/market_analysis.py tests/market_analysis/test_two_pass_engine.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/market_analysis tests/test_api/test_market_analysis.py tests/apply/test_apply_faq.py` **19 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** La vérification visuelle de la route locale via le navigateur intégré a été tentée, mais bloquée avant rendu par `net::ERR_BLOCKED_BY_CLIENT`. `ruff check .` a été tenté mais échoue sur des violations préexistantes dans `tests/market_analysis/test_jobs.py`, non modifié dans cette tâche.
- **Open issues:** Le sélecteur de mode `manual` / `automatic` et la publication complète meta/description/FAQ/article ne sont pas encore implémentés. L'incrément actuel expose le gate nécessaire et supprime l'écriture implicite FAQ. Une édition marchande invalide le gate ; une action de revalidation devra être branchée au workflow de publication.
- **Next recommended action:** Implémenter un réglage marchand `publication_mode` (`manual` / `automatic`) et une couche d'application unique : en `manual`, préparer le push ; en `automatic`, publier uniquement les packs `content_quality.publish_ready`, avec snapshot/rollback pour chaque champ.

## Previous completed task

- **Date:** 2026-05-25
- **Agent:** Claude Code (claude-opus-4-7)
- **Goal:** Analyse marché — pipeline LLM à 2 passes pour alimenter les propositions de contenu avec les données réelles (volumes DataForSEO, concurrents SERP, questions PAA, crawl).
- **Summary:** Avant, le `content_test_pack` était généré par 1 seul appel LLM par produit qui ne voyait aucune des données coûteuses (récupérées seulement après, pour enrichir l'affichage des scores). Refonte de `run_market_analysis` en pipeline phasé : **Passe 1 (ciblage)** → le LLM produit compréhension + mots-clés candidats, enrichis (GSC + DataForSEO volumes/difficulté) ; **batch global** → 1 appel SERP intelligence plafonné (`_SERP_MAX_KEYWORDS`) qui capture désormais les questions PAA (auparavant jetées), + keyword ideas + concurrents ; **Passe 2 (contenu)** → le LLM rédige le pack en connaissant volumes réels, angles concurrents SERP, questions PAA et `crawl_findings` (jusque-là chargés mais inutilisés). Ajout d'une garde budget LLM (absente jusqu'ici dans ce moteur) : si budget dépassé → Passe 2 sautée, mots-clés conservés sans contenu (dégradation gracieuse, pattern `priorities/engine.py`). Mode gratuit (sans DataForSEO) : Passe 2 tourne quand même sans blocs SERP/PAA. UI : sous-libellé de phase sous la barre de progression.
- **Files created:** `tests/market_analysis/__init__.py`, `tests/market_analysis/test_two_pass_engine.py`, `tests/market_analysis/test_dataforseo_serp_intelligence.py`.
- **Files modified:** `app/market_analysis/engine.py` (split prompts `_build_pass1_prompt`/`_build_pass2_prompt`, `_PASS1_KEYS`/`_PASS2_KEYS`, helpers `_complete_json`/`_extract_product_fields`/`_crawl_for_handle`, budget `_PLAN_BUDGETS_USD`, restructuration phasée), `app/market_analysis/providers/dataforseo_provider.py` (ajout `fetch_serp_intelligence` + `_parse_serp_intelligence`, additif), `app/api/market_analysis.py` (threading `plan`, `phase` dans le callback `_on_progress`), `shopify-app/app/routes/app.market-analysis.tsx` (champ `phase` + sous-libellé), `shopify-app/app/lib/i18n.ts` (2 clés FR+EN).
- **Validations run:** `ruff check .` ✅ ; `pytest tests/market_analysis tests/test_geo tests/test_priorities tests/test_observability` **146 passed** ✅ ; `npm run typecheck` ✅ (seul warning préexistant : dépréciation `baseUrl` dans tsconfig) ; `npm run build` ✅.
- **Validations skipped:** `pytest` complet non lançable dans ce conteneur — `cryptography.hazmat.bindings._rust` (lib native) provoque `pyo3_runtime.PanicException` à la collection des modules utilisant le TestClient FastAPI / JWT. Problème d'environnement, sans rapport avec ce changement (vérifié : l'import du moteur fonctionne, seuls les modules à crypto échouent).
- **Decisions made:** (1) `_PLAN_BUDGETS_USD["free"] = 2.0` au lieu de 0.0 prévu au plan — sinon `check_budget` reporterait toujours over-budget pour les boutiques free et sauterait la Passe 2, régression où free n'aurait plus de contenu du tout. (2) Architecture phasée (pas interleaved) pour conserver le cap de coût SERP global existant. (3) Prompts gardés hardcodés (pas de migration YAML) — diff focalisé. (4) `plan` passé en query param optionnel ; sans valeur → budget par défaut 20 USD (cohérent avec le billing encore provisoire).
- **Open issues:** Le `plan` n'est pas encore transmis par le frontend (query param optionnel non utilisé côté Remix) → budget par défaut en pratique. Le coût LLM double (2 appels/produit) ; surveiller la consommation réelle sur les boutiques pilotes. La barre de progression reste à 0 % pendant la Passe 1 (cartes mots-clés visibles) puis avance en Passe 2 — vérifier le ressenti UX dans l'app réelle.
- **Next recommended action:** Test manuel dans l'app Shopify pilote (DataForSEO activé) : confirmer que la FAQ générée reprend des questions PAA et que les descriptions citent les volumes/angles réels. Décider si `plan` doit être câblé depuis le billing pour activer la garde budget par palier.

## Previous completed task

- **Date:** 2026-05-23
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Page expérimentale "Analyse marché" — V1 lecture seule (SEO/GEO par produit actif).
- **Summary:** Ajout complet de la fonctionnalité "Analyse marché" : moteur Python d'analyse LLM par produit actif, endpoint FastAPI POST, route Remix avec `useFetcher`, affichage Polaris (DataTable keywords SEO, questions GEO, propositions contenu, faits manquants, FAQ, blog). Plusieurs bugs corrigés en post-déploiement : `_coerce_list()` pour normaliser REST vs GraphQL Shopify, fallback gracieux si LLMError, scorer léger sans ML pour éviter l'OOM sur Render 512MB, timeout 180s côté Remix. L'analyse fonctionne en production (3 produits, 200 OK confirmé par le marchand).
- **Files created:** `app/market_analysis/__init__.py`, `app/market_analysis/engine.py`, `app/api/market_analysis.py`.
- **Files modified:** `app/main.py` (+1 import +1 include_router), `shopify-app/app/lib/i18n.ts` (+13 clés FR + 13 clés EN), `shopify-app/app/routes/app.market-analysis.tsx` (créé de zéro), `shopify-app/app/routes/app.insights.tsx` (+1 item HubGrid).
- **Validations run:** `ruff check .` ✅ ; `npm run typecheck` ✅ ; test manuel en production (200 OK, 3 produits analysés) ✅.
- **Validations skipped:** `pytest` non relancé — aucun test existant ne couvre le module market_analysis ; les tests Python core n'ont pas été modifiés.
- **Decisions made:** (1) Scorer léger `_score_active_products` (heuristiques de champs) à la place de `find_opportunities_for_catalog` (TF-IDF/K-means) → évite OOM Render 512MB. (2) `_coerce_list()` comme normaliseur universel pour les shapes REST (liste) et GraphQL (Connection) de Shopify. (3) `max_products=3` par défaut côté Remix pour rester sous le timeout 180s. (4) Merge vers `main` immédiat car Render déploie uniquement depuis `main`.
- **Open issues:** L'analyse est limitée à 3 produits par contrainte de timeout et RAM. Pour analyser plus, il faudrait un job async (POST → polling). La qualité des propositions LLM dépend de la complétude des données GSC/niche hypothesis.
- **Next recommended action:** Collecter le feedback marchand sur la qualité des propositions (mots-clés, questions GEO, textes) et décider si la V2 nécessite un job async pour couvrir plus de produits.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Tasks 155–163 — Phase 11.9 complete (Merchant Journey Unification & Friction Reduction).
- **Summary:** 8 documents canoniques créés + ajustements UX/i18n dans 5 routes Remix. i18n.ts : 22 nouvelles clés merchant-friendly + 12 clés existantes renommées (Valider, Prévisualiser, Publier, Refuser, statuts, types de contenu). app._index.tsx : Zone 1 CTA primary si niche non validée, badge niveau i18n, Zone 6 masquée. app.safe-apply.tsx : bannière sécurité permanente, labels merchant, boutons restructurés (primary: Valider/Publier, pas de tone critique). app.niche-understanding.tsx : "Analyser" passe en secondary. app.priorities.tsx : gain estimé badge + CTA "Préparer cette action". app.impact.tsx : Banner rétention en haut, section jalons déplacée avant les courbes, CTA NBA primary. launch-readiness.md + DECISIONS.md : §0 prérequis Phase 11.9 ajouté.
- **Files created:** `docs/dashboard-command-center.md`, `docs/cta-matrix.md`, `docs/merchant-language-glossary.md`, `docs/advanced-tools-strategy.md`, `docs/action-card-spec.md`, `docs/safe-apply-narrative.md`, `docs/impact-feedback-loop.md`, `docs/pilot-merchant-test-script.md`.
- **Files modified:** `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.safe-apply.tsx`, `shopify-app/app/routes/app.niche-understanding.tsx`, `shopify-app/app/routes/app.priorities.tsx`, `shopify-app/app/routes/app.impact.tsx`, `docs/launch-readiness.md`, `DECISIONS.md`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Python tests non relancés — aucun fichier Python modifié.
- **Decisions made:** Zone 2 gate garde le texte mais supprime le bouton primary (Zone 1 est le seul CTA primary quand niche non validée). `tone="critical"` retiré des boutons Publier/Valider dans safe-apply (remplacé par `variant="primary"`). Jalons rétention déplacés en haut de app.impact avant les courbes techniques pour prioriser la narration marchand.
- **Open issues:** Vérification visuelle dans l'app Shopify réelle recommandée (comportement `<Banner>` + badges `tone` en contexte Polaris embedded). Test utilisateur 3 marchands pilotes reste le seul critère bloquant pour Phase 12.
- **Next recommended action:** Planifier les 3 sessions test utilisateur marchands pilotes selon `docs/pilot-merchant-test-script.md`. Dès les 5 critères atteints → **tâche 150 — décision finale go/no-go App Store**.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** Task 154 — Unified Onboarding Flow.
- **Summary:** Création du document canonique `docs/unified-onboarding-flow.md` et simplification de `app.onboarding` en parcours principal 4 étapes : connecter Google, analyser la boutique avec l'IA, valider la compréhension IA, voir les 3 actions prioritaires. Les anciennes cartes checklist, jobs, GSC détaillé, PageSpeed et crawl restent disponibles derrière **Outils avancés**.
- **Files created:** `docs/unified-onboarding-flow.md`.
- **Files modified:** `ROADMAP.md`, `PROGRESS.md`, `shopify-app/app/routes/app.onboarding.tsx`, `docs/AI_HANDOFF.md`.
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Python tests non relancés car changement limité à Markdown et route Remix frontend.
- **Decisions made:** Réutiliser les routes existantes : `gsc_connect`, `/niche/understand`, `app.niche-understanding`, `app.priorities`. GA4, PageSpeed et crawl restent non bloquants et repliés.
- **Open issues:** Vérification visuelle dans l'app Shopify réelle utile pour confirmer le rendu du `<details>` Polaris autour des outils avancés.
- **Next recommended action:** Démarrer la tâche 155 — Dashboard as Single Command Center.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** Task 153 — Niche Understanding as Mandatory Gate.
- **Summary:** Création du document canonique `docs/niche-understanding-gate.md` et implémentation d'une gate UX avant les recommandations principales. L'accueil masque désormais les cartes d'actions si `zone1.niche_validated` est faux, et la page Top 3 Actions vérifie `/niche/hypothesis` avant de charger les priorités.
- **Files created:** `docs/niche-understanding-gate.md`.
- **Files modified:** `ROADMAP.md`, `PROGRESS.md`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.priorities.tsx`, `docs/AI_HANDOFF.md`.
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Python tests non relancés car changement limité à Markdown et routes Remix frontend.
- **Decisions made:** Gate visuelle sans nouveau backend : réutilisation de `zone1.niche_validated` sur l'accueil et de `/api/shops/{shop}/niche/hypothesis` sur Top 3 Actions. Les réglages et le mode avancé restent accessibles.
- **Open issues:** Les modules backend peuvent encore exposer certains endpoints si appelés directement ; cette étape verrouille le parcours marchand principal, pas une politique serveur globale.
- **Next recommended action:** Démarrer la tâche 154 — Unified Onboarding Flow.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** Task 152 — First-Run Journey Map.
- **Summary:** Création du document canonique `docs/first-run-merchant-journey.md` pour cadrer le parcours marchand de première connexion jusqu'à la première action appliquée. Premier incrément UX associé : le JSON brut de l'écran "Ce que l'IA a compris" est désormais replié derrière un bloc **Mode avancé**, afin de garder la vue standard centrée sur les panneaux marchand.
- **Files created:** `docs/first-run-merchant-journey.md`.
- **Files modified:** `ROADMAP.md`, `PROGRESS.md`, `shopify-app/app/routes/app.niche-understanding.tsx`, `docs/AI_HANDOFF.md`.
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Python tests non relancés car seuls Markdown et une route Remix frontend ont changé.
- **Decisions made:** Implémenter Phase 11.9 en mini-cycles cadrage + UX concret ; conserver le JSON pour diagnostic/correction fine, mais seulement en mode avancé replié par défaut.
- **Open issues:** Les panneaux Boutique/Voix/Clients/Intentions/À éviter restent lisibles mais pas encore éditables champ par champ ; cette granularité relève de la tâche 153/154 si retenue.
- **Next recommended action:** Démarrer la tâche 153 — Niche Understanding as Mandatory Gate.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter Phase 11.9 à la roadmap.
- **Summary:** Mise à jour documentaire uniquement : ajout de la **Phase 11.9 — Merchant Journey Unification & Friction Reduction** dans `ROADMAP.md`, avec tâches 152-163 en attente, principes produit, parcours marchand cible, navigation cible, vocabulaire marchand et critères d'entrée Phase 12. `PROGRESS.md` et ce handoff notent que la Phase 12 démarre après validation Phase 11.9 et tests pilotes.
- **Files created:** Aucun.
- **Files modified:** `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** Vérification documentaire de placement Phase 11.9 avant Phase 12, numérotation 152-163 et mentions Phase 12.
- **Validations skipped:** Tests code non lancés, changement Markdown uniquement.
- **Open issues:** Les tâches 153-163 restent à cadrer/implémenter.
- **Next recommended action:** Démarrer la tâche 152 — First-Run Journey Map.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** Fix inactive buttons on Store Understanding page.
- **Summary:** Remplacement du déclenchement programmatique `useSubmit()` par des formulaires Remix natifs sur `app.niche-understanding.tsx`. Les boutons `Analyser`, `Enregistrer` et `Valider` soumettent maintenant chacun une vraie requête POST avec `_action`, affichent un état loading ciblé, et `Enregistrer`/`Valider` transmettent explicitement le JSON courant via champ caché.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/app/routes/app.niche-understanding.tsx`, `docs/AI_HANDOFF.md`.
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅.
- **Validations skipped:** Python tests non relancés car seule une route Remix frontend a changé.
- **Decisions made:** Garder les boutons Polaris pour l'apparence, mais utiliser des `<Form method="post">` natifs pour fiabiliser les actions dans l'app embedded.
- **Open issues:** À vérifier dans Shopify Pilot réel : clic sur `Analyser`, puis apparition de la banner succès/erreur ; clic sur `Valider`, puis retour accueil avec résumé niche.
- **Next recommended action:** Tester le flux marchand complet Accueil → Voir ce que l'IA a compris → Analyser → Valider → Accueil.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** UX simplification pass for the Shopify embedded app.
- **Summary:** Simplification de la navigation et des hubs marchands : la nav principale passe à 4 entrées visibles (`Accueil`, `Actions`, `Mesure`, `Compte & configuration`). Les hubs ne se présentent plus comme des catalogues d'outils : `Actions` met en avant les parcours canoniques (`Top 3 Actions`, `Content Actions`, `Review & Apply`, `Historique des modifications`), `Mesure` met en avant l'impact, les prochaines actions, les jalons et les rapports, et les anciennes pages techniques sont regroupées dans des sections avancées repliées par défaut. `Analyse` et `Contenu & visibilité` restent accessibles par URL mais ne dominent plus la navigation principale.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/app/components/HubGrid.tsx`, `shopify-app/app/routes/app.tsx`, `shopify-app/app/routes/app.optimization.tsx`, `shopify-app/app/routes/app.insights.tsx`, `shopify-app/app/routes/app.audit-hub.tsx`, `shopify-app/app/routes/app.content-hub.tsx`, `shopify-app/app/lib/i18n.ts`, `docs/AI_HANDOFF.md`.
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅ ; `npm run web -- --host 127.0.0.1 --port 3000` démarre le serveur Remix local ✅.
- **Validations skipped:** Python tests non relancés car seules des routes Remix/i18n frontend ont changé. Vérification visuelle navigateur non concluante : l'in-app browser a bloqué `localhost:3000` et `127.0.0.1:3000` avec `ERR_BLOCKED_BY_CLIENT` avant rendu de page.
- **Decisions made:** Les routes historiques ne sont pas supprimées physiquement pour éviter de casser des liens pilote ou des écrans encore utilisés ; elles sont masquées du chemin marchand principal et repliées en outils avancés.
- **Open issues:** Une passe visuelle dans l'app Shopify réelle reste utile pour juger le rendu exact des sections avancées repliées dans Polaris. Les routes historiques restent buildées et accessibles directement.
- **Next recommended action:** Tester manuellement dans l'app Shopify Pilot : accueil → Actions → Mesure → Réglages, puis vérifier que les outils avancés sont compréhensibles sans distraire le marchand.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Codex (GPT-5)
- **Goal:** Fix dashboard homepage HTTP 500.
- **Summary:** Correction du dashboard marchand `GET /api/shops/{shop}/dashboard` : `list_geo_events()` renvoie un payload paginé (`{"events": [...]}`), mais l'agrégateur passait ce payload entier à `_build_zone3()` comme une liste. En runtime réel, Zone 3 pouvait donc itérer sur les clés du dictionnaire et déclencher un 500 affiché dans la page d'accueil Remix comme "État du service / HTTP 500". Ajout d'un helper `_load_dashboard_events()` qui extrait défensivement la liste `events` et isole les erreurs ledger pour éviter qu'une zone secondaire casse toute la page.
- **Files created:** Aucun.
- **Files modified:** `app/api/dashboard.py`, `tests/test_api/test_dashboard.py`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check app/api/dashboard.py tests/test_api/test_dashboard.py` ✅ ; `pytest tests/test_api/test_dashboard.py` **7 passed** ✅ ; `ruff check .` ✅ ; `pytest` **1521 passed** ✅.
- **Validations skipped:** Aucune.
- **Decisions made:** Garder le dashboard résilient : si le ledger est indisponible ou mal formé, la page affiche simplement zéro optimisation active au lieu de répondre HTTP 500.
- **Open issues:** Aucun connu pour ce bug après test ciblé.
- **Next recommended action:** Recharger la page d'accueil Léonie SEO Pilot après déploiement/redémarrage backend.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 149 — Launch Readiness Evidence Pass.
- **Summary:** Audit mécanique complet des 13 catégories §3.1-§3.13 de `docs/launch-readiness.md` (50+ critères). Résultat : 3 vrais bugs trouvés et corrigés. Verdict `DECISIONS.md` : **NO-GO Phase 12** — bloquant unique = test utilisateur 3 marchands pilotes (§3.1 + §3.12, exigence humaine non substituable par audit interne). Toutes les vérifications techniques passent.
- **Files created:** (aucun nouveau fichier)
- **Files modified:** `app/content_actions/runner.py` (ajout `_effective_tier`, `os` import, `_LOW_COST_ONLY_ENV`), `app/api/rollback.py` (TTL 90j : `_ROLLBACK_TTL_DAYS`, `confirm_stale_revert` dans `RevertRequest`, check 409 + `stale_warning` + `age_days` dans dry_run response, `applied_at` ajouté à SELECT), `shopify-app/app/components/onboarding/CrawlCard.tsx` (texte "obligatoire"→"optionnel — mode avancé", description mini-crawl automatique, `required` retiré), `shopify-app/app/components/onboarding/InstallationChecklistCard.tsx` (libellé SF optionnel), `tests/test_content_actions/test_runner.py` (+3 tests `_effective_tier`), `tests/test_api/test_rollback.py` (+1 test TTL stale, `timedelta` import), `DECISIONS.md`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1520 passed** ✅ ; `npm run typecheck` ✅.
- **Decisions made:** `_effective_tier()` préserve "deterministic" même si `LEONIE_LLM_LOW_COST_ONLY=true` — on ne peut pas downgrader le déterministe. Rollback TTL utilise `confirm_stale_revert: bool = False` champ séparé plutôt que réutiliser `confirm_live_write` — sémantique plus explicite. `applied_at` manquait dans la SELECT `revert_change` — bug latent depuis Task 146, corrigé.
- **Open issues:** Test utilisateur sur 3 marchands pilotes (§3.1 et §3.12) — seul critère ⏳ restant pour le go/no-go App Store. Non implémentable par code, exige planification humaine.
- **Next recommended action:** Planifier les 3 sessions test utilisateur marchands pilotes. Dès validation humaine OK → **tâche 150 — Décision finale go/no-go App Store.**

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 148 — Merchant Dashboard Runtime.
- **Summary:** Endpoint canonique `GET /api/shops/{shop}/dashboard?plan=...` agrégeant 6 zones + header + banners en un seul appel. Zone 1 : score readiness + niveau coloré + niche hypothesis. Zone 2 : 3 actions Priority Engine + mode sparse_signal. Zone 3 : count optimisations actives + prochain jalon + sparkline GSC. Zone 4 : pending steps onboarding (GSC/GA4/niche/plan). Zone 5 : top 3 alertes. Zone 6 : AI Visibility désactivée. Header : budget LLM (used/limit/pct). Banners : pilot_safe, stale_snapshot, bulk_apply. Refonte complète `app._index.tsx` en 6 zones Polaris avec composants inline (DashboardHeader, Zone1-6, ActionCard). Loader unique `GET /dashboard`. Renommage nav : Audit→Analyse, Optimisation→Actions, Insights→Mesure. 50 nouvelles clés i18n FR+EN (`dashboard*`). 6 nouveaux tests API.
- **Files created:** `app/api/dashboard.py`, `tests/test_api/test_dashboard.py`.
- **Files modified:** `app/main.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app._index.tsx`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1516 passed** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Decisions made:** Composants Zone1-6 inline dans `app._index.tsx` plutôt que fichiers séparés — conforme à AGENTS.md "no speculative abstraction". `_PLAN_BUDGET_USD` hardcodé (free=0, pro=15, agency=50) — valeurs provisoires avant billing réel (tâche 150). Playwright tests non réalisés (pas de browser disponible en CLI) — notés comme skipped. `_build_zone5` utilise `merchant_alerts` table — `except Exception: []` car la table peut ne pas exister en test.
- **Open issues:** Playwright tests skipped — UI non testée côté browser. `Zone4` filtre les pending_steps niche/plan via niche_hypothesis passé en mémoire — pas de source base de données dédiée. LLM budget limit hardcodé, sera remplacé par le billing réel tâche 150.
- **Next recommended action:** **Tâche 149 — Launch Readiness Evidence Pass** : exécuter `docs/launch-readiness.md` §3, cocher chaque critère avec preuve, documenter les manques restants et décision go/no-go dans `DECISIONS.md`.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 147 — Impact Tracker Productization.
- **Summary:** Recentrage du dashboard Impact autour du cycle de mesure complet et ajout de l'encart AI Visibility désactivé V1. Nouveau endpoint `GET /api/shops/{shop}/ai-visibility/status` → `{enabled: false, available_in: "v2", axis: "ai_visibility", message_fr/en}`. `app.impact.tsx` enrichi : loader parallèle sur 6 endpoints (+ retention-milestones, + next-best-actions, + ai-visibility/status), 3 nouvelles sections UI — (1) Retention inline : prochain jalon avec date + days_remaining + message rétention + lien drill-down ; (2) NBA inline : summary total/high_priority + 3 premières actions avec badge priorité + lien "Voir tout" ; (3) AI Visibility encart désactivé : Banner info + badge "Disponible en V2". 14 nouvelles clés i18n (7 FR + 7 EN). 3 nouveaux tests API.
- **Files created:** `app/api/ai_visibility.py`, `tests/test_api/test_ai_visibility.py`.
- **Files modified:** `app/main.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.impact.tsx`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1510 passed** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Decisions made:** `nbaHighPriority` était déjà défini aux lignes 205 (FR) et 529 (EN) — doublon supprimé des nouvelles clés. Badge Polaris n'accepte pas `{number} {string}` — corrigé en template literal `` `${n} ${label}` ``. `LoaderData` avec nouveaux champs `retention`, `nba`, `aiVisibility` tous `| null` — pas de garde `!` inutile dans les renders conditionnels.
- **Open issues:** AI Visibility entièrement désactivée en V1. `retention.next_milestone` peut être `null` si aucun event actif → section conditionnelle (`retention?.next_milestone && ...`). NBA inline affiche max 3 actions — lien drill-down pour voir la liste complète.
- **Next recommended action:** **Tâche 148 — Merchant Dashboard Runtime** : créer `GET /api/shops/{shop}/dashboard`, refondre `app._index.tsx` en 6 zones, renommer la navigation et valider responsive/Playwright.

## Previous completed task

- **Date:** 2026-05-21
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 146 — Safe Apply Runtime.
- **Summary:** Workflow complet de validation humaine et application sécurisée des actions contenu vers Shopify. 5 modules Python nouveaux : `app/safe_apply/diff.py` (build_diff — aperçu avant/après avec blocked_reasons et next_actions), `app/safe_apply/decisions.py` (record_decision — accept/edit/reject/retry avec cap 3 retries et blocage sur violations, get_decision_history), `app/safe_apply/writer_adapters.py` (dry_run_preview + live_write pour META_TITLE/META_DESCRIPTION/PRODUCT_DESCRIPTION), `app/safe_apply/rollback_adapters.py` (revert_field — rollback des 3 champs supportés). 5 routes API FastAPI : `GET /diff`, `POST /decision`, `POST /dry-run` (requires status=approved), `POST /live` (gates : plan Pro/Agency + pilot_safe_mode + confirm_live_write + status=approved), `POST /revert?change_id=N` (dry_run par défaut). Table `content_action_decisions` ajoutée dans `app/db.py`. UI Remix : `app.safe-apply.tsx` (review queue avec ActionCard, QualityBar, violations banner, boutons decision/dry-run/apply) et `app.rollback-history.tsx` (DataTable + revert). 16 clés i18n. Entrée nav Safe Apply ajoutée dans audit-hub.
- **Files created:** `app/safe_apply/__init__.py`, `app/safe_apply/diff.py`, `app/safe_apply/decisions.py`, `app/safe_apply/writer_adapters.py`, `app/safe_apply/rollback_adapters.py`, `app/api/safe_apply.py`, `shopify-app/app/routes/app.safe-apply.tsx`, `shopify-app/app/routes/app.rollback-history.tsx`, `tests/test_safe_apply/__init__.py`, `tests/test_safe_apply/test_diff.py`, `tests/test_safe_apply/test_decisions.py`, `tests/test_safe_apply/test_writer_adapters.py`, `tests/test_api/test_safe_apply.py`.
- **Files modified:** `app/db.py`, `app/main.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.audit-hub.tsx`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1507 passed** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Decisions made:** `_retry_count` utilise `SELECT COUNT(*) AS cnt` (alias explicite) car `_Cursor.fetchone()` retourne un `dict` — `row[0]` lève `KeyError`. Imports de `_load_action`/`ContentStatus`/`DB_PATH` tous lazy (dans le corps de fonction) pour éviter les cycles et permettre le patching dans les tests. `EXTENDED_REVERTIBLE_FIELDS` étend le rollback.py existant avec `descriptionHtml`. `LoaderData` avec `locale: Locale` explicite requis pour que `tsc` accepte les appels `t(locale, ...)`.
- **Open issues:** Live write Shopify en V1 limité à META_TITLE, META_DESCRIPTION, PRODUCT_DESCRIPTION. Autres types (FAQ_BLOCK, ALT_TEXT, etc.) retournent `applied=False` avec `not_supported_v1`. `before` est `null` en V1 (pas de fetch Shopify avant génération). Plan `pro/agency` hardcodé dans l'UI, le vrai plan sera passé via session Shopify Billing après tâche 150.
- **Next recommended action:** **Tâche 147 — Impact Tracker Productization** : recentrer l'UI Impact autour de Search Performance, optimisations actives, rétention, next actions, ajouter `ai-visibility/status` désactivé V1.

## Previous completed task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 144 — Priority Engine Runtime.
- **Summary:** Pipeline 4 étapes sélectionnant exactement 3 dossiers d'actions prioritaires par catalogue. Étape 1 : agrégation Opportunity Finder (top 50). Étape 2 : Risk Guard — exclusion des produits `protected`. Étape 3 : pré-score déterministe `0.40×opp + 0.25×bv + 0.15×confidence + 0.10×niche_boost - 0.05×effort - 0.05×risk`, top 10 retenus. Étape 4 : arbitrage LLM (plans pro/agency avec contrôle budget + cache TTL 24h) ou fallback déterministe (plan free / over_budget / llm_error). Dossier par action : rank, action_id, why_now, evidence (max 5), estimates (impact/confidence/effort/risk/revenue), success_metric (name/current/target/window), preview.depends_on, risk_guard.override_required, niche_alerts. Prompt YAML `priority_arbitrage` v0.1.0. Nouveau endpoint `GET /api/shops/{shop}/priorities?scope=active&plan=free`. UI Remix `app.priorities.tsx` grille 3 cartes `InlineGrid columns=["oneThird","oneThird","oneThird"]` avec badges rank, progress bar score, why_now box, estimates badges, risk override banner, success metric. Entrée "Top 3 Actions" ajoutée en tête du hub. 14 clés i18n FR/EN.
- **Files created:** `app/priorities/__init__.py`, `app/priorities/engine.py`, `app/api/priorities.py`, `config/prompts/priority_arbitrage.yaml`, `shopify-app/app/routes/app.priorities.tsx`, `tests/test_priorities/__init__.py`, `tests/test_priorities/test_engine.py`, `tests/test_api/test_priorities.py`.
- **Files modified:** `app/main.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.audit-hub.tsx`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1435 passed** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Decisions made:** `_load_gsc_query_rows` importé depuis `app.api.opportunities` (réutilisé, pas dupliqué). `check_budget` et `assess_product_risk` mocké dans les tests engine pour isoler la logique de scoring. Fallback_reason `"plan_free"` assigné en dernier (après le bloc LLM) pour ne pas écraser les raisons précédentes (budget_exceeded, llm_unavailable). Pas de route de déclenchement LLM explicite dans l'UI V1 — le plan est passé en query param.
- **Open issues:** Le prompt_template.version dans `_try_llm_arbitrage` suppose que `load_prompt` retourne un objet avec attribut `.version`. À valider lors de l'intégration LLM réelle (tâche 145+).
- **Next recommended action:** **Tâche 145 — AI Content Actions Runtime** : orchestrateur unique, schémas Pydantic, prompts v2.0, table `content_actions`, route `/content-actions/run` et UI unifiée.

## Previous completed task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 143 — Opportunity Finder Runtime.
- **Summary:** Couche d'agrégation déterministe 7 signaux (GSC, keyword gaps, audit pressure, intent match, cannibalization, link opportunity V1=0, competitor pressure) ordonnant les produits ACTIVE par ratio impact/effort. Formule pondérée : 0.30/0.20/0.15/0.10/0.10/0.10/0.05. Ajustements niche validée : priority_products +10pts (cap 100), forbidden_promise → alerte seule. Tier : ≥70 high / ≥40 medium / <40 low. Confidence : ≥3 signaux non-nuls → high. Nouveau endpoint `GET /api/shops/{shop}/opportunities?scope=active&top=20&intent=...` avec schema complet. UI Remix `app.opportunities.tsx` avec summary bar, Tabs intent, Cards ProgressBar, primary_reason, niche_alerts, recommended_actions. Entrée "Opportunity Finder" ajoutée en tête du hub. 11 clés i18n FR/EN.
- **Files created:** `app/opportunities/__init__.py`, `app/opportunities/finder.py`, `app/api/opportunities.py`, `shopify-app/app/routes/app.opportunities.tsx`, `tests/test_opportunities/__init__.py`, `tests/test_opportunities/test_finder.py`, `tests/test_api/test_opportunities.py`.
- **Files modified:** `app/main.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.audit-hub.tsx`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1419 passed** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Decisions made:** Two GSC data formats: page-level CSV (for gsc_signal per product URL) and query-level JSON (for keyword gaps and intent clusters). `_load_gsc_query_rows` inline in opportunities API mirrors the private `_load_gsc` in `app.api.niche` to avoid coupling. `link_opportunity` signal hard-coded to 0.0 in V1 (no link graph). Niche conversational_intent +5 pts skipped to avoid double-counting with `_intent_match_boost`.
- **Open issues:** Intent matching uses product title token overlap against cluster keywords, not semantic matching — may miss indirect matches. `_cannibalization_for_product` uses `resource_id` equality (GID string) which may produce 0 counts if snapshot uses short IDs. UI drill-down to product page not yet linked.
- **Next recommended action:** **Task 144 — Priority Engine Runtime** : produire exactement 3 actions prioritaires avec fallback déterministe, arbitrage LLM plafonné/cache, route `/priorities`, UI cartes et tests budget/fallback.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Sonnet 4.6)
- **Goal:** Task 142 — Unified Readiness Audit Runtime.
- **Summary:** Score AI Search Readiness unifié : 4 niveaux (`excellent/bon/partiel/faible`), intégration Crawl L3 (malus SEO sur page_404/server_error/redirect_chain/missing_canonical), intégration hypothèse niche validée (forbidden_promises → malus Trust + niche_alerts, brand_voice.do_not_say → alertes, conversational_intents → delta Answerability ±5%). Nouveau endpoint `GET /api/shops/{shop}/audit/readiness` avec global_score, global_level, crawl_health, niche_alerts, snapshot_freshness_warning. Redirection 301 de `/geo/readiness` vers `/audit/readiness`. Compatibilité `prioritization.py` pour le nouveau format `components[key]["score"]`. UI Remix `app.audit-readiness.tsx` avec score card, crawl health, niche alerts et top 3 actions. Entrée dans l'audit hub. 18 clés i18n FR/EN.
- **Files created:** `shopify-app/app/routes/app.audit-readiness.tsx`, `tests/test_api/test_audit_readiness.py`.
- **Files modified:** `app/geo/readiness.py`, `app/api/audit.py`, `app/api/geo.py`, `app/geo/prioritization.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.audit-hub.tsx`, `tests/test_geo/test_readiness.py`, `tests/test_api/test_geo.py`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`.
- **Validations run:** `ruff check .` ✅ ; `pytest` **1407 passed** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Decisions made:** `components` format changed from flat int to `{score, weight}` dict — backward compat ensured in `prioritization.py`. `/geo/readiness` → 301 redirect (permanent move, no functional bypass). Niche adjustments only apply when `status == "validated_by_merchant"`. Crawl findings matched by URL handle (substring). Freshness warning threshold: 7 days.
- **Open issues:** `components` dict format change may affect other consumers not yet identified. Niche answerability delta is a rough keyword match, not a true FAQ coverage check. UI drill-down to product detail not yet linked.
- **Next recommended action:** **Task 143 — Opportunity Finder Runtime** : agréger signaux GSC/niche/crawl en opportunités par produit actif, route `/opportunities`, UI et tests.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Codex (GPT-5)
- **Goal:** Task 141 — Niche Understanding Runtime.
- **Summary:** Création du runtime de compréhension boutique : prompt versionné `config/prompts/niche_understanding.yaml`, orchestrateur `app/niche/understanding.py`, cache LLM 30 jours en table `llm_cache`, parsing/normalisation du JSON contractuel, contrôle budget avant appel LLM, persistance `shop_config.niche_hypothesis`, historique `niche_hypothesis_history` limité à 5 versions, helper `get_validated_niche_hypothesis()` pour bloquer l'usage aval tant que le marchand n'a pas validé. Endpoints `POST /api/shops/{shop}/niche/understand`, `GET/PATCH /api/shops/{shop}/niche/hypothesis`. UI Remix `app.niche-understanding.tsx` pour générer, éditer le JSON et valider.
- **Files created:** `app/niche/understanding.py`, `config/prompts/niche_understanding.yaml`, `tests/test_niche/test_understanding.py`, `tests/test_api/test_niche_understanding.py`, `shopify-app/app/routes/app.niche-understanding.tsx`.
- **Files modified:** `app/api/niche.py`, `app/db.py`, `pyproject.toml`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.content-hub.tsx`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`, `docs/niche-understanding.md`.
- **Validations run:** `ruff check ...` ciblé ✅ ; `pytest ...` ciblé **56 passed** ✅ ; `ruff check .` ✅ ; `pytest` **1393 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Decisions made:** Le LLM reçoit un signal bundle compact dérivé des produits actifs, clusters, intents, gaps, entités et top queries, jamais le snapshot brut complet. Le flux standard UI appelle le LLM ; un fallback déterministe existe pour tests et mode explicite `use_llm=false`. Free est taggé en tier logique `medium`, Pro/Agency en `advanced`. Les prompts de génération existants restent inchangés jusqu'à la tâche 145.
- **Open issues:** L'UI de correction est une édition JSON complète plutôt qu'un formulaire section par section riche. L'invalidation automatique cache sur variation catalogue >20 % ou >10 nouvelles top queries n'est pas encore déclenchée par job ; le `force_refresh` manuel existe. Les modules 142-145 ne consomment pas encore `get_validated_niche_hypothesis()`.
- **Next recommended action:** **Task 142 — Unified Readiness Audit Runtime** : exposer le score unifié actif, sous-scores, recommandations, route canonique `/audit/readiness`, UI `app.audit-readiness` et compatibilité drill-down.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Codex (GPT-5)
- **Goal:** Task 140 — Crawl L3 Native Runtime.
- **Summary:** Création du runtime Crawl L3 natif : modules `robots`, `sitemap`, `mini` et `findings`, endpoint `POST /api/shops/{shop}/crawl/l3`, table `crawl_findings`, rapport crawl stocké via le client existant et persistance des findings. Le snapshot Shopify est étendu aux pages CMS, articles de blog, redirects URL et métadonnées shop. Le mini-crawl respecte robots.txt, utilise le user-agent Léonie, throttle les requêtes, collecte statut HTTP, chaînes de redirection, canonical, hreflang, title, meta description et validité JSON-LD. Screaming Frog reste disponible via l'upload CSV existant en mode avancé, mais n'est plus requis pour le chemin backend natif.
- **Files created:** `app/crawl/robots.py`, `app/crawl/sitemap.py`, `app/crawl/mini.py`, `app/crawl/findings.py`, `tests/test_crawl/test_robots.py`, `tests/test_crawl/test_sitemap.py`, `tests/test_crawl/test_mini.py`, `tests/test_crawl/test_findings.py`.
- **Files modified:** `app/api/crawl.py`, `app/api/snapshot_store.py`, `app/db.py`, `app/jobs/audit_snapshot.py`, `scripts/audit/crawl_shopify.py`, `tests/test_api/test_crawl.py`, `tests/audit/test_crawl_shopify.py`, `tests/test_jobs/test_audit_snapshot.py`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`, `docs/crawl-strategy.md`.
- **Validations run:** `ruff check ...` ciblé ✅ ; `pytest ...` ciblé **53 passed** ✅ ; `ruff check .` ✅ ; `pytest` **1385 passed** ✅.
- **Decisions made:** Crawl L3 reste HTTP-only sans Chromium headless et sans stockage HTML brut. Les URLs candidates sont limitées au domaine primaire du snapshot et dédupliquées depuis snapshot + sitemap. Le CSV Screaming Frog conserve sa route existante, mais le runtime natif devient le chemin backend standard.
- **Open issues:** UI Audit non encore modifiée pour mettre Crawl L3 au premier plan. Les plafonds Free/Pro/Agency sont cadrés mais pas encore branchés à la route `crawl/l3`, qui expose seulement `max_urls` borné. Le snapshot étendu couvre pages/articles/redirects/shop, mais pas encore locales actives ni tous les metafields évoqués dans le cadrage. Pas de TTL/purge automatique des `crawl_findings` à ce stade.
- **Next recommended action:** **Task 141 — Niche Understanding Runtime** : créer le prompt versionné, l'orchestrateur LLM, les endpoints `understand` / `hypothesis`, la persistance validée marchand et l'UI de correction. Terminée le 2026-05-20.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Codex (GPT-5)
- **Goal:** Task 139 — Product Scope Runtime.
- **Summary:** Création du helper canonique `app/snapshot/scope.py` avec scopes `active`, `draft`, `unlisted`, `archived`, `all`. Le scope `active` inclut les produits `ACTIVE` publiés Online Store, avec compatibilité legacy pour les anciens snapshots sans signal `onlineStoreUrl`/`publishedAt`. Branchement de `scope="active"` par défaut dans `score_catalog_readiness()`, `prioritize_catalog()`, `build_weekly_actions()`, `build_next_best_actions()` et `generate_catalog_content()`. Les endpoints GEO `readiness`, `priorities`, `weekly-actions`, `next-best-actions` et `faq-content` acceptent désormais `scope`. Le crawl Shopify demande maintenant `publishedAt` et `onlineStoreUrl`, conformément à la doc Shopify Admin GraphQL : `onlineStoreUrl = null` signifie non publié Online Store. Chaque réponse concernée expose un résumé `scope` avec compteurs par vue.
- **Files created:** `app/snapshot/__init__.py`, `app/snapshot/scope.py`, `tests/test_snapshot/test_scope.py`.
- **Files modified:** `app/geo/readiness.py`, `app/geo/prioritization.py`, `app/geo/weekly.py`, `app/geo/next_best_actions.py`, `app/geo/faq_generator.py`, `app/api/geo.py`, `scripts/audit/crawl_shopify.py`, `tests/test_geo/test_readiness.py`, `tests/test_geo/test_prioritization.py`, `tests/test_geo/test_weekly.py`, `tests/test_geo/test_next_best_actions.py`, `tests/test_geo/test_faq_generator.py`, `tests/test_api/test_geo.py`, `tests/audit/test_crawl_shopify.py`, `ROADMAP.md`, `PROGRESS.md`, `docs/AI_HANDOFF.md`, `docs/product-scope.md`.
- **Validations run:** `ruff check ...` ciblé ✅ ; `pytest ...` ciblé **80 passed** ✅ ; `ruff check .` ✅ ; `pytest` **1369 passed** ✅.
- **Decisions made:** Le snapshot reste complet, le filtrage se fait en aval. Les anciens snapshots sans champ Online Store restent inclus dans `active` pour éviter une régression de données avant refresh. Les produits explicitement `ACTIVE` avec `onlineStoreUrl = null` sont classés `unlisted`.
- **Open issues:** Le Product Facts Layer reste volontairement non filtré globalement, conformément à `docs/product-scope.md` : le scan de faits reste utile tous statuts, seuls les agrégats/scorings principaux sont limités à `active`. Les UI n'ont pas encore le sélecteur de scope ni le bandeau "x produits inclus" ; ce sera porté par les tâches UI/dashboard.
- **Next recommended action:** **Task 140 — Crawl L3 Native Runtime** : créer `app/crawl/sitemap.py`, `robots.py`, `mini.py`, `findings.py`, étendre le snapshot Shopify aux pages/articles/redirects et garder Screaming Frog comme mode avancé optionnel. Terminée le 2026-05-20.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Codex (GPT-5)
- **Goal:** Formaliser une **Phase 11.8 — Implémentation GEO Autopilot Simplification** entre le cadrage Phase 11.7 et la soumission Phase 12.
- **Summary:** Ajout d'une nouvelle phase d'implémentation dans `ROADMAP.md`, avec 11 tâches applicatives numérotées 139-149 : Product Scope Runtime, Crawl L3 Native Runtime, Niche Understanding Runtime, Unified Readiness Audit Runtime, Opportunity Finder Runtime, Priority Engine Runtime, AI Content Actions Runtime, Safe Apply Runtime, Impact Tracker Productization, Merchant Dashboard Runtime, Launch Readiness Evidence Pass. Phase 12 repoussée et renumérotée en 150-151. Objectif clarifié : la checklist `docs/launch-readiness.md` §3 ne peut pas servir de go/no-go tant que les critères bloquants restent seulement documentés.
- **Files created:** Aucun.
- **Files modified:** `ROADMAP.md`, `docs/AI_HANDOFF.md`, `PROGRESS.md`.
- **Validations run:** Aucune (mise à jour documentaire de pilotage uniquement).
- **Next recommended action:** Démarrer la **tâche 139 — Product Scope Runtime** : implémenter le helper canonique de filtrage produits `ACTIVE` visibles Online Store, le brancher aux modules GEO concernés et ajouter les tests de scope.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 138 — Public Launch Readiness Criteria. **Clôture intégrale de la Phase 11.7 documentation.**
- **Summary:** Création de `docs/launch-readiness.md`. Checklist canonique d'entrée Phase 12 distillant les 11 docs amont en **13 catégories de critères** opérationnels (3.1 Compréhension marchand < 5 min, 3.2 3 actions prioritaires max, 3.3 IA assistante avec review humaine obligatoire, 3.4 Mesure d'impact obligatoire avec event créé par apply, 3.5 Scope produit ACTIVE Online Store, 3.6 Pas de Screaming Frog obligatoire, 3.7 Aucune promesse ChatGPT/Perplexity/Gemini, 3.8 Search Performance et AI Visibility séparés, 3.9 Coût LLM maîtrisé avec 10 sous-critères, 3.10 Rollback per-item sur 10 content_types, 3.11 Dry-run par défaut + pilot-safe + confirm_live_write triple verrou, 3.12 Dashboard impact lisible, 3.13 Niche Understanding gating). Chaque critère a 3 colonnes : Référence doc, Preuve attendue (test automatisé / capture / métrique / audit textuel), Statut. Règle stricte : **aucun critère ❌ ou ⏳ ne peut être contourné** — le go/no-go n'est pas une moyenne pondérée. Processus tâche 139 explicité : lecture exhaustive, cocher chaque ligne, documenter dans `DECISIONS.md`, critères secondaires §4 listés en *known limitations*. Critères opérationnels Shopify App Store (OAuth, Billing, GDPR webhooks, App Bridge v4, API 2025-01) déjà couverts par tâche 75, vérification anti-régression Phase 11.7. État final attendu post-Phase 12 listé en §8. Test utilisateur sur 3 marchands pilotes exigé pour §3.1 et §3.12 (non remplaçable par test interne). Aucune décision produit nouvelle introduite dans 138 — uniquement consolidation et mise en checklist opérationnelle.
- **Files created:** `docs/launch-readiness.md`.
- **Files modified:** `ROADMAP.md` (statut 138 → ✅ 2026-05-20, **Phase 11.7 close**), `docs/AI_HANDOFF.md` (cette entrée + Current roadmap mis à jour).
- **Validations run:** Aucune (tâche purement documentaire de synthèse).
- **Phase 11.7 final bilan:** 12 tâches documentaires closes en 2 jours (2026-05-19 → 2026-05-20). 12 fichiers `docs/*.md` créés (llm-strategy, product-scope, crawl-strategy, niche-understanding, readiness-audit, opportunity-finder, priority-engine, ai-content-actions, safe-apply, impact-tracker, dashboard-simplification, launch-readiness). Aucune ligne de code applicatif modifiée. Toutes les décisions produit/architecture pour la V1 publique sont figées et tracées.
- **Next recommended action:** **Phase 12 — Tâche 139 (Décision go/no-go App Store).** Exécuter la checklist `docs/launch-readiness.md` §3 en marquant chaque critère ✅/❌/⏳ avec preuves. Le résultat conditionne le démarrage de la tâche 140 (Soumission App Store finale). En parallèle ou avant 139, prioriser l'implémentation effective des éléments ⏳ de la Phase 11.7 (modules code à porter, refactor `app._index.tsx`, prompts v2.0, etc.) selon la stratégie business retenue.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 137 — Merchant-Friendly Dashboard Simplification (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/dashboard-simplification.md`. Décisions figées : structure cible **6 zones** (Header avec coût LLM en première classe + Zone 1 État boutique avec score + niche + Zone 2 **exactement 3 actions prioritaires en cartes** + Zone 3 Impact en cours avec mini-sparkline + Zone 4 Onboarding conditionnel + Zone 5 Alertes max 3 + Zone 6 AI Visibility V2 désactivé sans promesse). Promesse marchand non-expert : lecture en < 30s, zéro jargon en Zone 1-3. **Tableau de vocabulaire interdit** ("GEO", "JSON-LD", "Crawl L3", "CTR", "Cannibalisation", "score readiness"...) → remplacements marchand ("moteurs IA", "données structurées", "analyse de votre site", "taux de clic", "deux pages qui se concurrencent", "Score Léonie"...). Endpoint canonique unique `GET /api/shops/{shop}/dashboard` agrège les 6 zones en 1 seul appel (cible FCP < 1.5s, TTI < 3s). NavMenu renommé : "Insights" → "Mesure", "Optimization" → "Actions", "Account" → "Réglages". 8 états dégradés explicites (snapshot obsolète, pilot-safe, sparse_signal, niche non validée, plan Free → bouton "Exporter" au lieu de "Appliquer", etc.). Cohérence stricte avec les 6 modules amont : Zone 1 consomme `docs/readiness-audit.md` + `docs/niche-understanding.md`, Zone 2 consomme `docs/priority-engine.md` (3 cartes exactement), Zone 3 consomme `docs/impact-tracker.md` (Search Performance seulement, pas d'agrégation AI Visibility), Header consomme `docs/llm-strategy.md` budget. Garde-fous : pas de customization, pas de gamification, pas de notification push intrusive, pas de message technique brut, tooltips Polaris au lieu d'options, aucune page existante supprimée. Observation clé : dashboard actuel `app._index.tsx:1` = 4 cartes basiques (Setup/Alerts/Shortcuts/Recent) — la tâche 137 **recentre** sans supprimer.
- **Files created:** `docs/dashboard-simplification.md`.
- **Files modified:** `ROADMAP.md` (statut 137 → ✅ 2026-05-20), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** Refactor `app._index.tsx` autour des 6 zones, création `app/api/dashboard.py` (endpoint canonique agrégateur), clés i18n `dashboard*` FR/EN, NavMenu renommages Polaris et tests Playwright restent à porter par la tâche d'implémentation. Limites V1 explicites : pas de dashboard customizable, pas d'objectifs SMART configurables, pas de leaderboard, pas de digest email hebdo, pas de comparaison historique multi-période sur le dashboard, pas de filtre par segment client, pas de prévisualisation thème depuis le dashboard.
- **Next recommended action:** Tâche 138 (Public Launch Readiness Criteria) — dernière tâche Phase 11.7. Synthétise les critères go/no-go pour Phase 12 (App Store) à partir des 11 docs déjà produits : compréhension < 5 min, 3 actions max, LLM-assisté + review humaine, événement mesurable, scope produits actifs, pas de Screaming Frog, pas de promesse ranking ChatGPT, séparation Google / IA, coût LLM maîtrisé, rollback, dry-run, dashboard impact lisible.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 136 — Impact Tracker as Core Product Value (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/impact-tracker.md`. **Observation clé** : les 8 briques Phase 11.5 (tâches 116-125) sont **100 % déjà codées** — `app/geo/optimization_snapshots.py:103`, `app/geo/ledger.py:48`, `app/geo/validation_timeline.py:100`, `app/geo/progress_curve.py:1`, `app/geo/confidence.py:139`, `app/geo/impact_report.py:137`, `app/geo/next_best_actions.py:85`, `app/geo/retention_milestones.py:54`. 5 pages Remix existent (`app.impact`, `app.impact-report`, `app.retention-milestones`, `app.next-best-actions`, `app.reports`, 1358 lignes au total). La tâche 136 ne réécrit rien — elle **repositionne** ces briques comme un seul module conceptuel "cœur de valeur différenciant". Décisions structurantes : (1) cycle de mesure unifié en 10 étapes (Plan → Snapshot → Apply → Event → Wait → Re-measure → Confidence → Verdict → Next Action → Retention) avec boucle vers Priority Engine 133, (2) **séparation stricte Search Performance (GSC/GA4/Shopify, fiable V1) vs AI Visibility (signal mesurable mais imparfait, branche V2 opt-in)**, jamais d'agrégation, deux dashboards distincts, (3) couplage strict avec 135 : aucun apply terminé sans event créé, aucun event sans `success_metric` venu de 133, (4) confidence score obligatoire sur tout verdict, stabilité commerce baisse le confidence si prix/stock changent pendant la fenêtre, (5) règle anti-dark-pattern explicite sur Retention Milestones (basés sur faits techniques, pas urgency artificielle), (6) AI Visibility hors V1 : pas implémenté côté code aujourd'hui, encart UI désactivé avec message *"disponible dans une version future"*, aucune promesse d'apparition dans ChatGPT/Perplexity/Gemini, conditions d'activation V2 cadrées (pricing distinct, table séparée `ai_visibility_events`, UI séparée). Pas de page Remix dépréciée — repositionnement UI uniquement. Travail post-136 : recentrage `app.impact.tsx` autour des 4 sections (Search Performance / Active Optimizations / Retention / Next Best Actions), endpoint `GET /ai-visibility/status` retournant `{enabled: false, available_in: "v2"}`, encart désactivé.
- **Files created:** `docs/impact-tracker.md`.
- **Files modified:** `ROADMAP.md` (statut 136 → ✅ 2026-05-20), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire, briques Python déjà testées en Phase 11.5).
- **Known limitations:** Pas de comparaison concurrentielle auto, pas d'A/B testing auto, pas de scoring multi-langues différencié, pas d'attribution cross-channel, pas de cohort GA4, pas de re-mesure d'une fenêtre fermée. AI Visibility complet (cron prompts ChatGPT/Perplexity/Gemini, table dédiée, UI dédiée) est V2 explicitement hors Phase 11.7. Recentrage UI `app.impact.tsx` + endpoint `ai-visibility/status` + encart désactivé restent à porter par la tâche d'implémentation finale.
- **Next recommended action:** Tâche 137 (Merchant-Friendly Dashboard Simplification) — consomme les sorties des 6 modules précédents pour définir l'interface marchand non-expert (score global, niche détectée, 3 actions prioritaires, impact en cours, métriques séparées Google/IA, pas de jargon en premier niveau). Avant-dernière tâche de la Phase 11.7.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 135 — Human Review & Safe Apply Workflow (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/safe-apply.md`. Décisions figées : workflow 7 étapes (receive draft 134 → diff → human decision → dry-run obligatoire → live apply → event tracking → post-apply) couvrant les 10 `content_type` de 134 (alors qu'aujourd'hui seul meta a un review complet). Schéma `Diff` unifié avec `before` / `after`, `facts_used` highlighted, `claims_unverified` avec severity, `merchant_view.summary_fr` obligatoire (non-technique). 4 actions humaines : accept / edit / reject / retry (× 3 max plafonné par `docs/ai-content-actions.md`). **Auto-approve définitivement supprimé** (`app/api/generate.py:214`). Étape 4 dry-run obligatoire avant live avec **détection `before_drift_detected`** (re-fetch Shopify entre génération et apply). Réutilisation maximale de l'existant : `app/safety.py:14` (`is_pilot_safe_mode`), `app/safety.py:19` (`require_shopify_write_allowed`), `app/apply/shopify_writer.py:16`, `app/apply/bulk_orchestrator.py:84` (dry_run par défaut + rate-limit 50/run + delay 0.5s), `app/api/rollback.py:59` per-item, `app/geo/ledger.py:48` (`create_geo_event`), `app/db.py:39` (`seo_changes`), `app/db.py:144` (`geo_impact_events`). Extension nécessaire de `seo_changes` aux nouveaux content_types (product_description, alt_text, faq_block, answer_block, buying_guide, jsonld_faqpage, collection_description, meta_multilingual). Plan-based behavior strict : Free = export only (pas de live), Pro = 50/run, Agency = 100/run. UI unique `app.safe-apply.tsx` remplace `app.review.tsx` + `app.descriptions.tsx` (alias deprecated 1 release). Couplage strict 136 : pas d'apply sans event créé. Rollback TTL 90 jours aligné fenêtre de mesure J+90. Idempotence garantie : 2 apply identiques = no-op. Tests requis : pilot-safe bloque live, forbidden_promise bloque accept, drift detect force re-gen, retry × 4 → erreur, Free → bouton Export.
- **Files created:** `docs/safe-apply.md`.
- **Files modified:** `ROADMAP.md` (statut 135 → ✅ 2026-05-20), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** `app/safe_apply/diff.py` + `decisions.py` + `writer_adapters.py` + `rollback_adapters.py`, route `POST /safe-apply/*` canoniques, UI `app.safe-apply.tsx` + `app.rollback-history.tsx`, extension `shopify_writer.py` aux nouveaux content_types, table `content_action_decisions` restent à porter. Limites V1 explicites : pas de workflow multi-niveau (1 admin = 1 niveau), pas de scheduling apply, pas de pre-staging hors theme preview Shopify, pas de notifications email/Slack post-apply, pas de signature cryptographique des changements (table `seo_changes` source de vérité sans hash chain).
- **Next recommended action:** Tâche 136 (Impact Tracker as Core Product Value) — consomme directement les événements `geo_impact_events` créés par 135, fusionne Snapshot, Ledger, Validation Timeline J+7/J+30/J+60/J+90, Progress Curve, Confidence Score, Before/After Report, Win/Neutral/Risk Detection, Next Best Action Loop et Retention Milestones en un module central de mesure d'impact.

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 134 — AI Content Actions Simplification (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/ai-content-actions.md`. Décisions figées : **un seul orchestrateur** (workflow 11 étapes) qui couvre 10 `content_type` (meta_title, meta_description, product_description, collection_description, alt_text, faq_block, answer_block, buying_guide, jsonld_faqpage, meta_multilingual). Mapping tier LLM strict : `low-cost` (meta/alt/multilingual), `medium` (descriptions/FAQ/guides), `jsonld_faqpage` **déterministe Python sans appel LLM**. Bundle d'inputs unifié : `confirmed_facts` (seule source pour affirmations factuelles), Shopify, GSC + GA4 avec `estimate_basis` transparent, `niche_context` injecté depuis `shop_config.niche_hypothesis` (refus d'exécution si non validée pour content_types à charge factuelle). Schéma JSON de sortie unique avec `facts_used` obligatoire, `claims_unverified` listé, `constraints_check` (forbidden_promises + do_not_say + longueurs + langue) systématique, `quality.score` 0-100, `llm_meta` complet pour traçabilité. 6 statuts (draft → needs_review → approved → exported → applied → reverted) avec transitions auto sur violations. **Migration prompts hardcodés v1 → v2.0** : `meta_title.yaml:3`, `meta_description.yaml:3`, `product_description.yaml:3`, `collection_brief.yaml:3`, `alt_text.yaml`, `meta_multilingual.yaml` éliminent "premium animaux" et injectent `niche_context` ; nouveaux prompts `faq_product.yaml`, `answer_block.yaml`, `buying_guide.yaml`. FAQ : LLM **enrichit** le template (`app/geo/faq_generator.py:283` conservé en fallback Free / budget dépassé). Boucle retravail plafonnée 3. Endpoints existants conservés en alias deprecated, `POST /content-actions/run` canonique. UI unique `app.content-actions.tsx` remplace `app.review`, `app.descriptions`, `app.geo-faq-content` (drill-downs accessibles). Apply Shopify déjà aligné (`app/apply/shopify_writer.py:16` dry-run par défaut + rollback `app/apply/bulk_orchestrator.py:22`). Cohérence `docs/llm-strategy.md` §1-12 vérifiée intégralement.
- **Files created:** `docs/ai-content-actions.md`.
- **Files modified:** `ROADMAP.md` (statut 134 → ✅ 2026-05-20), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** `app/content_actions/runner.py` (orchestrateur), `audit.py` (6 garde-fous), `schema.py` (Pydantic), `app/api/content_actions.py` (routes canoniques), nouveaux prompts FAQ/Answer/Guide, table DB `content_actions`, UI unique, migration prompts hardcodés et migration 5 workflows UI restent à porter. Limites V1 : pas de génération blog massive, pas de pages CMS, pas de vidéo/image, locales V1 = FR + EN seulement, pas de fine-tuning par shop, pas d'A/B testing auto.
- **Next recommended action:** Tâche 135 (Human Review & Safe Apply Workflow) — consomme directement la sortie schéma `docs/ai-content-actions.md` §6 et orchestre preview → diff → accept/edit/reject → dry-run → apply → rollback → event tracking. Couplage strict avec 136 (Impact Tracker capture snapshot avant/après chaque `applied`).

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 133 — Unified Priority Engine (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/priority-engine.md`. Décisions figées : **exactement 3 actions prioritaires** à la fois (sparse_signal si < 3). Pipeline 4 étapes : (1) pull `/opportunities?top=50`, (2) Risk Guard filter (`app/geo/risk_guard.py:10` réutilisé), (3) pre-score déterministe avec poids publiés (40 % opportunity + 25 % business + 15 % confidence + 10 % niche boost − 5 % effort − 5 % risk), (4) **arbitrage LLM tier `advanced`** plafonné à 1 appel/cycle avec cache 24h, fallback déterministe top-3 si LLM échoue / budget dépassé / plan Free / mode low-cost only. **Schéma de dossier d'action complet et auto-suffisant** : `why_now`, `evidence` sourcée, `estimates` (impact/confidence/effort/risk + click_gain + revenue + `estimate_basis: gsc_only|gsc+ga4|gsc+fallback`), **`success_metric` obligatoire** avec measurement_window aligné J+7/J+30/J+60/J+90, `preview.human_review_required: true` par défaut. 8 action_types stables : 6 existants (`enrich_product_facts`, `improve_schema`, `add_answer_blocks`, `add_trust_proofs`, `improve_seo_copy`, `review_commerce_data` dans `app/geo/weekly.py:21`) + 2 nouveaux (`fix_cannibalization`, `add_internal_link`). Cohérence `docs/llm-strategy.md` §2-12 vérifiée : tier advanced, cache, check_budget, plan Free dégradé, prompt YAML versionné. UI : 3 cartes côte à côte dans `app.priorities.tsx`, dépréciation `app.geo-priorities` et `app.next-best-actions`, `app.geo-risk-guard` conservée en drill-down. Endpoints : `GET /api/shops/{shop}/priorities` canonique, `geo/priorities` brut déprécié. Garde-fous : Risk Guard prioritaire (protected non proposé sans override), `forbidden_promises` exclut à l'étape 4, aucune dépendance directe GA4 (fallback transparent), pas de boucle interne LLM.
- **Files created:** `docs/priority-engine.md`.
- **Files modified:** `ROADMAP.md` (statut 133 → ✅ 2026-05-20), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** `app/priorities/engine.py` (orchestrateur 4 étapes), `config/prompts/priority_arbitrage.yaml`, route canonique `GET /priorities`, UI `app.priorities.tsx` 3 cartes, tests pre-score + fallback LLM restent à porter. Limites V1 explicites : pas de scoring par segment client, pas de calendrier marketing saisonnier, pas de batch d'actions liées.
- **Next recommended action:** Tâche 134 (AI Content Actions Simplification) — fusionne meta, descriptions, alt text, FAQ, Answer Blocks, guides courts, JSON-LD en un seul workflow de génération basé sur faits confirmés + Shopify + GSC/GA4 + hypothèses validées niche. C'est le **principal consommateur LLM de la phase** (tiers low-cost + medium selon `docs/llm-strategy.md`).

---

## Previous task

- **Date:** 2026-05-20
- **Agent:** Claude Code (Opus 4.7)
- **Goal:** Task 132 — Unified Opportunity Finder (cadrage produit/architecture, Phase 11.7).
- **Summary:** Création de `docs/opportunity-finder.md`. Décisions figées : un seul module qui répond à "quelles pages produits ACTIVE Online Store méritent une action maintenant ?". Fusion de 7 sources existantes sans réécriture : `scripts/audit/detect_gsc_opportunities.py:77`, `app/niche/gaps.py:106`, `app/niche/intent.py:390`, `app/niche/clustering.py:142`, `scripts/audit/detect_cannibalization.py:49`, `scripts/report/detect_internal_links.py:23`, `app/geo/competitors.py:62` + consommation des `recommended_actions` du score 131 et des hypothèses validées 130. **Une entrée par produit** (jamais par requête ni par cluster) avec `opportunity_score` 0-100, `tier` high/medium/low, signaux typés + evidence + source, `matched_queries`, `matched_intents`, `recommended_actions` (max 3), `niche_alerts`, `confidence`. Formule de scoring à poids publiés : GSC 30 % + keyword_gap 20 % + audit_action_pressure 15 % + intent_match 10 % + cannibalization 10 % + link_opportunity 10 % + competitor_pressure 5 %. Ajustements niche : `priority_products` +10 pts, intents non couverts +5 pts, `forbidden_promises` en alerte sans malus (le malus tombe sur Trust dans 131). Endpoint canonique `GET /api/shops/{shop}/opportunities?scope=active&top=20`. UI `app.opportunities.tsx` à créer, pages existantes (`niche`, `longtail`, `cannibalization`, `internal-links`, `geo-competitors`) conservées en drill-down via liens. Garde-fous : pas de nouveau détecteur dans cette couche, pas d'appel LLM (déterministe), `top` plafonné à 100, scope `active` par défaut, compatibilité ascendante des 7 endpoints existants.
- **Files created:** `docs/opportunity-finder.md`.
- **Files modified:** `ROADMAP.md` (statut 132 → ✅ 2026-05-20), `docs/AI_HANDOFF.md` (cette entrée).
- **Validations run:** Aucune (tâche purement documentaire).
- **Known limitations:** `app/opportunities/finder.py` (orchestrateur d'agrégation), `app/api/opportunities.py` (route canonique), UI `app.opportunities.tsx` et tests d'agrégation restent à porter par la tâche d'implémentation ultérieure et par 133 (Priority Engine consomme `opportunities`) + 137 (Dashboard).
- **Next recommended action:** Tâche 133 (Unified Priority Engine) — fusionne ICE, Revenue-Aware Prioritization, Weekly Actions, Risk Guard pour ne sortir que 3 actions prioritaires consommables directement par le marchand. Consomme l'opportunity_score et les recommended_actions cadrés en 131/132.

---

## Previous task

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
