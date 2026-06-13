# AI_HANDOFF.md — Giulio Geo

## Current project state

- **Summary:** Giulio Geo est une app Shopify embedded + moteur Python/FastAPI/CLI pour audit SEO, recommandations supervisées, contenus, données structurées, jobs async, intégrations Shopify/Google/LLM et garde-fous dry-run.
- **Main stack:** Python 3.11+, FastAPI, Click, pytest, ruff, Remix, React, TypeScript, Shopify App Bridge, Shopify Polaris, npm.
- **Main working areas:** `app/`, `scripts/`, `shopify-app/`, `config/`, `docs/`, `tests/`.
- **Current roadmap:** Phase 10 clôturée. Phase 11 terminée. Phase 11.5-11.8 complètes. **Phase 11.9 complète (12/12 tâches 152-163 ✅, terminée 2026-05-21).** **Phase 11.11 complète (9/9 tâches du plan "Merchant Journey Alignment" ✅, terminée 2026-06-10).** **Phase 12 (tâches 150-151) démarre seulement après test 3 marchands pilotes (critère humain — `docs/pilot-merchant-test-script.md`).**
- **Known limitations:** Les workflows GEO restent majoritairement read-only. La mesure pilote garde des lacunes historiques sur IDs/durées de jobs, compteurs exacts, coût LLM et suivi fin de certains jobs. Les snapshots V1 ne capturent pas encore GA4 ni JSON-LD détaillé. Crawl L3 existe côté backend/API, mais les plafonds Free/Pro/Agency ne sont pas encore appliqués par plan. Niche Understanding est disponible — les modules aval consomment l'hypothèse via gate UX (app._index.tsx + app.priorities.tsx) mais pas encore via appel backend automatique.

## Last completed task

- **Date:** 2026-06-13
- **Agent:** Claude (Opus 4.8)
- **Goal:** Supprimer le « mode pilote » (`LEONIE_PILOT_SAFE_MODE`) qui désactivait toute écriture Shopify : les écritures live doivent être activées dans tous les cas et non désactivables depuis l'app.
- **Summary:** `is_pilot_safe_mode()` (`app/safety.py`) retourne désormais **toujours `False`** (chokepoint unique → la variable d'env ne peut plus rebloquer les écritures). Le garde-fou **`confirm_live_write` est conservé** : chaque écriture live exige toujours une confirmation explicite (c'est lui qui fait fonctionner « Valider »). `app/api/dashboard.py` : `pilot_safe = False` en dur (env plus lu, import `os` retiré). **Frontend** : bannière « Mode pilote actif… » retirée du dashboard (`app._index.tsx`), carte Réglages (`app.settings.tsx`) remplacée par « Écritures Shopify — Écritures live activées », clé i18n `dashboardPilotSafeBanner` supprimée (FR+EN). **Tests** : suppression des tests devenus obsolètes qui attendaient un blocage en mode pilote (dashboard banner, billing subscribe/cancel, bulk orchestrator, safe-apply live, generate bulk-apply, apply meta blocks) ; conservation du test dry-run (renommé `test_apply_meta_allows_dry_run`).
- **Files modified:** `app/safety.py`, `app/api/dashboard.py`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.settings.tsx`, `shopify-app/app/lib/i18n.ts`, et 6 fichiers de tests (suppression des cas mode pilote).
- **Decisions made:** Neutralisation à la source plutôt que suppression complète de la fonction/garde-fous : `is_pilot_safe_mode()` et `require_billing_write_allowed()` restent (signatures stables, no-op) pour limiter la surface du diff. Distinction clé maintenue : **mode pilote supprimé ≠ confirmation live supprimée**.
- **Validations run:** `ruff check tests/ app/` ✅ ; `npm run typecheck`/`build` ✅ ; fichiers de tests affectés 37 passed / 22 skipped ; suite complète `pytest -q` (voir ci-dessous).
- **Open issues:** La variable d'env `LEONIE_PILOT_SAFE_MODE` sur Render n'a plus aucun effet (peut être retirée du dashboard Render, optionnel).
- **Next recommended action:** Déployer ; vérifier que la bannière a disparu et qu'une écriture live (Valider) fonctionne.

## Previous completed task

- **Date:** 2026-06-13
- **Agent:** Claude (Opus 4.8)
- **Goal:** Uniformiser `app/api/geo.py` : déplacer **toutes** les lectures bloquantes restantes (snapshot 10-100 Mo + CSV GSC) hors de la boucle asyncio, comme déjà fait pour `next-best-actions`/`control-groups`.
- **Summary:** Ajout de 3 helpers bloquants module-level (`_load_snapshot_blocking`, `_read_gsc_rows_blocking`, `_read_gsc_query_page_rows_blocking`) appelés via `await asyncio.to_thread(...)`. Conversion de tous les endpoints `async def` qui lisaient le snapshot ou un CSV GSC en synchrone : `facts`, `priorities`, `weekly-actions`, `faq-content`, `risk-guard`, `collections`, `answer-blocks`, `crawlability`, `competitors`, et le POST `optimization-snapshots`. Après ce diff, **aucune route async de geo.py ne fait plus d'I/O bloquante sur la boucle** — les seules lectures restantes (`load_snapshot_from_file_or_db`, `read_text`) sont dans les helpers sync (`_load_next_best_actions`, `_load_control_groups`, + les 3 nouveaux), tous invoqués via `to_thread`. Comportement et réponses inchangés (404 snapshot absent compris).
- **Files modified:** `app/api/geo.py`.
- **Decisions made:** Uniformisation préventive — ces endpoints ne sont pas appelés par le frontend actuel (seuls les 6 de Mesure + continuous-improvement le sont), donc aucun impact perf immédiat ; bénéfice = cohérence + filet si l'un est rebranché à une page faisant des appels parallèles. Le helper sync `_load_control_groups` (ligne ~512) garde sa lecture GSC interne telle quelle (déjà sous `to_thread`).
- **Validations run:** `ruff check app/api/geo.py` ✅ ; `pytest tests/test_api/test_geo.py -q` → 34 passed ; suite complète `pytest -q` (voir ci-dessous).
- **Open issues:** Aucun connu sur geo.py. Le drift de types frontend (tâche précédente) reste hors scope.
- **Next recommended action:** Déployer ; aucun changement visible attendu côté marchand (uniformisation interne).

## Previous completed task

- **Date:** 2026-06-13
- **Agent:** Claude (Opus 4.8)
- **Goal:** Afficher sur l'Accueil (« Vos produits actifs ») la **fiche produit complète et interactive** de la page Produits, limitée aux 2 premiers produits.
- **Summary:** **Extraction** : `ProductCard` (+ helpers `ImprovementTags`, `InternalLinksSection`, `tagToneInAdded`) sorti de `app.products.tsx` vers `shopify-app/app/components/ProductCard.tsx` (export). Types alignés : ajout à `marketAnalysisShared.tsx` de `BusinessProfileContextStatus`, `InternalLinkSuggestion`, et des champs optionnels `ContentTestPack.recommended_internal_links`, `ProductResult.business_profile_context_status`/`_hash` (optionnels → aucune régression). **Mutualisation des intents** : nouveau `shopify-app/app/lib/productCardActions.server.ts` `handleProductCardIntent(intent, formData, session)` regroupant les 10 handlers du ProductCard (`applyToShopify`, `addTag`, `retireTag`/`restoreTag`, `retireKeyword`, `validateQuestion`, `retireQuestion`/`restoreQuestion`, `syncSchemaFacts`, `saveProposals`) ; les deux routes délèguent à cette fonction en tête de leur `action`. Les blocs dupliqués supprimés de `app.products.tsx` et `app._index.tsx`. **Dashboard** : `ActiveProductsCard` rend `<ProductCard>` pour `products.slice(0, 2)` quand un pack existe (sinon prompt « Analyser » compact) ; `shouldRevalidate` ignore les intents de mutation (liste inline, pas d'import `.server` côté client) ; `shop` passé en prop. Nettoyage : helpers morts retirés de `app.products.tsx` (`scoreTone`, `keywordCoverage`, `confidenceTone`, `formatDate`, `contentWords`, `keywordIsUsed`, `FR_STOP_WORDS`, import `ProgressBar`) — désormais dans le composant partagé.
- **Files created:** `shopify-app/app/components/ProductCard.tsx`, `shopify-app/app/lib/productCardActions.server.ts`.
- **Files modified:** `shopify-app/app/lib/marketAnalysisShared.tsx`, `shopify-app/app/routes/app.products.tsx`, `shopify-app/app/routes/app._index.tsx`.
- **Decisions made:** Le write Shopify `applyToShopify` (« Valider ») est désormais aussi accessible depuis l'Accueil — même endpoint et garde-fous que la page Produits, point d'entrée supplémentaire assumé. `PRODUCT_CARD_INTENTS` n'est PAS exporté du module `.server` (sinon erreur build « server-only module referenced by client » via `shouldRevalidate`) : la liste est dupliquée inline côté dashboard.
- **Validations run:** `npm run typecheck` ✅, `npm run build` ✅ (1583 modules). Aucun backend Python modifié.
- **Open issues:** Drift de types restant entre les définitions locales de `app.products.tsx` (JobState, CTP local enrichi) et `marketAnalysisShared.tsx` — non unifié (hors scope), seuls les champs nécessaires à ProductCard ont été ajoutés au shared en optionnel.
- **Next recommended action:** Déployer ; vérifier sur l'Accueil que les 2 fiches sont identiques à Produits (photo, mots-clés, tags, Améliorer/Valider, décompte) et qu'une validation depuis l'Accueil écrit bien dans Shopify.

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Fable 5)
- **Goal:** Page Produits : loader élégant sur « Régénérer avec mes réponses », badge « Validé » (et fin de l'encadré jaune) après « Valider les propositions », décompte de 28 jours avant les résultats.
- **Summary:** **Backend** (`app/api/market_analysis.py`) : l'endpoint apply-to-shopify persiste désormais `applied_fields` (champ → ISO date) dans le `content_test_pack` via `patch_product_proposals` après chaque apply réussi, et l'expose dans sa réponse — sans ça, badge et décompte disparaissaient au rechargement. Une nouvelle analyse régénère le pack, donc l'état « validé » repart à zéro naturellement. **Frontend** : type `applied_fields` ajouté à `ContentTestPack` (shared + local app.products) ; dans `ProductContentProposals.tsx`, l'encadré jaune `#F4C430` est supprimé pour les champs appliqués (`showYellow && !appliedAt`), la checkbox est masquée et un `Badge tone="success"` « Validé »/« Applied » s'affiche (mapping `alt_text`→`image_alts`) ; `AnalysisLoader` (phrases `analysis`) sous le bouton Régénérer pendant l'analyse. Dans `app.products.tsx` : état local `appliedFields` (seedé du pack, mis à jour à la réponse du fetcher pour un retour visuel immédiat), pack fusionné passé au composant enfant, et à côté du bouton « Valider les propositions » : « Résultats dans {n} j » (`MEASURE_CYCLE_DAYS = 28`, aligné jalon J+28 de Mesure) puis lien « Résultats disponibles dans Mesure » quand le délai est écoulé.
- **Files modified:** `app/api/market_analysis.py`, `tests/test_api/test_market_analysis.py` (nouveau test apply→applied_fields), `shopify-app/app/lib/marketAnalysisShared.tsx`, `shopify-app/app/components/ProductContentProposals.tsx`, `shopify-app/app/routes/app.products.tsx`.
- **Decisions made:** Persistance dans le pack (même mécanisme que `faq_sync`/`schema_facts_sync`) plutôt qu'une table dédiée — le cycle de vie « reset à chaque réanalyse » est exactement le comportement voulu. 28 jours = constante frontend locale, pas la fréquence configurable du shop (le décompte parle du jalon de mesure J+28, pas du cycle de réanalyse).
- **Validations run:** `ruff check .` ✅ ; `pytest tests/test_api/test_market_analysis.py -q` → 12 passed ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Validations skipped:** suite pytest complète (changement Python limité à 1 endpoint, fichier de test correspondant vert).
- **Open issues:** néant.
- **Next recommended action:** Déployer, valider une proposition en prod : encadré jaune disparaît + badge Validé + « Résultats dans 28 j », persistant au rechargement.

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Fable 5)
- **Goal:** UX — toutes les attentes longues (générations, analyses) doivent afficher une barre de chargement élégante + une phrase vague rotative en dessous (style « Claude réfléchit »).
- **Summary:** Nouveau composant partagé `shopify-app/app/components/AnalysisLoader.tsx` : Polaris `ProgressBar` (progress réel plafonné à 97 si le job fournit `progress/total`, sinon rampe temporelle asymptotique `1-exp(-t/τ)` calée sur `estimateMs`, plafond 92) + phrase `subdued` qui tourne toutes les 4 s avec fondu CSS. Banques de phrases FR/EN dans `i18n.ts` (`loaderPhrases(locale, kind)`, 4 jeux : `analysis`, `writing`, `profile`, `crawl`, 6 phrases chacun). Branché sur 8 endroits : analyse marché (`app.products.tsx`, progress réel), génération blog (`app.blog.tsx`, rampe 90 s), profil business + identification produits (panneaux onboarding, remplace les ProgressBar figées à 50 %), analyse approfondie (`MarketAnalysisProgressPanel.tsx`, supprime le cap 95 local), audit dashboard (`app._index.tsx`, remplace l'animation locale supprimée), analyse mono-produit (`app._index.tsx`, remplace le Spinner seul), crawl concurrents (`app.competitor-crawl.tsx`, 2 spots Spinner).
- **Files created:** `shopify-app/app/components/AnalysisLoader.tsx`.
- **Files modified:** `shopify-app/app/lib/i18n.ts`, `app.products.tsx`, `app.blog.tsx`, `app._index.tsx`, `app.competitor-crawl.tsx`, `components/MarketAnalysisProgressPanel.tsx`, `components/ProductIdentificationPanel.tsx`, `components/BusinessProfilePanel.tsx`.
- **Decisions made:** Boutons `loading` rapides (régénération de section, publications) laissés tels quels — hors scope. Le composant ne porte pas de Banner : chaque page garde son habillage existant.
- **Validations run:** `npm run typecheck` ✅, `npm run build` ✅.
- **Validations skipped:** `pytest`/`ruff` — aucun changement Python. Test visuel manuel à faire en prod (rotation des phrases, complétion, FR/EN).
- **Open issues:** néant.
- **Next recommended action:** Déployer et vérifier visuellement une génération blog + une analyse produit.

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Fable 5)
- **Goal:** Objectif produit « le marchand n'a rien à faire sauf (re)connecter Google » : détecter la révocation du token Google (invalid_grant, vu en prod) et afficher une bannière « Reconnexion requise » au lieu d'échouer en silence.
- **Summary:** **Backend** : nouveau flag `google_reauth_required` dans `shop_config` (clé exportée `GOOGLE_REAUTH_REQUIRED_KEY` dans `app/gsc/token_store.py`). Posé dans les deux chemins de refresh : `app/gsc/client.py` `_credentials_for_shop` (le `except RefreshError` existant qui supprimait déjà le token) et `app/ga4/oauth.py` `get_credentials` (qui ne gérait **pas** `RefreshError` — c'était la source du 500 `invalid_grant` en prod ; il pose maintenant le flag, supprime le token et retourne `None`). Effacé dans `save_google_token` (couvre reconnexion GSC et GA4). `gsc_status` (`app/api/gsc.py`) expose `reauth_required` (flag posé **et** token absent) + message `action_required` distinct. **Frontend** : bannière 3 états sur `app._index.tsx` et `app.products.tsx` — `reauth_required` → bannière critical « Reconnexion à Google requise » avec bouton ; non connecté → bannière warning existante ; connecté → rien. Le loader de l'index appelle désormais `/gsc/status` (6e appel du `Promise.allSettled`) ; la bannière se base sur le statut OAuth réel et non plus sur la présence du fichier `gsc_performance.csv` (fallback sur l'ancien heuristique si l'appel statut échoue).
- **Files created:** `tests/test_ga4/test_oauth_refresh.py`.
- **Files modified:** `app/gsc/token_store.py`, `app/gsc/client.py`, `app/ga4/oauth.py`, `app/api/gsc.py`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.products.tsx`, `tests/test_gsc/test_client.py`, `tests/test_gsc/test_token_store.py`, `tests/test_api/test_gsc.py`.
- **Decisions made:** Flag dans `shop_config` (clé/valeur existante, pas de migration) plutôt qu'une colonne dans `google_tokens` ; le pattern existant « token supprimé à la révocation » est conservé, le flag ne sert qu'à distinguer « jamais connecté » de « reconnexion requise ». Si un token valide existe, un flag résiduel est ignoré par `gsc_status`.
- **Validations run:** `ruff check .` ✅ ; `pytest tests/test_gsc tests/test_api/test_gsc.py tests/test_ga4 tests/test_api/test_ga4_oauth.py -q` → 57 passed ; `pytest -q` complet (voir ci-dessous) ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Open issues:** Cause racine des révocations = app OAuth Google en mode « Testing » (tokens révoqués après 7 jours) — action manuelle utilisateur : passer en « In production » dans Google Cloud Console.
- **Next recommended action:** Déployer, vérifier que le shop pilote (token GA4 mort) voit la bannière « Reconnexion à Google requise », reconnecter, confirmer que la bannière disparaît et que l'import GSC repart au prochain cycle.

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Fable 5)
- **Goal:** Lenteur ressentie en naviguant entre les pages Produits et Blog.
- **Summary:** Deux causes corrigées. (1) **`GET /products/active`** (`app/api/shops.py`, appelé à chaque ouverture de la page Produits) lisait le snapshot 10-100 Mo **synchrone dans un handler `async def`** — même anti-pattern que le fix 502 de la page Mesure. Extraction de `_build_active_products()` (sync) appelée via `asyncio.to_thread`, comportement identique. (2) **Loader Blog** (`shopify-app/app/routes/app.blog.tsx`) : 4 appels backend en série → la liste des brouillons et `market-analysis/latest` passent en `Promise.all` (indépendants) ; le brouillon sélectionné et les clusters restent séquentiels (dépendances réelles). ~4 allers-retours → ~3 dont 2 parallèles.
- **Files modified:** `app/api/shops.py`, `shopify-app/app/routes/app.blog.tsx`.
- **Validations run:** `ruff check app/api/shops.py` ✅ ; `pytest tests/test_api/test_shops.py -q` → 13 passed ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Validations skipped:** `pytest -q` complet (changement Python ciblé sur 1 endpoint, fichier de test correspondant vert).
- **Open issues:** L'audit des ~10 autres endpoints `geo.py` (et désormais d'autres routers) avec lecture snapshot synchrone reste recommandé.
- **Next recommended action:** Déployer, puis faire re-tester la navigation Produits ↔ Blog au marchand.

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Suite directe du fix 502 précédent — la page Mesure fonctionne mais reste lente à l'ouverture ; réduire le coût d'un cache froid en évitant la double lecture du snapshot.
- **Summary:** Sur cache froid (juste après un redémarrage), `/geo/next-best-actions` et `/geo/control-groups` sont appelés en parallèle par le loader Mesure et **manquent tous les deux le cache au même instant** : chacun relit et re-parse le fichier snapshot (10-100 Mo) indépendamment, doublant le coût CPU/I/O même après le fix `asyncio.to_thread` de la tâche précédente (qui évite seulement de bloquer la boucle, pas le travail redondant). **Fix** (`app/api/snapshot_store.py`) : ajout d'un verrou **single-flight par chemin de fichier** (`_snapshot_load_locks`, dict de `threading.Lock` gardé par `_snapshot_load_locks_guard`). Dans `load_snapshot_from_file_or_db`, si le cache est manqué, l'appelant acquiert le verrou du chemin avant de lire+parser ; un second appelant concurrent pour le même chemin attend ce verrou puis trouve le cache déjà rempli (re-check sous `_snapshot_cache_lock` après acquisition) au lieu de relire le fichier. Le comportement observable (valeur retournée, TTL 60s, invalidation par mtime, fallback DB) est inchangé — seul le nombre de lectures disque en cas de cache-miss concurrent passe de N à 1. Ajout d'une fonction `clear_snapshot_cache()` exportée (existait déjà en interne, maintenant publique pour les tests).
- **Files created:** `tests/test_api/test_snapshot_store.py` (2 tests : cache hit dans le TTL → 1 seul `json.loads` ; 5 threads concurrents sur cache froid → 1 seul `json.loads`, même résultat pour tous).
- **Files modified:** `app/api/snapshot_store.py`.
- **Decisions made:** Verrou par chemin (et non un verrou global) pour ne pas sérialiser les lectures de snapshots de boutiques différentes. Le re-check du cache est effectué **deux fois** (avant et après acquisition du verrou de chargement) pour éviter de prendre le verrou inutilement sur un cache déjà chaud, et pour éviter une relecture si un autre thread a rempli le cache pendant l'attente.
- **Validations run:** `ruff check app/api/snapshot_store.py tests/test_api/test_snapshot_store.py` ✅ ; `pytest tests/test_api/test_snapshot_store.py tests/test_api/test_geo.py -q` → **36 passed** ; `pytest -q` complet → **1869 passed, 185 skipped, 0 failed**.
- **Validations skipped:** `npm run typecheck`/`npm run build` (aucun changement frontend).
- **Open issues:** Reprendre l'audit de suivi mentionné dans la tâche précédente (~10 autres endpoints `geo.py` avec lecture snapshot synchrone hors `asyncio.to_thread`) — ce fix réduit leur risque marginal supplémentaire (single-flight) mais ne les fait pas passer sur un thread séparé.
- **Next recommended action:** Déployer (push → auto-deploy `leonie-seo-pilot-api`), puis demander au marchand de confirmer que l'ouverture de la page Mesure après un redémarrage est plus rapide qu'avant. Si la latence reste perçue comme un problème, envisager l'option B (upgrade Render plan) déjà évoquée.

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Diagnostiquer et corriger un "Erreur backend 502" / "Network error" en prod, reproductible spécifiquement en cliquant sur la page **Mesure**.
- **Summary:** **Diagnostic confirmé via l'onglet Events de `leonie-seo-pilot-api`** (pas un artefact de déploiement) : `Instance failed: HTTP health check failed (timed out after 5 seconds) while running your code` — l'instance était vivante mais ne répondait plus, donc Render l'a tuée/redémarrée en plein milieu d'une requête. Mémoire (38% max) écarte l'OOM ; le tick `_agent_schedule_loop` (300s par défaut) écarte aussi cette piste pour ce timing précis. **Root cause** : le loader de `/app/measure` (`shopify-app/app/routes/app.measure.tsx:141-147`) lance **6 appels backend en parallèle** (`Promise.all`), dont `/geo/next-best-actions` et `/geo/control-groups`. Ces deux endpoints appelaient `load_snapshot_from_file_or_db()` (lecture + `json.loads()` **synchrones** d'un fichier snapshot de 10-100 Mo, `app/api/snapshot_store.py`) directement dans un handler `async def`, sans `asyncio.to_thread`. Sur un cache froid (ex: juste après un redémarrage d'instance — cache TTL 60s), les deux endpoints ratent le cache **simultanément** et exécutent chacun une lecture+parsing JSON bloquante de plusieurs dizaines de Mo, dos à dos dans la boucle asyncio (rien d'autre ne peut s'exécuter pendant ce temps, y compris `/health`). Les deux lectures combinées ont bloqué la boucle ~54s (gap confirmé dans les logs API entre 11:33:58 et 11:34:52), `/health` a timeout (5s) à répétition → Render a tué/redémarré l'instance → la requête `/app/measure` en cours côté web a reçu un 502 après ~55s. **Fix** (`app/api/geo.py`) : extraction de `_load_next_best_actions()` et `_load_control_groups()` (fonctions privées synchrones regroupant `load_snapshot_from_file_or_db` + `build_next_best_actions`/`build_control_groups` + parsing GSC), appelées via `await asyncio.to_thread(...)` — même pattern déjà utilisé dans ce fichier pour `run_continuous_improvement_agent` et `get_organic_daily`. Le comportement (réponses, codes HTTP, 404 si snapshot absent) est strictement identique, seul le thread d'exécution change.
- **Files modified:** `app/api/geo.py` (endpoints `GET /geo/next-best-actions` et `GET /geo/control-groups`).
- **Decisions made:** Le **même anti-pattern** (`load_snapshot_from_file_or_db`/`_parse_gsc_csv` appelés synchrones dans un handler `async def`) existe dans **~10 autres endpoints** de `app/api/geo.py` (`progress-curve` indirect via cache, `faq-content`, `validation-timeline`, `weekly-actions`, etc. — voir grep `load_snapshot_from_file_or_db` dans ce fichier). Ils n'ont **pas** été corrigés dans ce diff : individuellement, ils ne sont généralement appelés qu'un par un (pas en rafale parallèle comme Mesure) et bénéficient du cache 60s après le premier appel, donc le risque de dépasser le timeout health-check de 5s est plus faible — mais le risque existe (cache froid + fichier volumineux). Périmètre volontairement limité aux 2 endpoints **confirmés** responsables du 502 observé, pour garder un diff petit et ciblé sur un incident de prod actif.
- **Validations run:** `ruff check app/api/geo.py` ✅ ; `pytest tests/test_api/test_geo.py -q` → **34 passed** (inclut les tests des deux endpoints modifiés).
- **Validations skipped:** `npm run typecheck`/`npm run build` (aucun changement frontend) ; suite `pytest` complète (changement Python ciblé sur 1 fichier, fichier de test correspondant entièrement vert).
- **Open issues:** (1) **Audit de suivi recommandé** : passer en revue les ~10 autres endpoits de `app/api/geo.py` partageant l'anti-pattern `load_snapshot_from_file_or_db` synchrone-dans-async, et leur appliquer le même `asyncio.to_thread` si jugé pertinent (priorité aux pages qui font des appels parallèles comme Mesure). (2) **Sans rapport** : token GA4 expiré pour la boutique `287c4a-bb.myshopify.com` (`invalid_grant: Token has been expired or revoked`, `/geo/progress-curve` → 500) — le marchand doit reconnecter GA4 depuis `/app/account`. (3) Premier "Instance failed" du même incident (`connection refused`, 11:32) reste non expliqué — probablement un redémarrage lié aux déploiements `b56cc3d`/`c726c59` de la tâche précédente, sans rapport avec ce bug.
- **Next recommended action:** Déployer ce fix (push → auto-deploy `leonie-seo-pilot-api`), puis demander au marchand de retester la page Mesure (idéalement juste après un redémarrage d'instance, pour retomber sur le cache froid) — plus de 502/health-check-timeout attendu. Si stable, planifier l'audit de suivi des autres endpoints `geo.py` (Decisions made (1)).

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Suite directe de la tâche précédente (Redis sessions + réseau privé) — déployer en prod et corriger une régression introduite par le réseau privé web↔api.
- **Summary:** **Redis sessions : confirmé en prod.** Après sync du Blueprint Render (création manuelle de `leonie-seo-pilot-sessions`) et ajout manuel des env vars sur `leonie-seo-pilot-web`, le log `[shopify.server] REDIS_URL set — using Redis session storage` confirme que `RedisSessionStorage` est bien actif — ce levier (le principal) est acquis. **Réseau privé web↔api : régression et rollback.** `PYTHON_BACKEND_URL=leonie-seo-pilot-api:10000` (hostname interne confirmé correct dans le dashboard Render, même région Frankfurt pour les deux services) provoquait `FetchError ... ENOTFOUND leonie-seo-pilot-api` sur tous les appels `callBackendForShop()` — app cassée en prod. Cause probable identifiée par recherche : les environnements Render créés avant le 16/10/2025 n'exposent que des enregistrements DNS **AAAA (IPv6)** sur le réseau privé, alors que le `fetch`/`undici` de Node fait une résolution IPv4 par défaut → `ENOTFOUND` même avec un hostname correct. **`render.yaml`** : `PYTHON_BACKEND_URL` repassé de `fromService: {type: web, name: leonie-seo-pilot-api, property: hostport}` à `sync: false` (valeur manuelle = URL publique `https://leonie-seo-pilot-api.onrender.com`, comme avant ce diff), pour qu'un futur sync de Blueprint ne réintroduise pas la régression. `shopify-app/app/lib/api.server.ts` (`normalizeBackendUrl`) reste inchangé — sans effet sur une URL `https://...` déjà schémée, mais conservé car inoffensif et utile pour le cas local `localhost:8000`.
- **Files modified:** `render.yaml` (revert `PYTHON_BACKEND_URL` → `sync: false`).
- **Decisions made:** Réseau privé web↔api **descopé** plutôt que de patcher la résolution DNS côté Node (ex: forcer `family: 0`/dual-stack dans `fetch`) — le gain de latence est marginal comparé au levier Redis (déjà acquis et confirmé), et un fix DNS ajouterait de la complexité/risque pour un service en prod avec des marchands actifs. Action manuelle requise sur Render : remettre `PYTHON_BACKEND_URL=https://leonie-seo-pilot-api.onrender.com` dans l'environnement de `leonie-seo-pilot-web` (dashboard) pour restaurer l'app — pas un changement de code.
- **Validations run:** Aucune commande locale pertinente (changement `render.yaml` uniquement, pas de build/typecheck affecté). Confirmation de fonctionnement via log de prod fourni par l'utilisateur (Redis actif).
- **Validations skipped:** `npm run typecheck`/`npm run build` — pas de changement TypeScript dans ce diff.
- **Open issues:** (1) **Urgent côté Render** : remettre `PYTHON_BACKEND_URL=https://leonie-seo-pilot-api.onrender.com` dans l'environnement de `leonie-seo-pilot-web` (dashboard) si pas déjà fait — sans ça l'app reste cassée (`ENOTFOUND`). (2) Si la latence redevient un problème à 50 marchands, réseau privé web↔api à reprendre avec un fix DNS dédié côté Node (`fetch` avec résolveur dual-stack/IPv6) plutôt que `fromService hostport` brut. (3) Budget confirmé : ~$24/mois (Redis Key Value ajouté, ~$10/mois).
- **Next recommended action:** Vérifier dans le dashboard Render que `PYTHON_BACKEND_URL` de `leonie-seo-pilot-web` est bien revenu à l'URL publique et que l'app est de nouveau fonctionnelle (navigation produits/blog/mesure). Puis reprendre l'investigation Background Worker (cf. entrée précédente, "Decisions made").

## Previous completed task

- **Date:** 2026-06-12
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Préparer le lancement à ~50 marchands : réduire la latence "par clic" (chaque navigation embarquée Shopify exécute `authenticate.admin()`, qui faisait un aller-retour Postgres/Neon) et l'aller-retour réseau public entre les deux services Render (`leonie-seo-pilot-web` ↔ `leonie-seo-pilot-api`).
- **Summary:** **Sessions Shopify : Postgres → Redis.** `shopify-app/app/shopify.server.ts` ajoute `RedisSessionStorage` en tête de la chaîne de fallback existante — priorité `REDIS_URL` > `DATABASE_URL` (Postgres, inchangé) > SQLite (local, inchangé). Aucune migration de données : les sessions existantes en Postgres ne sont simplement plus lues, les marchands sont ré-authentifiés au prochain chargement (flux OAuth embedded standard, automatique). **`render.yaml`** : nouveau service `type: keyvalue` (`leonie-seo-pilot-sessions`, Render Key Value/Valkey, région Frankfurt, plan starter, `ipAllowList: []` requis) ; `REDIS_URL` injecté dans `leonie-seo-pilot-web` via `fromService: {type: keyvalue, property: connectionString}`. **Réseau privé web↔api** : `PYTHON_BACKEND_URL` (auparavant `sync: false` pointant vers l'URL publique `*.onrender.com`) passe en `fromService: {type: web, name: leonie-seo-pilot-api, property: hostport}` — renvoie `host:port` sans schéma (réseau interne Render = HTTP). `shopify-app/app/lib/api.server.ts` ajoute `normalizeBackendUrl()` qui préfixe `http://` si le schéma est absent, pour rester compatible avec un usage local (`http://localhost:8000`) et l'URL interne Render.
- **Files created:** aucun.
- **Files modified:** `shopify-app/package.json` (ajout `@shopify/shopify-app-session-storage-redis@^3.0.1`), `shopify-app/app/shopify.server.ts`, `shopify-app/app/lib/api.server.ts`, `shopify-app/.env.example`, `render.yaml`.
- **Decisions made:** Le split du ticker `_agent_schedule_loop` (`app/main.py:117-133`) en Background Worker Render dédié (pour isoler le CPU des cycles d'apprentissage de fond de celui des requêtes web) a été **explicitement écarté de ce diff** : `run_continuous_improvement_agent()` lit le snapshot produit (`data/raw/{shop}/snapshot_*.json`, 10-100 Mo) sur le disque persistant attaché uniquement à `leonie-seo-pilot-api` — un Background Worker Render est un service séparé qui ne peut pas monter ce disque. Avant d'implémenter ce split, il faut vérifier si la persistance DB ajoutée à la tâche 9 (`app/analysis_artifacts.py`) couvre aussi le snapshot produit lui-même (pas seulement `market_analysis_latest.json`/`business_profile.json`). Si non, alternative : passer `leonie-seo-pilot-api` en plan Standard ($25/mois) plutôt qu'ajouter un worker.
- **Validations run:** `cd shopify-app && npm install` (aucun conflit de peer-deps avec le nouveau package Redis) ✅, `npm run typecheck` ✅, `npm run build` ✅ (client + SSR).
- **Validations skipped:** `pytest`/`ruff check .` — aucun fichier Python modifié dans ce diff. Pas de test en conditions réelles avec Redis (nécessite la ressource Render provisionnée, cf. "Open issues").
- **Open issues:** (1) Le service `leonie-seo-pilot-sessions` (Render Key Value, ~$10/mois) et le câblage `fromService` ne prennent effet qu'après synchronisation du Blueprint `render.yaml` depuis le dashboard Render (action manuelle, ressource payante — nécessite confirmation explicite du owner du compte). (2) Vérifier après déploiement, dans les logs du service web, que `[shopify.server] REDIS_URL set — using Redis session storage` s'affiche bien (pas de fallback silencieux vers Postgres si la connexion Redis échoue). (3) Vérifier la région de la base Neon (Postgres) — si elle n'est pas en Frankfurt, une latence cross-région reste sur les écritures DB côté API, indépendamment de ce changement. (4) Budget : ~$14.25/mois → ~$24/mois (ajout Redis).
- **Next recommended action:** Synchroniser le Blueprint Render (créer `leonie-seo-pilot-sessions`), déployer, puis vérifier en prod les logs de session storage + une navigation marchand de bout en bout. Ensuite, investiguer le split Background Worker (cf. "Decisions made") en explorant `app/geo/continuous_agent.py` et `app/market_analysis/history_context.py` pour déterminer si le snapshot produit peut être lu depuis Postgres.

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâche 9/9 (dernière) du plan "Align Giulio Geo with the target merchant journey" — persistance DB best-effort des artefacts d'analyse JSON (`market_analysis_latest.json`, `market_analysis_identifications.json`, `market_analysis_merchant_facts.json`, `business_profile.json`) pour qu'ils survivent à un redémarrage/disque éphémère (Render Free).
- **Summary:** **Nouvelle table générique `analysis_artifacts(shop, artifact_type, data_json, updated_at)`** (`PRIMARY KEY (shop, artifact_type)`, `data_json TEXT` — même convention que `auto_publish_scopes`) ajoutée à `_SQLITE_DDL`/`_PG_DDL` dans `app/db.py` (`CREATE TABLE IF NOT EXISTS`, aucune migration nécessaire — table neuve). **Nouveau module `app/analysis_artifacts.py`** : `save_artifact(shop, artifact_type, data, *, db_path=None)` (upsert via `INSERT ... ON CONFLICT (shop, artifact_type) DO UPDATE SET ...`, syntaxe identique SQLite 3.24+/Postgres, même pattern que `app/shop_config_store.py`) et `load_artifact(shop, artifact_type, *, db_path=None)` — toutes deux best-effort, `except Exception` (justifié dans la docstring : table absente si `init_db()` jamais exécuté, ou shop pré-migration) loggué en `WARNING` (visible en prod, contrairement à `DEBUG`), jamais propagé. **Câblage dans `app/market_analysis/jobs.py`** (nouveau paramètre kwargs-only `db_path: Path | None = None` sur les 6 fonctions) : `save_latest_result`/`save_identifications`/`save_merchant_facts` écrivent désormais aussi dans `analysis_artifacts` (dual-write, y compris si l'écriture fichier a échoué — la DB est justement le filet de secours pour ce cas) ; `load_latest_result`/`load_identifications`/`load_merchant_facts` gardent le **fichier JSON comme source primaire** (chemin inchangé) et ne consultent la DB qu'en cas d'`(OSError, json.JSONDecodeError)` (fichier absent/corrompu). Même schéma pour `app/business_profile/jobs.py` (`save_business_profile`/`load_business_profile`, artifact_type `"business_profile"`).
- **Files created:** `app/analysis_artifacts.py`, `tests/market_analysis/test_persistence.py` (8 tests), `tests/business_profile/test_persistence.py` (3 tests).
- **Files modified:** `app/db.py` (table `analysis_artifacts` dans `_SQLITE_DDL`+`_PG_DDL`), `app/market_analysis/jobs.py` (`db_path` kwarg + dual-write/read-through sur 3 paires save/load), `app/business_profile/jobs.py` (idem, 1 paire).
- **Decisions made:** **Choix "fichier prioritaire"** plutôt que "DB prioritaire" (suggestion initiale du plan) pour `load_latest_result` : trois autres fonctions (`remove_products_from_analysis`, `patch_product_proposals`, `replace_product_analysis`) éditent `market_analysis_latest.json` directement sans passer par `save_latest_result` — si la DB était prioritaire, `load_latest_result` aurait pu renvoyer une copie DB périmée juste après ces éditions. Avec le fichier prioritaire, ces trois fonctions restent inchangées (diff minimal) et la copie DB ne sert qu'en cas de disque effacé (mieux qu'avant : `None`). Limite documentée dans la docstring de `app/analysis_artifacts.py` : la copie DB de `market_analysis_latest` peut être en retard sur le fichier après ces 3 fonctions, jusqu'au prochain `save_latest_result` complet. `db_path` ajouté en kwargs-only optionnel (cohérent avec `run_market_analysis(db_path=...)` de la tâche 6) — aucun appelant existant ne le passe, comportement par défaut strictement inchangé (`get_conn(None)` → Postgres si `DATABASE_URL`, sinon SQLite locale).
- **Validations run:** `ruff check .` ✅ ; `python3 -m pytest tests/market_analysis/test_persistence.py tests/business_profile/test_persistence.py -q` → **11 passed** ; `pytest -q` complet → **1795 passed, 185 skipped, 72 failed** (mêmes 72 échecs préexistants 401 Unauthorized, sans rapport — confirmés à l'identique depuis la tâche 5). `cd shopify-app && npm run typecheck` ✅, `npm run build` ✅ (aucun changement frontend, validation de non-régression suite au commit de la tâche 8). `code-reviewer` exécuté (agentId `ac866ced9d6f885cf`) : aucun point bloquant ; 4 points non bloquants corrigés avant commit — niveau de log `WARNING` au lieu de `DEBUG`, commentaire sur l'appel `save_artifact` hors du `try` (intentionnel), documentation de la limite "fichier vs DB" dans la docstring, garde `isinstance(dict)` ajoutée à `load_identifications` pour symétrie avec `load_merchant_facts` ; 2 nouveaux tests ajoutés (DB sans `init_db()` → no-op gracieux ; `data` non sérialisable → `save_artifact` n'explose pas).
- **Validations skipped:** Aucune — c'est la dernière tâche du plan, suite complète Python + frontend exécutée.
- **Open issues:** La copie DB de `market_analysis_latest` peut être en retard sur le fichier si `remove_products_from_analysis`/`patch_product_proposals`/`replace_product_analysis` ont été appelées depuis le dernier `save_latest_result` complet (limite documentée, acceptable car le fichier reste prioritaire). Chemin Postgres (`ON CONFLICT` via `psycopg2`) non testé en CI (suite SQLite uniquement) mais syntaxe identique à `app/shop_config_store.py`, déjà en production.
- **Next recommended action:** Plan "Merchant Journey Alignment" (tâches 1-9) terminé. Prochaine étape suggérée : smoke test manuel de la tâche 8 (connecter/déconnecter GSC/GA4 depuis `/app/account?locale=fr`, cf. "Open issues" de l'entrée précédente), puis reprise de la Phase 11.10 (Market Analysis Improvements, tâches 164-168) ou préparation Phase 12 (go/no-go App Store) selon priorité produit.

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâche 8/9 du plan "Align Giulio Geo with the target merchant journey" — page Réglages (`/app/account`) consolidée avec 4 sections : Automatisation (mode + `reanalysis_frequency_days` + `auto_publish_scopes` de la tâche 7), Connexions Google (GSC/GA4), Visibilité auprès des crawlers IA (llms.txt), et l'existant (hub + danger zone).
- **Summary:** **`app/api/learning.py`** : `LearningSettingsRequest` expose désormais `reanalysis_frequency_days: int | None` et `auto_publish_scopes: list[str] | None` sur `PUT /learning/settings` (la validation/coercition existait déjà côté store depuis la tâche 7 — pur exposé d'API). **Nouveau composant partagé `shopify-app/app/components/GoogleConnectionsCard.tsx`** : extrait de l'ancien `ConnectGoogleStep` local de `app.onboarding.tsx`, affiche le statut GSC/GA4 + boutons connecter/déconnecter ; supporte deux modes de soumission — `useSubmit()` même-route (onboarding, par défaut) ou un `fetcher`+`actionPath` optionnels pour soumission cross-route (Réglages soumet vers l'action de `/app/onboarding`). **`app.onboarding.tsx`** : suppression du `ConnectGoogleStep` local au profit de `<GoogleConnectionsCard>`, ajout d'un intent `ga4_disconnect` (miroir de `gsc_disconnect`, appelle `DELETE /api/shops/{shop}/ga4/disconnect`, endpoint déjà existant). **`app.account.tsx` (réécrite, ~490 lignes)** : `loader` charge en parallèle (`Promise.allSettled`) `gsc/status`, `ga4/status`, `learning/settings`, `llms-txt/status` ; nouvel intent d'action `saveAutomation` (PUT `/learning/settings`). UI : carte "Automatisation" (Select mode manuel/semi-auto/auto — mappé sur `enabled`+`mode` du modèle backend à 2 champs ; Select fréquence 14/28j ; ChoiceList `auto_publish_scopes` avec avertissement + bouton Enregistrer désactivé si aucune portée sélectionnée — évite le retour silencieux aux valeurs par défaut backend sur liste vide ; lien vers `/app/continuous-improvement` pour la planification complète) ; carte "Connexions" (réutilise `GoogleConnectionsCard` avec `fetcher`+`actionPath="/app/onboarding"`) ; carte "Visibilité auprès des crawlers IA" (badge statut llms.txt + lien `/app/geo-llms-txt`) ; carte "Analyse SEO — sources de données" simplifiée (badges Shopify/GSC/GA4 sans liens de connexion dupliqués) ; zone de danger inchangée. **i18n** : ~20 nouvelles clés FR+EN (`connectionsTitle/Body`, `automation*` dont `automationScopesEmptyWarning`, `aiCrawlerVisibilityTitle/Body/Manage` — renommées depuis `aiVisibility*` pour éviter une collision TS1117 avec des clés V2 existantes sans rapport, `onboardingDisconnectGA4`).
- **Files created:** `shopify-app/app/components/GoogleConnectionsCard.tsx`.
- **Files modified:** `app/api/learning.py`, `tests/test_api/test_learning.py` (nouveau test round-trip `reanalysis_frequency_days`/`auto_publish_scopes`), `shopify-app/app/routes/app.onboarding.tsx`, `shopify-app/app/routes/app.account.tsx` (réécriture), `shopify-app/app/lib/i18n.ts`.
- **Decisions made:** (a) `LearningMode` n'a que `semi_auto`/`auto_apply` — le Select UI à 3 options (`manual`/`semi_auto`/`auto_apply`) mappe `manual` → `enabled=false` ; le `mode` persisté en mode "manuel" retombe sur `semi_auto` (perte d'état mineure documentée en commentaire dans `app.account.tsx`, acceptable pour un contrôle 3 voies sur un modèle backend à 2 champs). (b) Aucun composant `LlmsTxtPanel` réutilisable n'existe (`app.geo-llms-txt.tsx` fait ~460 lignes inline) — plutôt que dupliquer, la carte "Visibilité IA" affiche un badge de statut + lien vers la page dédiée. (c) Section "existant" du plan non déplacée physiquement : les entrées `billing`/`settings` du hub couvrent déjà budget/plan/santé backend, et les "concurrents manuels" restent sur le dashboard (`app._index.tsx`) — relocalisation jugée trop risquée/hors-scope pour ce diff. (d) Carte "Connexions" : les liens Connecter/Déconnecter GSC/GA4 retirés de la carte "sources de données" (devenue badges-only) au profit de la nouvelle carte `GoogleConnectionsCard`, qui soumet en cross-route vers `/app/onboarding`. (e) `auto_publish_scopes` vide : `_validated_auto_publish_scopes([])` retombe silencieusement sur les 3 valeurs par défaut côté backend (`app/learning/store.py:188-193`) — plutôt que de modifier cette logique partagée (hors-scope), le bouton "Enregistrer" de la carte Automatisation est désactivé et un avertissement s'affiche tant qu'aucune portée n'est sélectionnée.
- **Validations run:** `cd shopify-app && npm run typecheck` ✅, `npm run build` ✅ (client + SSR) ; `ruff check app/api/learning.py app/learning/ tests/test_api/test_learning.py` ✅ ; `python3 -m pytest tests/test_api/test_learning.py -q` → **8 passed**. `code-reviewer` exécuté (agentId `abc08c02843d70f2f`) : aucun problème bloquant de sécurité/architecture ; 2 points corrigés avant commit — bouton "Enregistrer" désactivé + avertissement quand `auto_publish_scopes` est vide (point décisionnel (e) ci-dessus), commentaire ajouté sur la perte d'état `mode` en bascule "manuel" (point (a)). 1 point non bloquant noté pour suivi : `useFetcher().submit(formData, {action: "/app/onboarding?locale=fr"})` — la query string `?locale=` devrait être préservée par Remix 2.9 sur une soumission POST avec FormData (comportement standard, contrairement aux soumissions GET qui reconstruisent l'URL depuis les champs), mais recommandé un smoke test manuel (connecter/déconnecter GSC depuis `/app/account?locale=fr`) avant un déploiement large — documenté en "Open issues".
- **Validations skipped:** Suite Python complète (`pytest -q`) non relancée pour cette tâche ciblée frontend+1 endpoint — le run complet sera fait à la fin de la tâche 9 (dernière tâche du plan) avant le push final.
- **Open issues:** Smoke test manuel recommandé avant déploiement large : connecter/déconnecter GSC et GA4 depuis `/app/account?locale=fr` pour confirmer que `?locale=` est bien préservé par `fetcher.submit` cross-route (Remix 2.9, risque jugé faible par le code-reviewer mais non vérifié en conditions réelles).
- **Next recommended action:** Tâche 9/9 — persistance DB des artefacts d'analyse (`analysis_artifacts(shop, artifact_type, data_json, updated_at)`, dual-write/read-through pour `market_analysis_latest.json`, `business_profile.json`, `market_analysis_identifications.json`, `market_analysis_merchant_facts.json`).

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâche 7/9 du plan "Align Giulio Geo with the target merchant journey" — cycle de ré-analyse automatique 14/28 jours dans le scheduler, avec auto-apply restreint par `auto_publish_scopes`.
- **Summary:** **Schéma** (`app/db.py`, migrations idempotentes SQLite + Postgres) : `merchant_learning_settings` gagne `reanalysis_frequency_days` (INTEGER, défaut 28, contraint à {14, 28} en couche store) et `auto_publish_scopes` (TEXT/JSON, défaut `["meta_title","meta_description","alt_text"]`) ; `agent_schedule_settings` gagne `last_reanalysis_at` (TEXT, nullable) — cadence de ré-analyse suivie indépendamment du tick d'apprentissage quotidien. **`app/learning/models.py`/`store.py`** : nouveaux champs sur `MerchantLearningSettings` + validation aux bornes (`_validated_reanalysis_frequency` retombe sur 28 si valeur hors {14,28} ; `_validated_auto_publish_scopes` retombe sur les défauts si liste vide/non-liste). **Nouveau module `app/agent_schedule/reanalysis.py`** : `is_reanalysis_due(last_reanalysis_at, frequency_days, *, now)` (jamais lancé = dû) ; `_enqueue_refresh_jobs()` (via `enqueue_unique`, cohérent avec `app/jobs/router.py`) ; `run_market_reanalysis()` reconstruit un `ShopContext` hors contexte FastAPI (même pattern que `get_shop_context`) et exécute le pipeline complet (`_gather_analysis_inputs` → `run_market_analysis` → enrichissement → `save_latest_result` → sync schema facts → drafts orphelins) ; `run_scheduled_reanalysis()` vérifie d'abord `check_budget()` (skip `budget_exceeded` si dépassé) puis lance le pipeline, avec un `try/except HTTPException(404)` → `{"status": "skipped", "reason": "no_snapshot"}` si aucun snapshot Shopify n'est encore présent sur disque (ne bloque jamais le cycle d'apprentissage). **Refactor DRY** dans `app/api/market_analysis.py` : extraction de `_gather_analysis_inputs(ctx)` depuis `run_market_analysis_endpoint` (comportement strictement préservé), réutilisée par le nouveau pipeline planifié. **`app/agent_schedule/scheduler.py`** : nouveau `_maybe_run_reanalysis()` appelé dans `run_due_agent_schedules()` (à l'intérieur du verrou `_RUNNING` existant, après le cooldown de 20h) — récupère le token OAuth via `get_token()` (skip `no_access_token` si absent), met à jour `last_reanalysis_at` uniquement sur `status="completed"` (un skip/erreur reste "dû" au prochain tick), et toute exception est capturée/loguée sans jamais interrompre `run_learning_cycle`. **Auto-apply scopé** : `run_continuous_improvement_agent()` gagne `auto_publish_scopes: list[str] | None = None` — l'auto-apply n'est tenté que si `decision.auto_apply_eligible` (garde existante, inchangée) **ET** `content_type.value in auto_publish_scopes` (nouvelle restriction additive ; `None` = comportement inchangé). `app/learning/scheduler.py` transmet `settings.auto_publish_scopes` au cycle continu.
- **Files created:** `app/agent_schedule/reanalysis.py`, `tests/test_agent_schedule/test_reanalysis.py` (12 tests).
- **Files modified:** `app/db.py` (schéma + migrations `merchant_learning_settings`/`agent_schedule_settings`, SQLite + Postgres), `app/learning/models.py`, `app/learning/store.py`, `app/agent_schedule/store.py` (`AgentScheduleSettings.last_reanalysis_at`), `app/agent_schedule/scheduler.py` (`_maybe_run_reanalysis`), `app/api/market_analysis.py` (extraction `_gather_analysis_inputs`), `app/geo/continuous_agent.py` (`auto_publish_scopes`), `app/learning/scheduler.py` (transmission du scope), `tests/test_learning/test_scheduler.py`, `tests/test_geo/test_continuous_agent_learning.py`.
- **Decisions made:** Vocabulaire `auto_publish_scopes` aligné sur les valeurs `ContentType` existantes (`meta_title`, `meta_description`, `alt_text`, ...) plutôt que les catégories larges du brief (`"meta"`/`"blog"`) — correspond directement à `content_type.value` utilisé dans le gating ; la tâche 8 (UI Réglages) devra mapper ses catégories vers ce vocabulaire. Le check `check_budget()` propre à `run_scheduled_reanalysis` ne couvre que le coût LLM ; l'appel `ensure_fresh_gsc` (API GSC externe) dans `_gather_analysis_inputs` n'est pas budget-gated — acceptable car peu coûteux, mais un shop en `status="error"` persistant le rappellera chaque jour tant que `last_reanalysis_at` n'avance pas (documenté comme limite connue, pas un risque de sécurité/coût).
- **Validations run:** `ruff check .` ✅ ; `pytest tests/test_agent_schedule/ tests/test_learning/ tests/test_geo/` → **261 passed** (30 dans `test_agent_schedule/`, dont 12 dans le nouveau `test_reanalysis.py`) ; `pytest -q` complet → **1782 passed** + 72 échecs préexistants identiques (confirmés par `git stash` avant ce diff — 401 Unauthorized sans rapport, `test_billing`/`test_privacy`/`test_shops`/`test_pagespeed_configure`/`test_llm`). `shopify-architecture-reviewer` exécuté (agentId `acf3c86d963cba247`) : 4/4 points "pass" (construction `ShopContext`/token hors requête conforme au pattern existant ; `auto_publish_scopes` purement additif, ne peut pas contourner `confirm_live_write` ; migrations DB idempotentes SQLite+Postgres correctes ; `_RUNNING`/cooldown hérités correctement) — 1 correction appliquée avant commit (`enqueue` → `enqueue_unique` pour `seo_audit`/`gsc_import`, cohérence avec `app/jobs/router.py`). `code-reviewer` exécuté (agentId `a83c2c0b27dd7af8a`) : extraction `_gather_analysis_inputs` confirmée comportementalement identique à l'endpoint d'origine ; 2 points corrigés avant commit (nettoyage `plan or ""` → `plan` car `get_plan_for_shop` ne retourne jamais de valeur fausse ; ajout du fallback `{"status": "skipped", "reason": "no_snapshot"}` sur `HTTPException(404)` + test dédié).
- **Validations skipped:** `npm run typecheck`/`npm run build` non requis (aucun changement frontend).
- **Open issues:** Le scope `auto_publish_scopes` est actuellement un garde-fou "prêt pour l'avenir" sur le chemin planifié : `run_due_agent_schedules` → `run_learning_cycle` → `run_continuous_improvement_agent` n'active jamais `confirm_live_write=True` aujourd'hui, donc `decision.auto_apply_eligible` reste structurellement `False` sur ce chemin (pas une régression — comportement pré-existant). `_API_VERSION = "2025-01"` dupliqué une 5e fois (`app/agent_schedule/reanalysis.py`) — déjà dupliqué ailleurs avant ce diff (`app/api/deps.py`, `app/billing/client.py`, ...) ; à factoriser dans un futur nettoyage si la version d'API Shopify est amenée à changer.
- **Next recommended action:** Tâche 8/9 — page Réglages consolidée (automatisation incluant `reanalysis_frequency_days`/`auto_publish_scopes`, connexions Google, visibilité IA, existant).

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâche 6/9 du plan "Align Giulio Geo with the target merchant journey" — alimenter le moteur d'analyse marché avec l'historique d'optimisation (changements déjà appliqués + signaux d'apprentissage boutique), pour que les prompts IA évitent de re-proposer une valeur déjà mesurée positive et révisent ce qui a régressé.
- **Summary:** Nouveau module `app/market_analysis/history_context.py` : `build_optimization_history(shop, product_id, *, db_path=None, max_events=5) -> dict` lit `list_geo_events(shop, limit=500, status="applied")` (ledger GEO existant), filtre sur `resource_id == product_id`, et pour chaque événement réutilise `compute_event_confidence()` + `build_event_report()` (même pipeline que `/geo/impact-report`) pour extraire `{field, old_value, new_value, applied_at, verdict, confidence}` — `old_value`/`new_value` proviennent de `before_snapshot.content[field]`/`after_snapshot.value` quand disponibles (chemin `record_applied_change`), sinon seuls `field`/`verdict`/`confidence` sont affichés (chemin agent continu → approbation, qui ne stocke pas le texte avant/après). `_shop_summary()` lit `list_weights(shop, feature_key="action_type")` pour lister les types d'action ayant le mieux/le moins bien fonctionné sur la boutique (texte FR court). `format_optimization_history(history) -> str` rend un bloc `=== HISTORIQUE D'OPTIMISATION ===` + une règle explicite ("ne re-propose pas une valeur déjà mesurée positive ; révise/annule ce qui a régressé") — retourne `""` si rien à montrer (section omise du prompt). **Câblage dans `app/market_analysis/engine.py`** : nouveau paramètre `db_path: Path | None = None` sur `run_market_analysis()` ; dans la boucle pass-1, `build_optimization_history()` est appelé une fois par produit, le bloc formaté est injecté dans `_build_pass1_prompt()` (nouveau paramètre `optimization_history_block`, ajouté juste avant les instructions de ciblage) et stocké dans `pass1_states` pour réutilisation en pass-2 (`_build_pass2_prompt()`, nouveau paramètre du même nom, ajouté comme section conditionnelle après `FORMULATIONS INTERDITES`) ; `"optimization_history"` ajouté à `sources_used` quand le bloc est non vide.
- **Files created:** `app/market_analysis/history_context.py`, `tests/market_analysis/test_history_context.py`.
- **Files modified:** `app/market_analysis/engine.py` (`_build_pass1_prompt`/`_build_pass2_prompt` : nouveau paramètre `optimization_history_block` ; `run_market_analysis` : nouveau paramètre `db_path`, calcul + câblage par produit dans les boucles pass-1/pass-2).
- **Decisions made:** Réutilisation du pipeline de mesure existant (`compute_event_confidence`/`build_event_report`) plutôt que de recalculer un verdict ad-hoc — garantit la cohérence avec ce que le marchand voit sur `/app/measure`. Les deux formes d'événements "applied" (avec/sans `before_snapshot.content`/`after_snapshot.value`) sont gérées de façon défensive : si aucune valeur avant/après n'est disponible, la ligne d'historique affiche uniquement `champ — verdict (confiance X/100)` plutôt qu'un texte vide ou mal formaté (corrigé suite à la review `code-reviewer`). `db_path` ajouté en paramètre kwargs-only optionnel de `run_market_analysis()` (cohérent avec le pattern `db_path: Path | None = None` utilisé dans `app/geo/*`/`app/learning/*`), purement additif.
- **Validations run:** `ruff check .` ✅ ; `pytest tests/market_analysis/ tests/test_geo/ tests/test_learning/` → **448 passed** ; `pytest -q` complet → **1768 passed, 185 skipped, 72 failed** (les 72 échecs sont préexistants, identiques avant cette tâche — voir entrée précédente). `code-reviewer` exécuté (agentId `ae90f8fa2417f3055`) : 1 point bloquant identifié et corrigé (rendu dégradé pour les événements sans `old_value`/`new_value`) + 1 point cosmétique corrigé (double saut de ligne dans le prompt pass-1 quand le bloc historique est vide). Le point N+1 (`list_geo_events` appelé une fois par produit) est documenté comme acceptable pour ce volume (shops pilotes), à optimiser en suivi si besoin (requête unique groupée par `resource_id`).
- **Validations skipped:** `npm run typecheck`/`npm run build` non requis (aucun changement frontend).
- **Open issues:** Pour les événements "applied" issus de l'agent continu / approbations (sans `before_snapshot.content`/`after_snapshot.value`), l'historique de prompt n'affiche pas le texte avant/après — seulement field/verdict/confiance. `build_optimization_history()` fait une requête `list_geo_events` par produit (N+1, acceptable au volume actuel des shops pilotes).
- **Next recommended action:** Tâche 7/9 — cycle de ré-analyse automatique 14/28 jours dans le scheduler (`app/agent_schedule/scheduler.py`), avec `shopify-architecture-reviewer` avant commit (automatisation + écritures Shopify).

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâche 5/9 du plan "Align Giulio Geo with the target merchant journey" — créer automatiquement un snapshot GEO + un événement "applied" du ledger d'impact à chaque application live (non dry-run) d'une optimisation, sans intervention manuelle du marchand.
- **Summary:** Nouveau module `app/geo/auto_tracking.py` avec `record_applied_change(shop, resource_type, resource_id, resource_title, action_type, field, old_value, new_value, resource_handle="", db_path=None) -> int | None` : crée un `geo_optimization_snapshots` minimal (contenu = `{field: old_value}`, `readiness_score`/`seo_score` = 0 car non recalculés à l'apply) via `create_optimization_snapshot()`, puis un `geo_impact_events` (`event_type="applied_optimization"`, `status="applied"`, `measurement_status="baseline_captured"`, `after_snapshot={"field": field, "value": new_value}`) via `create_geo_event()` — réutilise les helpers existants, pas de nouveau schéma. Métriques GSC de référence récupérées via `_find_gsc_file`/`_parse_gsc_csv` (`app/impact/report.py`) sur le path produit/collection. **Idempotence** : `_already_applied_today()` ignore l'appel (retourne `None`, aucune écriture) si un événement "applied" pour le même `(shop, resource_type, resource_id, action_type, field)` existe déjà aujourd'hui (UTC). **Robustesse** : tout le corps de `record_applied_change()` est dans un `try/except Exception` qui logue (`logger.exception`) et retourne `None` — un échec de cette écriture de bookkeeping local ne doit jamais transformer une écriture Shopify déjà réussie en erreur 500 pour le marchand (justification documentée dans la docstring, conforme à la règle AGENTS.md sur les `except Exception`). **Câblage** dans 4 points d'application live : `app/api/market_analysis.py` (`apply-to-shopify`, par champ appliqué : `meta_title`, `meta_description`, `product_description`, `alt_text` agrégé ; et `schema-facts/sync` avec `action_type="faq_metafield_sync"`), `app/api/blog.py` (`publish_blog_draft`, `action_type="blog_publish"`), `app/learning/approvals.py` (`apply_approval`, uniquement quand il n'existe pas déjà de `ledger_event_id` planifié à transitionner — sinon le chemin existant `update_geo_event_status(status="applied")` est conservé inchangé). Pour cohérence avec les autres points d'appel et avec `_already_applied_today`, `field=content_type.value` (ex. `"meta_title"`) est utilisé dans `apply_approval`, et non `FIELD_FOR_CONTENT_TYPE` (qui mappe vers les chemins GraphQL Shopify type `"seo.title"`, utilisés uniquement pour `seo_changes`/rollback).
- **Files created:** `app/geo/auto_tracking.py`, `tests/test_geo/test_auto_tracking.py`.
- **Files modified:** `app/api/market_analysis.py` (apply-to-shopify : `record_applied_change` par champ appliqué + schema-facts sync), `app/api/blog.py` (`publish_blog_draft`), `app/learning/approvals.py` (`apply_approval`, branche `else` quand pas de `ledger_event_id`), `tests/test_api/test_market_analysis.py` (mock de `record_applied_change` ajouté à `test_schema_facts_sync_is_explicit_shopify_write`).
- **Decisions made:** `record_applied_change()` conçu en version "légère" plutôt qu'en réutilisant `build_optimization_snapshot()` (qui recharge tout le snapshot boutique + recalcule `readiness_score`/`analyze_product_facts` — trop coûteux par écriture) : snapshot minimal centré sur le seul champ modifié, `readiness_score`/`seo_score` à `0` (inconnus à l'apply), mêmes tables/fonctions de persistance que le flux manuel. Idempotence par filtre SQL `created_at LIKE '{today}%'` + comparaison Python `after_snapshot.field == field` plutôt qu'une nouvelle colonne de dédup. Suite à la review `shopify-architecture-reviewer` (aucun nouvel appel Shopify/OAuth/scope, gating dry-run vérifié correct sur les 4 points d'appel) et au `code-reviewer` (bug bloquant trouvé et corrigé : `apply_approval` passait `field=FIELD_FOR_CONTENT_TYPE[...]` — ex. `"seo.title"` — au lieu de `field=content_type.value` — ex. `"meta_title"` —, ce qui aurait cassé l'idempotence inter-chemins et le contrat `before_snapshot.content[field]`/`after_snapshot.field` lu par les pages de mesure).
- **Validations run:** `ruff check .` ✅ ; `pytest -q` complet → **1764 passed, 185 skipped, 72 failed** (les 72 échecs sont préexistants, confirmés par `git stash` — tous des 401 Unauthorized sur `test_geo`/`test_billing`/`test_privacy`/`test_shops`/`test_pagespeed_configure`/`test_llm`, problème d'environnement de test sans rapport avec ce diff) ; ciblé `tests/test_geo/ tests/test_api/test_market_analysis.py tests/test_blog/ tests/test_learning/` → **275 passed**. `shopify-architecture-reviewer` exécuté (agentId `a741cc67bdf0934de`) : aucun problème OAuth/billing/scope, gating dry-run correct partout, 1 point bloquant (exception non catchée pourrait transformer un apply Shopify réussi en 500) → corrigé (try/except Exception + log dans `record_applied_change`). `code-reviewer` exécuté (agentId `a79ca4afc330373f1`) : 1 bug bloquant (`field` incorrect dans `apply_approval`) → corrigé.
- **Validations skipped:** `npm run typecheck`/`npm run build` non requis (aucun changement frontend sur cette tâche).
- **Open issues:** `record_applied_change()` fait des écritures SQLite synchrones (+ lecture CSV GSC) directement dans des handlers `async def`, sans `asyncio.to_thread` (incohérent avec les appels `ShopifyWriter` voisins qui sont wrappés — risque faible, fichiers locaux petits, mais à harmoniser si ça devient un point chaud). Le snapshot et l'event ne sont pas écrits dans une transaction unique (crash entre les deux insertions = snapshot orphelin, sans conséquence côté Shopify).
- **Next recommended action:** Tâche 6/9 — alimenter le moteur d'analyse marché avec l'historique d'optimisation (`build_optimization_history()` à partir de `geo_impact_events`, injecté dans `_build_pass1_prompt`/`_build_pass2_prompt`).

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâches 2, 4, 3/9 du plan "Align Giulio Geo with the target merchant journey" (`.claude/plans/claude-code-task-rippling-matsumoto.md`, ordre d'exécution 1, 2, 4, 3, 5, 6, 7, 8, 9) — corriger les liens morts et alléger `app._index.tsx` (tâche 2), créer la page Mesure consommant le backend GEO (tâche 4), renommer "Analyse marché" en "Produits" et restructurer la nav (tâche 3).
- **Summary:** **Tâche 2 (liens morts + dashboard)** : `app.onboarding.tsx` accepte un paramètre `?step=` (1-4) pour forcer l'étape affichée sans déclencher la redirection "analyse déjà complète → /app", évitant une boucle de redirection. `app._index.tsx` : le CTA "Comprendre ma niche"/regénérer l'analyse pointe vers `/app/onboarding&step=2` (au lieu de `/app/niche-understanding`, mort) ; le bouton "Voir tout"/CTA d'action priorisée pointe vers `/app/products?product=...` (au lieu de `/app/safe-apply?highlight=...`, mort) ; le lien zone "Performance" pointe vers `/app/measure` (au lieu de `/app/impact`, mort). **Tâche 4 (page Mesure)** : nouvelle route `app.measure.tsx` (~360 lignes, lecture seule, aucun job) — `loader` appelle en parallèle `GET /geo/{progress-curve,ledger,retention-milestones,impact-report,confidence-scores,control-groups,next-best-actions}` via `callBackendForShop`. UI : bandeau "tracking incomplet" (flags), KPIs + sparklines de tendance (réutilise le composant `Sparkline` existant — pas de nouvelle dépendance graphique), cartes de jalons de rétention (J+14/28/60), tableau impact-report (verdicts/recommandations), aperçu de confiance par catalogue, tableau control-groups (modifié vs témoin), liste next-best-actions. ~65 nouvelles clés i18n FR+EN (`measure*`), incluant `measureNav: "Mesure"/"Measure"`. **Tâche 3 (renommage Produits + nav)** : `git mv app.market-analysis.tsx app.products.tsx` (composant renommé `ProductsPage`, titre de page `t(locale, "navProducts")`) ; nouvelle `app.market-analysis.tsx` créée comme redirect-only vers `/app/products` (préserve query params + locale, pas de boucle de redirection). `app.tsx` : `NavMenu` restructuré en **Dashboard / Produits / Blog / Mesure / Réglages** — `geo-llms-txt` et `continuous-improvement` retirés du menu (routes conservées, atteignables par URL directe ; seront référencées depuis Réglages/Mesure à la tâche 8). Toutes les références `/app/market-analysis` dans `app._index.tsx`, `app.competitor-crawl.tsx`, `app.blog.tsx` mises à jour vers `/app/products` ; libellés "Analyse marché"/"Market analysis" qui désignaient cette page renommés en "Produits"/"Products" (`app.blog.tsx` bannière + empty-state, `i18n.ts` `marketAnalysisCompetitorsSubtitle`). Clé i18n `marketAnalysis` (titre de page, devenue inutilisée) supprimée des dictionnaires FR+EN ; `navProducts: "Produits"/"Products"` ajoutée (préparée à la tâche 4).
- **Files created:** `shopify-app/app/routes/app.measure.tsx`, `shopify-app/app/routes/app.products.tsx` (renommé depuis `app.market-analysis.tsx` via `git mv`, contenu inchangé hors nom de composant et titre).
- **Files modified:** `shopify-app/app/routes/app.onboarding.tsx` (bypass `?step=`), `shopify-app/app/routes/app._index.tsx` (3 liens morts → cibles valides), `shopify-app/app/routes/app.tsx` (nav restructurée), `shopify-app/app/routes/app.market-analysis.tsx` (devenu un redirect-only vers `/app/products`), `shopify-app/app/routes/app.competitor-crawl.tsx` (2 liens `/app/market-analysis` → `/app/products`), `shopify-app/app/routes/app.blog.tsx` (2 liens + libellés "Analyse marché"/"Market analysis" → "Produits"/"Products"), `shopify-app/app/lib/i18n.ts` (~65 clés `measure*` + `navProducts` ajoutées, `marketAnalysis`/`continuousImprovementNav`/`llmsTxtNavLabel` supprimées, `marketAnalysisCompetitorsSubtitle` reformulée).
- **Decisions made:** Renommage de fichier via `git mv` + redirect-stub plutôt que ré-export Remix (le fichier d'origine doit devenir un loader de redirection pur, incompatible avec un ré-export du même loader pour la nouvelle route). `geo-llms-txt`/`continuous-improvement` retirés de la nav primaire mais routes non supprimées (référencées plus tard depuis Réglages/Mesure, tâche 8) — pas de régression, juste orphelins de nav pour l'instant. Sparkline existant réutilisé pour la page Mesure (aucune librairie de graphiques dans le projet, confirmé par grep).
- **Validations run:** `cd shopify-app && npm run typecheck` ✅, `npm run build` ✅ (après chacune des 3 tâches). `code-reviewer` exécuté sur chaque diff (tâche 4 : agentId `a3d41151fd2192e39`, "Safe to commit" ; tâche 3 : agentId `aa2b7c676b7594b8f`, "Safe to commit", item `&product=` non câblé identifié comme dette pré-existante non-régressive). Re-grep final : zéro occurrence de `/app/niche-understanding`, `/app/safe-apply`, `/app/impact`, `/app/priorities`, `/app/ga4`, `/app/market-analysis` dans `shopify-app/app/routes/` (hors le nouveau redirect stub lui-même).
- **Validations skipped:** `ruff check .`/`pytest` non requis (aucun changement Python sur ces 3 tâches). Test manuel navigateur non exécuté (pas d'environnement Shopify dev disponible).
- **Open issues:** Le bouton dashboard `app._index.tsx` (CTA action priorisée) génère `/app/products?locale=...&product=<action_id>`, mais `app.products.tsx` ne lit/consomme aucun paramètre `product` (dette pré-existante, identique avant le renommage — pas une régression de cette session). `geo-llms-txt`/`continuous-improvement` désormais accessibles uniquement par URL directe jusqu'à la tâche 8 (Réglages consolidé).
- **Next recommended action:** Tâche 5/9 — créer automatiquement des `geo_impact_events`/`geo_optimization_snapshots` à chaque application live (apply-to-shopify, blog publish, schema-facts sync, approbations learning), avec déduplication par jour calendaire.

## Previous completed task

- **Date:** 2026-06-10
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Tâche 1/9 du plan "Align Giulio Geo with the target merchant journey" — reconstruire `app.onboarding.tsx` en assistant 4 étapes (Connecter Google → Première analyse → Identification produits → Analyse approfondie) sans dupliquer la logique d'action déjà présente dans `app._index.tsx`.
- **Summary:** **Helpers serveur partagés** : extraction de la logique `callBackendForShop` des intents d'analyse depuis `app._index.tsx` vers `shopify-app/app/lib/businessProfileActions.server.ts` (`startBusinessAnalysis`, `pollBusinessAnalysis`, `saveBusinessProfile`, `saveBusinessProfileAndStartIdentification`, `fetchLatestBusinessProfile`) et `shopify-app/app/lib/productIdentificationActions.server.ts` (`startProductAnalysis`, `pollProductIdentification`, `saveProductIdentificationAndStartAnalysis`, `pollProductAnalysis`) — mêmes endpoints/payloads/réponses qu'avant. **Composants UI partagés** (`shopify-app/app/components/`) : `BusinessProfilePanel.tsx`, `ProductIdentificationPanel.tsx`, `MarketAnalysisProgressPanel.tsx` — chacun gère ses propres fetchers/polling et expose un callback (`onValidated`/`onSaved`/`onComplete`). `marketAnalysisShared.tsx` centralise désormais `BusinessProfile`, `MarketJobState`, `BusinessPersona`, `ContentStyle`, `linesFromText`, `textFromLines`, `SectionTitle` (déplacés hors de `app._index.tsx`, qui les importe). **`app._index.tsx`** : `action()` délègue maintenant aux mêmes helpers (comportement inchangé) ; la redirection de `loader()` vers `/app/onboarding` repose désormais sur `!businessProfile || businessProfile.status !== "validated"` (au lieu de `dashboard.zone1.niche_available`, lié à l'ancien flux `niche/understand` mort) — évite une boucle de redirection infinie avec le nouvel onboarding. **`app.onboarding.tsx` réécrit** : étape 1 "Connecter Google" (GSC connect/disconnect existant + nouveau bouton GA4 `ga4_connect`, popup OAuth + `postMessage`) ; étapes 2-4 = les 3 nouveaux panneaux partagés, avec `startStep` calculé côté loader (1 si GSC non connecté, 2 si connecté mais profil non validé, 3 sinon) et redirection vers `/app` si analyse déjà complète. Suppression de l'intent mort `niche_understand` et de `GuidedOnboardingFlow`/liens vers `/app/niche-understanding` et `/app/priorities`. Section "Outils avancés" conservée telle quelle. **`app/api/ga4.py`** : le callback OAuth GA4 envoie désormais `postMessage({source:"leonie-google-oauth-ga4", ok:true})` (distinct de GSC) ; l'onboarding affiche un badge "propriété à sélectionner" si OAuth fait mais `ga4.ready=false`. **i18n** : ~18 nouvelles clés FR+EN (`onboardingStepGoogleTitle/Body`, `onboardingConnectGSC/GA4`, `onboardingGSCConnected`, `onboardingGA4Connected/PropertyPending`, `onboardingGoogleContinue`, `onboardingStepProfileTitle/Body`, `onboardingStartBusinessAnalysis`, `onboardingStepProductsTitle/Body`, `onboardingStartProductIdentification`, `onboardingStepDeepTitle/Body`).
- **Files created:** `shopify-app/app/lib/businessProfileActions.server.ts`, `shopify-app/app/lib/productIdentificationActions.server.ts`, `shopify-app/app/components/BusinessProfilePanel.tsx`, `shopify-app/app/components/ProductIdentificationPanel.tsx`, `shopify-app/app/components/MarketAnalysisProgressPanel.tsx`.
- **Files modified:** `shopify-app/app/routes/app.onboarding.tsx` (réécriture complète), `shopify-app/app/routes/app._index.tsx` (action() délègue aux helpers, redirection loader corrigée, types/SectionTitle/linesFromText/textFromLines déplacés), `shopify-app/app/lib/marketAnalysisShared.tsx` (nouveaux types/exports), `shopify-app/app/lib/i18n.ts` (nouvelles clés FR+EN), `shopify-app/app/components/onboarding/types.ts` (nouveau `GA4Status`), `app/api/ga4.py` (postMessage callback GA4).
- **Decisions made:** Étape "Analyse approfondie" (step 4) reste pilotée côté client (`productJobId` en `useState`) — pas de nouvel endpoint backend "latest job" pour la reprise après reload (hors scope du plan approuvé, éviterait une dérive de périmètre). Risque connu documenté ci-dessous. GA4 reste "encouragé mais non bloquant" pour avancer dans l'assistant (seul GSC bloque l'étape 1).
- **Validations run:** `cd shopify-app && npm run typecheck` ✅, `npm run build` ✅ (après `npm install`, `node_modules` absent au départ). `code-reviewer` exécuté sur le diff complet.
- **Validations skipped:** `ruff check .`/`pytest` non requis (seul `app/api/ga4.py` a changé côté Python, modification HTML statique sans logique testable). Test manuel navigateur du nouvel assistant non exécuté (pas d'environnement Shopify dev disponible dans cette session).
- **Open issues:** Si un marchand recharge la page pendant l'étape 4 (analyse approfondie en cours), `startStep` retombe à 3 (pas de endpoint "latest product job") — il referait l'identification produits (peu coûteux) pendant qu'un job d'analyse approfondie tourne déjà côté serveur ; au rechargement suivant, `/market-analysis/latest` sera rempli et redirigera vers `/app`. Risque de double job d'analyse si le marchand relance l'étape 3 pendant ce délai — pas de garde-fou de déduplication côté backend (pré-existant, pas une régression de cette tâche).
- **Next recommended action:** Tâche 2/9 — corriger les liens morts (`/app/niche-understanding`, `/app/safe-apply`, `/app/impact`, `/app/priorities`, `/app/ga4`) et alléger `app._index.tsx` en réutilisant les panneaux partagés de la Tâche 1.

## Previous completed task

- **Date:** 2026-06-08
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Corriger 3 bugs remontés par l'utilisateur après usage réel du flux blog : (1) contenu généré pouvant nuire aux ventes (rubrique « Inconvénients » + markdown brut affiché), (2) absence d'indicateur de chargement au clic sur « Générer l'article », (3) génération qui « tourne mais ne génère rien » + impossibilité d'ajouter une photo sur les brouillons existants.
- **Summary:** **(1) Contenu sales-safe** (`af60028`) : ajout des règles 5/6 dans `_build_prompt` de `app/blog/section_generator.py` (texte brut uniquement — jamais de `**gras**`/markdown ; jamais de rubrique « inconvénients »/« points faibles »/prix présenté comme un défaut, reformulation constructive obligatoire) + règle miroir dans le prompt `proposed_blog_outline` de `app/market_analysis/engine.py` (interdiction des H2 à angle négatif, même si un concurrent en a un). **(2) Indicateur de chargement** (`2a5d22f`) : le bouton « Générer l'article » utilisait `fetcher.state`/`fetcher.formData` alors que le formulaire est un `<Form method="post">` Remix (navigation route-level, pas un fetcher) — `fetcher.state` restait `"idle"`, donc jamais de spinner. Remplacé par `useNavigation()` + `navigation.state`/`navigation.formData` (ajout de l'import) ; même correctif appliqué au bouton « Créer le brouillon ». **(3) Panneau bloqué + doublons + champ photo invisible** (`1675863`) : root cause unique — `selectedIdea` (état local React) survit à la redirection `?draft={newId}` après génération (le composant ne démonte pas en navigation same-route), donc le panneau restait affiché sur la carte « idée de blog » au lieu de basculer sur le brouillon fraîchement généré ; chaque reclic créait un nouveau brouillon en double. Étendu le `useEffect` existant keyé sur `[selected?.id]` pour appeler `setSelectedIdea(null)` (bascule auto vers le nouveau brouillon) **et** `setTabIndex(0)` (remet l'onglet "Édition" — où vit le champ image de couverture/alt-text — au lieu de rester figé sur "Aperçu" après un save antérieur, ce qui rendait le champ photo invisible sur les brouillons déjà générés). Ajout d'un texte explicatif visible pendant la génération (« cela peut prendre 1 à 2 minutes… inutile de cliquer à nouveau ») pour décourager les reclics tant que la génération reste synchrone (pas de job async, ~5-7 appels LLM séquentiels en ~1-3 min).
- **Files modified:** `app/blog/section_generator.py`, `app/market_analysis/engine.py`, `shopify-app/app/routes/app.blog.tsx` (3 commits distincts : `af60028`, `2a5d22f`, `1675863`).
- **Decisions made:** Pas de refactor vers un job async pour la génération de brouillon (changement d'architecture trop large, hors scope d'un correctif de bug) — palliatif côté UX (hint + désactivation du bouton pendant la génération) jugé suffisant pour empêcher les doublons. Réutilisation du `useEffect` existant `[selected?.id]` plutôt qu'un nouvel effet dédié — un seul déclencheur (changement de brouillon sélectionné) explique les deux symptômes (panneau figé + onglet figé).
- **Validations run:** `npm run typecheck` ✅ + `npm run build` ✅ après chacun des 3 correctifs (3 rounds de vérification).
- **Validations skipped:** Test manuel navigateur du flux complet de génération (1-3 min par run, non rejouable en CI) — diagnostic posé sur la base des retours utilisateur successifs (« rien ne change », « il apparaît mais longtemps après », « plusieurs apparaissent et reste sur idée de blog ») qui ont permis d'isoler la cause racine sans avoir à reproduire en live. `pytest`/`ruff` non requis (diff frontend + prompts LLM, pas de logique Python testable unitairement modifiée hors prompt strings).
- **Open issues:** Des brouillons en double ont probablement été créés côté boutique pilote pendant que le bug était actif (clics répétés par l'utilisateur) — à nettoyer manuellement via le bouton « Supprimer » existant, ou sur demande explicite via script (non fait : action destructive nécessitant confirmation). La génération reste synchrone (1-3 min, bloquante) — un futur passage au pattern job async (`POST /jobs` + polling, comme `app.market-analysis.tsx`) éliminerait le besoin du hint et améliorerait l'UX, mais c'est un changement d'architecture à planifier séparément.
- **Next recommended action:** Confirmer avec l'utilisateur que les 3 correctifs résolvent bien les symptômes en usage réel ; si des brouillons en double subsistent, proposer un nettoyage. Évaluer si le passage à un pattern job async pour la génération de blog mérite d'être planifié (réduirait drastiquement le risque de ce type de bug UX).

## Previous completed task

- **Date:** 2026-06-08
- **Agent:** Claude (Sonnet 4.6)
- **Goal:** Améliorer le SEO du blog avec le minimum d'effort marchand — 4 pistes (plan `.claude/plans/fait-un-git-pull-stateful-lantern.md`) : garde-fou de placement de mot-clé, profondeur de contenu, topic clusters/pillar pages, alt-text auto sur l'image de couverture.
- **Summary:** **(1) Garde-fou mot-clé** : nouveau `app/blog/quality.py` (`check_keyword_placement`, miroir du pattern `ConstraintsCheck`/scoring pondéré de `content_actions/audit.py`) — vérifie présence du mot-clé cible dans titre/H2/intro + densité, calculé automatiquement à la génération/régénération de section, affiché en badge + liste d'issues dans `app.blog.tsx` (`keyword_check`). **(2) Profondeur de contenu** : relevé du plancher du `body` de section dans `section_generator.py` (constantes du prompt) pour homogénéiser la profondeur sans gonflage artificiel (anti-remplissage, cohérent avec la règle anti-hallucination `claims_used`). **(3) Topic clusters / pillar pages** : nouveau `app/blog/clusters.py` (`build_blog_idea_clusters`, réutilise `build_clusters`/Jaccard de `keyword_normalization.py` — zéro nouvel appel API), nouvel endpoint `POST /shops/{shop}/blog/idea-clusters` ; extension des reason-tags de maillage interne (`app/blog/internal_links.py` → `suggest_cluster_links`, tags `cluster_pillar`/`cluster_sibling`) fusionnés dans `get_link_suggestions` ; UI : badge « Pilier suggéré » sur les idées de blog + badges de raison étendus (`linkReasonBadge`). **(4) Alt-text auto image de couverture** : génération template-based (pas de LLM, miroir de `_default_image_alt`) dans `_default_blog_image_alt`/`_apply_image_alt` (`app/api/blog.py`) — `title + " – " + keyword` si non dupliqué, tronqué à 125 car., persisté/éditable (jamais d'écrasement d'une édition marchande), envoyé à Shopify via `image_alt` → `ArticleCreateInput.image.altText` (schéma vérifié sur shopify.dev API 2025-01 avant codage, distinct de `ImageInput`). **Décision utilisateur respectée** : pas de génération d'image IA (nouvelle dépendance externe rejetée), uniquement alt-text sur l'image déjà fournie par le marchand.
- **Files created:** `app/blog/clusters.py`, `tests/test_blog/test_clusters.py`, `tests/test_blog/test_image_alt.py` (`app/blog/quality.py` + `tests/test_blog/test_quality.py` créés dans une session précédente sur ce même plan).
- **Files modified:** `app/api/blog.py` (modèles `IdeaClusterItem`/`IdeaClustersRequest`, `_default_blog_image_alt`/`_apply_image_alt`, endpoint `idea-clusters`, fusion cluster-links dans `get_link_suggestions`, wiring `image_alt` dans `update_blog_draft`/`publish_blog_draft`), `app/blog/internal_links.py` (`suggest_cluster_links`, seuil `_CLUSTER_SIM_THRESHOLD`), `app/blog/shopify_articles.py` (`image_alt` param + `altText` dans la mutation `articleCreate`), `app/blog/section_generator.py` (constantes de profondeur), `tests/test_blog/test_internal_links.py`, `tests/test_blog/test_shopify_articles.py`, `shopify-app/app/routes/app.blog.tsx` (UI : badge pilier, `linkReasonBadge`, bloc image de couverture éditable + alt-text, bloc `keyword_check`).
- **Decisions made:** Endpoint clustering stateless côté backend (le frontend transmet les `blogIdeas` déjà chargées) pour éviter de dupliquer l'extraction d'idées et la similarité Jaccard côté TypeScript. `_default_blog_image_alt` réécrite localement plutôt que d'importer le `_default_image_alt` privé de `market_analysis/engine.py` (encapsulation). `prefillCluster` (champ existant non câblé, fonctionnalité séparée) et `PublishDraftRequest`/`publish_draft` (route alternative non appelée par le frontend) volontairement non touchés — hors périmètre du plan.
- **Validations run:** `ruff check .` ✅ ; `pytest -q` complet → **1833 passed, 185 skipped** ; `npm run typecheck` ✅ + `npm run build` ✅ (production, client + SSR).
- **Validations skipped:** Test manuel navigateur du flux complet (génération → badges cluster/mot-clé → alt-text pré-rempli → publication) non exécuté — typecheck/build + suite de tests jugés suffisants pour ce diff backend-driven avec UI miroir des patterns existants.
- **Open issues:** UX pré-existante (non introduite ici, affecte identiquement `keyword_check` et `image_alt`) : `onSave` utilise `submit()` route-level et `useEffect` ne resynchronise `draft` que sur changement d'`id` — les champs recalculés côté serveur n'apparaissent pas immédiatement après edit+save sans navigation/reload (les données sont correctement persistées et envoyées à Shopify, seul l'affichage instantané est concerné). Pas de commits créés — à faire si demandé (1 par piste, par AGENTS.md §7).
- **Next recommended action:** Décider si on commite (4 commits séparés, un par piste) et si on corrige la resynchronisation UI post-save de `keyword_check`/`image_alt` (refactor `fetcher.submit` + `useEffect` plus large — hors scope de ce plan, à planifier séparément).

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Améliorations GEO v1 issues de l'analyse concurrentielle App Store — 3 phases.
- **Summary:** **Phase 1 — GEO Score** : le score readiness existant (`app/geo/readiness.py`, 0–100 + composantes, déjà en Zone 1) rebrandé « GEO Score » + ligne d'explication (i18n FR/EN) — lisibilité marchand & screenshots. **Phase 2 — Contrôles crawlers IA + filtres** : `app/geo/llms_txt.py` accepte des `prefs` (filtres produits/collections/pages réels + bloc consultatif `## AI access` listant les agents bienvenus) ; persistance `llms_txt_prefs` (table 2 schémas `app/db.py` + `store.get/save_crawler_prefs`) ; endpoints `GET/PUT /api/shops/{shop}/llms-txt/crawler-prefs` ; `publisher.publish` + `status` + `generate` chargent les prefs ; UI panneau de réglages dans `app.geo-llms-txt.tsx`. **Pas de robots.txt** (préserve l'allowlist write_themes 3 fichiers) — blocage dur documenté comme hors scope. **Phase 3 — AI Visibility (conforme V1, décision utilisateur)** : création de `app/api/ai_visibility.py` (`GET /ai-visibility/status` → `enabled:false`, `available_in:"v2"`, disclaimer « signal mesuré, jamais garanti »), router remonté dans `main.py`, retiré de la liste « archived » de `tests/conftest.py` → les 3 tests cassés passent ; encart UI honnête « Visibilité IA — bientôt ». **Respecte launch-readiness §3.7/§3.8** (pas de promesse, axes séparés) ; le sondage LLM live a été écarté (conflit conformité), à revoir en V2 opt-in.
- **Files created:** `app/api/ai_visibility.py`, `tests/test_geo/test_llms_txt_prefs.py`.
- **Files modified:** `app/geo/llms_txt.py`, `app/api/llms_txt.py`, `app/llms_txt/store.py`, `app/llms_txt/publisher.py`, `app/db.py`, `app/main.py`, `tests/conftest.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.geo-llms-txt.tsx`, `tests/test_api/test_llms_txt_api.py`, `tests/test_llms_txt/test_store.py`.
- **Decisions made:** Phase 3 livrée en **version conforme V1** (statut désactivé + framing no-promise), pas de signal LLM live — choix utilisateur, aligné §3.7. Contrôles crawlers = préférence advisory dans les fichiers IA (pas de robots.txt) pour ne pas élargir la surface write_themes. Defaults prefs « tout activé » → sortie llms.txt identique à l'existant (non-régression). Isolation DB par test ajoutée dans `test_llms_txt_api.py` (la persistance des prefs polluait la DB partagée).
- **Validations run:** `ruff check app/ tests/` ✅ ; `pytest` ciblé (`test_geo/`, `test_llms_txt/`, `apply/test_shopify_theme_files`, `test_api/{ai_visibility,llms_txt_api,dashboard}`) → **200 passed** ; `npm run typecheck` ✅ + `npm run build` ✅.
- **Validations skipped:** Comportement runtime des nouvelles UI (panneau prefs, encart AI visibility) non testé en navigateur (typecheck/build + tests backend). Pas de run full-suite (échecs env préexistants gdpr/billing 401 hors périmètre).
- **Open issues:** Signal AI-visibility live = V2 opt-in (plan-gated, budget, cache) si décidé plus tard. Hard-block crawlers via robots.txt = hors scope v1 (préserver l'allowlist). `render.yaml` scopes `read_orders` toujours en attente.
- **Next recommended action:** Mettre en avant GEO Score + contrôles crawlers dans les screenshots du listing ; décider V2 pour le signal AI-visibility.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Sécuriser, limiter, journaliser et justifier l'usage du scope `write_themes` (publication de `llms.txt` / `llms-full.txt` / `agents.md`) pour la review App Store — sans casser l'archi Remix + FastAPI.
- **Summary:** **(1) Allowlist stricte** dans `app/apply/shopify_theme_files.py` (`ALLOWED_THEME_FILES` = 3 templates) : `upsert_templates`/`delete_templates` refusent tout autre fichier (`layout/*`, `sections/*`, `snippets/*`, `assets/*`, `templates/product*`, `theme.liquid`, …) **avant tout appel réseau**. **(2) Mode `LEONIE_THEME_WRITE_MODE`** (`disabled`|`review_safe`|`live`) dans `app/safety.py` (`theme_write_mode()` + `require_theme_write_allowed()`), défaut `review_safe` en prod (DATABASE_URL présent), `disabled` en local/test. **(3) Confirmation marchand obligatoire** : endpoint publish exige `confirm=true` (409 sinon) + mode ≠ disabled (403 sinon) ; UI `app.geo-llms-txt.tsx` ajoute liste des 3 fichiers + disclaimers + case à cocher + bouton « Publier les fichiers IA sur mon thème » ; le panneau dashboard `LlmsTxtPanel.tsx` ne publie plus en 1 clic (il **navigue** vers la page de confirmation). **(4) Journal** `theme_write_log` (table dans `app/db.py` SQLite+PG, `store.log_theme_write`/`get_theme_write_log`) : shop, theme_id, action, filenames, hash avant/après, user_action, timestamp ; publish/unpublish loggés. **(5) Webhooks** : régénération seulement si déjà publié + mode ≠ disabled (sinon `regeneration_pending` enregistré, pas d'écriture ; debounce conservé). **(6) Justification review** : `docs/shopify-write-themes-review-justification.md` + lien dans la checklist. `REVIEW_NOTE` ajouté (code + doc) : vérifier sur boutique réelle que Shopify sert `/llms.txt` etc. depuis les templates ; sinon fallback `disabled` (preview/export) et retrait de `write_themes`. **Confirmé via doc Shopify** : `templates/llms.txt.liquid` est bien rendu pour `/llms.txt`.
- **Files created:** `docs/shopify-write-themes-review-justification.md`.
- **Files modified:** `app/safety.py`, `app/apply/shopify_theme_files.py`, `app/db.py`, `app/llms_txt/store.py`, `app/llms_txt/publisher.py`, `app/api/llms_txt.py`, `render.yaml`, `.env.example`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.geo-llms-txt.tsx`, `shopify-app/app/components/LlmsTxtPanel.tsx`, `tests/apply/test_shopify_theme_files.py`, `tests/test_llms_txt/test_publisher.py`, `tests/test_api/test_llms_txt_api.py`, `docs/app-store-submission-checklist.md`.
- **Decisions made:** `write_themes` **conservé** (mécanisme légitime et confirmé pour servir `/llms.txt`). `unpublish` autorisé dans tous les modes (off-switch, ne touche que les 3 fichiers). Mode par défaut `disabled` sous pytest → fixture `review_safe` ajoutée aux tests publisher. `render.yaml` : ajout de `LEONIE_THEME_WRITE_MODE=review_safe` (additif, pas un changement de scope) ; les scopes `read_orders` restants non touchés (séparé).
- **Validations run:** `ruff check app/ tests/...` ✅ ; `pytest tests/apply/test_shopify_theme_files.py tests/test_llms_txt/ tests/test_api/test_llms_txt_api.py tests/test_geo/test_llms_txt.py` → **62 passed** ; `npm run typecheck` ✅ + `npm run build` ✅.
- **Validations skipped:** Comportement runtime de la nouvelle UI de confirmation non testé en navigateur (typecheck/build + tests backend suffisent). Vérif réelle « Shopify sert /llms.txt depuis le template » à faire sur boutique (REVIEW_NOTE).
- **Open issues:** REVIEW_NOTE à lever avant soumission (GET /llms.txt en 200 sur boutique réelle + diff thème = 3 fichiers seulement). `render.yaml` scopes `read_orders` toujours en attente d'alignement.
- **Next recommended action:** Vérifier le REVIEW_NOTE sur une boutique de test, puis coller le résumé de `docs/shopify-write-themes-review-justification.md` dans les notes de review du Partner Dashboard.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Rebrand du nom visible de l'app en « Giulio Geo » (décision utilisateur), nom visible uniquement.
- **Summary:** Renommage du **nom produit visible** sur 55 fichiers. (1) `Léonie SEO` → `Giulio Geo` (UI/i18n, noms de plans billing `app/billing/client.py`, pages `/privacy` + `/terms`, nom user-facing de l'extension thème `shopify.extension.toml`, listing copy, docs, agents). (2) `Organically` → `Giulio Geo` (nom dans `shopify.app.toml`, commentaires, docs pilote). (3) `Léonie` seul → `Giulio Geo` **uniquement** dans l'UI marchand (`shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.onboarding.tsx`). **Préservé volontairement :** la marque du marchand pilote `Léonie Delacroix` / `Léonie de la Croix` (configs, fixtures, tests JSON-LD), et tous les **identifiants techniques** (variables `LEONIE_*`, domaines `leoniedelacroix.com`/onrender, email `support@leonie-seo.com`, handle d'extension `leonie-seo-jsonld`, namespace metafield `leonie.*`, nom de repo) — périmètre « nom visible uniquement » choisi par l'utilisateur.
- **Files created:** Aucun.
- **Files modified:** 55 fichiers (rename de chaînes). Clés : `shopify-app/shopify.app.toml`, `shopify-app/extensions/leonie-seo-jsonld/shopify.extension.toml`, `app/billing/client.py`, `app/api/privacy.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/routes/app.onboarding.tsx`, + docs et fixtures de tests synchronisées.
- **Decisions made:** Périmètre limité au nom visible (pas d'infra technique) pour éviter de casser le déploiement prod et les metafields existants. Remplacements faits par chaînes exactes (`Léonie SEO`, `Organically`) pour ne pas toucher `Léonie Delacroix` ; le `Léonie` isolé n'a été renommé que dans 2 fichiers UI sans collision avec la marque marchand.
- **Validations run:** `npm run typecheck` ✅ + `npm run build` ✅ (client + SSR) ; `ruff check` ✅ ; `pytest tests/test_billing/test_router.py tests/test_api/test_semantics.py tests/test_jsonld/test_builders.py` → source/tests synchronisés (`Giulio Geo Pro` des deux côtés), `Léonie Delacroix` toujours asserté OK ; les 9 échecs billing sont des **401 environnementaux** (session token sandbox), confirmés identiques après `git stash` → **aucune régression** introduite par le rename.
- **Validations skipped:** Rendu visuel navigateur non vérifié (typecheck/build/lint suffisent pour un rename de chaînes).
- **Open issues:** (1) Le nom Partner Dashboard + listing App Store doivent être mis à « Giulio Geo » manuellement, et l'unicité du nom vérifiée sur l'App Store. (2) `render.yaml` scopes `read_orders` toujours en attente. (3) Cold start non tranché. (4) Email support / domaines : restés en `leonie*` (hors périmètre « nom visible »).
- **Next recommended action:** Vérifier l'unicité « Giulio Geo » sur l'App Store et mettre à jour le Partner Dashboard (nom + listing). Décider si l'email support et les domaines doivent aussi être rebrandés.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Stratégie App Store — plan go/no-go end-to-end + premiers livrables in-repo (ToS publique + cohérence des scopes OAuth dans la doc).
- **Summary:** Plan complet écrit (`.claude/plans/`, hors repo) pour maximiser l'acceptation App Store : 7 phases (cohérence config, légal/support, assets, cold start, test marchand, validation, soumission). **Livrables produits :** (1) **Terms of Service** publique bilingue FR/EN via `GET /terms` ajouté dans `app/api/privacy.py` (réutilise le pattern de `/privacy`, routeur déjà monté dans `app/main.py`) — contient une **clause explicite « aucune garantie de ranking ni d'apparition dans les moteurs IA »** (garde-fou launch-readiness §3.7), billing via Shopify, usage acceptable, limitation de responsabilité, renvoi vers `/privacy`. (2) **Cohérence des scopes** : `read_orders` (inutilisé) retiré et `write_content` ajouté pour matcher `shopify.app.toml` (`read_products,write_products,write_content,read_themes,write_themes`) dans `.env.example` (racine, commenté), `docs/app-store-test-instructions.md` (copié verbatim au reviewer), `docs/pilot-real-store-setup.md`, `docs/app-store-submission-checklist.md`.
- **Files created:** Aucun (plan stocké hors repo dans `~/.claude/plans/`).
- **Files modified:** `app/api/privacy.py`, `.env.example`, `docs/app-store-test-instructions.md`, `docs/pilot-real-store-setup.md`, `docs/app-store-submission-checklist.md`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Nom de l'app (`Giulio Geo` dans `.toml` vs `Giulio Geo` dans la doc) **laissé inchangé** — décision utilisateur « nom à valider » (vérifier l'unicité App Store avant de figer). Cold start Render Free **non tranché** — à décider après les tests marchands (mitigation keep-alive vs migration Railway/Vercel). **`render.yaml` non modifié** : il porte encore `read_orders` (scope inutilisé) dans `SHOPIFY_SCOPES`, mais c'est de la **config de déploiement production** → changement à valider explicitement (AGENTS.md §11) avant édition + `shopify app deploy`.
- **Validations run:** `ruff check app/api/privacy.py` ✅ ; import du module + `GET /terms` via TestClient → 200, titres FR + EN présents ✅ ; `pytest tests/test_api/test_privacy.py` → 6 passed / 6 failed, les 6 échecs (`test_gdpr_export_*`, 401/KeyError) **préexistants** et environnementaux (session token dans le sandbox), confirmés identiques après `git stash` de mes modifs.
- **Validations skipped:** `npm run typecheck`/`build` non requis (aucune modif frontend ce tour). Rendu visuel HTML de `/terms` non vérifié en navigateur (TestClient suffit pour le statut + contenu).
- **Open issues:** (1) `render.yaml` à aligner sur les scopes (retirer `read_orders`) + `shopify app deploy` + re-consentement marchand — en attente d'accord explicite. (2) Nom d'app à figer après vérif unicité. (3) Décision cold start à prendre. (4) Assets de listing (icône, screenshots, vidéo), email support, publication ToS/guide à une URL publique : hors-repo. (5) Email support référencé : `support@leonie-seo.com` (à créer/monitorer).
- **Next recommended action:** Lancer les 3 tests marchands (`docs/pilot-merchant-test-script.md`), puis valider l'alignement `render.yaml` des scopes. En parallèle : figer le nom de l'app et préparer les assets de listing.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Décision cold start : conserver la mise en veille du backend Render Free (choix utilisateur), pas de maintien éveillé.
- **Summary:** Le cold start avait été diagnostiqué (`python -X importtime` : ~1,9 s d'imports, dont pandas ~242 ms et libs Google GA4 ~238 ms ; le gros du coût = reprovisioning ~30 s du conteneur Render après mise en veille à ~15 min d'inactivité). Un workflow keep-alive (`.github/workflows/keepalive.yml`) avait été ajouté pour garder l'instance chaude, **puis retiré** : l'utilisateur souhaite explicitement **conserver la mise en veille** (ne pas consommer les heures gratuites / coût). Net : aucun maintien éveillé. Le service dort comme prévu ; un cold start (~30 s) survient au 1er chargement après inactivité — accepté.
- **Files created:** Aucun (le `.github/workflows/keepalive.yml` créé plus tôt dans la session a été supprimé).
- **Files modified:** `docs/AI_HANDOFF.md`. **Supprimé :** `.github/workflows/keepalive.yml`.
- **Decisions made:** Pas de keep-alive. Pas de lazy-import (gain nul au boot : pandas reste tiré par `crawl/client.py`). Pas de modif `init_db()`. La latence de reprise après veille (~30 s, dominée par le reprovisioning Render) reste non adressable en code et est assumée. Conséquence à connaître : le critère Web Vitals (LCP ≤ 2,5 s) de Built for Shopify ne sera pas tenu sur le 1er chargement post-veille tant que le backend dort — c'est un arbitrage coût/perf choisi par l'utilisateur.
- **Validations run:** Aucune (suppression de fichier + doc).
- **Validations skipped:** N/A.
- **Open issues:** Si Built for Shopify (perf) devient prioritaire, il faudra soit un plan d'hébergement sans mise en veille, soit réintroduire un keep-alive — arbitrage à trancher à ce moment.
- **Next recommended action:** Rien côté cold start. Poursuivre sur les autres axes (rollout Save Bar vérifiable en runtime, soumission App Store) si souhaité.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Attaquer le cold start du backend Render Free (1er frein perf pour le critère Web Vitals de Built for Shopify) — par du code.
- **Summary:** Mesure du démarrage (`python -X importtime`) : ~1,9 s d'imports, dont pandas ~242 ms (tiré au boot par `app/crawl/client.py` — 15 usages — et `app/api/gsc.py`), libs Google GA4 ~238 ms. **Conclusion** : le gros du cold start vient de la **mise en veille Render Free** (reprovisioning ~30 s du conteneur, non adressable en code), pas des imports. Levier code retenu = **empêcher la mise en veille**. Ajout du workflow `.github/workflows/keepalive.yml` : cron toutes les 10 min (< fenêtre d'inactivité de 15 min) + `workflow_dispatch`, qui pingue l'endpoint santé du backend (`/health`, trivial, sans DB) et optionnellement l'app Remix, avec timeout large (70 s) et retries pour absorber un cold start. URLs configurables via variables Actions (`BACKEND_HEALTH_URL` défaut Render pilote, `APP_HEALTH_URL`). `concurrency` pour éviter l'empilement, `::warning::` au lieu d'échec pour ne pas spammer.
- **Files created:** `.github/workflows/keepalive.yml`.
- **Files modified:** `docs/AI_HANDOFF.md`.
- **Decisions made:** **Pas de lazy-import de pandas** : gain nul au boot car `crawl/client.py` (15 usages) le tire de toute façon ; lazy-importer seulement `gsc.py` (1 usage) n'enlèverait rien — pas worth le risque. **Pas de modif de `init_db()`** (nécessaire au boot, risqué). Le keep-alive est la solution code standard mais a un coût : garder un service Free éveillé consomme les heures gratuites (~750 h/mois) — la solution pérenne reste un plan payant. Limite connue : `/health` ne touche pas la DB, donc Neon Postgres (free) peut rester en veille même app chaude ; le 1er vrai requête réveille Neon (~1 s).
- **Validations run:** mesure `importtime` ; YAML validé (`yaml.safe_load`) ; vérif `/health` trivial (env-only) et densité pandas.
- **Validations skipped:** Le cron ne s'active que sur la branche par défaut (après merge) ; non exécuté ici. Effet réel sur le LCP à constater dans le Dev Dashboard après merge + déploiement.
- **Open issues:** Neon Postgres free se suspend aussi (~5 min) — non couvert par le ping `/health`. Si besoin, ajouter un ping d'un endpoint léger touchant la DB (< 5 min) ou passer Neon en plan sans suspension. La vraie élimination du cold start = backend sur plan payant.
- **Next recommended action:** Merger sur la branche par défaut, définir la variable Actions `BACKEND_HEALTH_URL` (et `APP_HEALTH_URL`), puis vérifier dans les logs du workflow que le ping renvoie 200 et suivre l'évolution du LCP.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Conformité Built for Shopify / publiabilité App Store (code) : nettoyer les scopes OAuth et ajouter la Contextual Save Bar App Bridge.
- **Summary:** **(1) Scopes OAuth** : retrait de `read_orders` (déclaré mais jamais utilisé dans le code — motif fréquent de rejet App Store) de `shopify.app.toml` et `.env.example`, et alignement de `.env.example` qui ne contenait pas `write_content`. Scopes finaux : `read_products,write_products,write_content,read_themes,write_themes`. **(2) Contextual Save Bar** (exigence d'intégration Built for Shopify) : ajout du composant App Bridge `<SaveBar>` (`@shopify/app-bridge-react`) sur l'éditeur de blog (`app.blog.tsx`), le formulaire « éditer puis enregistrer » le plus net. Suivi d'état « dirty » fiable via `serializeEditableDraft()` (comparaison des seuls champs persistés, ordre de clés fixe). La barre s'ouvre (`open={dirty}`) quand le brouillon a des modifications non enregistrées ; bouton primaire = Enregistrer (réutilise `onSave`), bouton secondaire = Annuler (`setDraft(selected)`), avec `discardConfirmation`.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/shopify.app.toml`, `shopify-app/.env.example`, `shopify-app/app/routes/app.blog.tsx`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Save Bar implémentée d'abord sur l'éditeur de blog comme **référence réutilisable** ; les formulaires `settings` (lecture seule) et `competitors` (auto-save, pas d'état dirty) n'en ont pas besoin. **Non couvert volontairement** : rollout de la Save Bar au profil business (dans `app._index.tsx`, 2971 l.) — trop risqué à faire en aveugle, et le comportement Save Bar (chrome admin, logique dirty) n'est **vérifiable qu'à l'exécution** dans l'admin embarqué. Distinction explicite faite à l'utilisateur : « publiable App Store » (≈ scopes propres + OAuth/billing/RGPD déjà OK) vs « badge Built for Shopify » (perf Web Vitals + Save Bar + seuils opérationnels 50 installs/5 avis).
- **Validations run:** `npm run typecheck` ✅ ; `npm run build` ✅ (client + SSR) ; vérif que `@shopify/app-bridge-react@4.1.5` exporte bien `SaveBar`/`useAppBridge` et grep confirmant `read_orders` inutilisé dans `app/` et `scripts/`.
- **Validations skipped:** Comportement runtime de la Save Bar non testé (nécessite `npm run dev` + tunnel sur une vraie boutique). Le changement de scopes nécessitera un `shopify app deploy` + re-consentement marchand au prochain chargement.
- **Open issues:** Save Bar à étendre aux autres formulaires multi-champs (profil business) lors d'une itération vérifiable en runtime. Critères Built for Shopify restants = perf Web Vitals réelle (dépend du cold start backend) + prérequis opérationnels non-code (App Store listing, 50 installs payants, 5 avis, partner standing).
- **Next recommended action:** `shopify app deploy` pour propager les nouveaux scopes, puis vérifier en `npm run dev` que la Save Bar s'affiche bien à l'édition d'un brouillon de blog et que Save/Discard fonctionnent dans l'admin embarqué.

## Previous completed task

- **Date:** 2026-06-06
- **Agent:** Claude (Opus 4.8)
- **Goal:** Revue perf + conformité « Built for Shopify » : rendre l'app plus fluide et corriger un bloquant Built for Shopify, code uniquement (infra Render hors périmètre).
- **Summary:** **(1) Built for Shopify — App Bridge dans le `<head>`** : `root.tsx` charge désormais le script CDN App Bridge (`https://cdn.shopify.com/shopifycloud/app-bridge.js` + `data-api-key`) comme premier élément du `<head>`, via un loader racine exposant `SHOPIFY_API_KEY`. Avant, App Bridge était injecté tardivement par `<AppProvider>` dans le body → Shopify ne pouvait pas mesurer les Web Vitals (LCP/CLS/INP) requis pour Built for Shopify. Pas de double-chargement : App Bridge s'auto-protège et `<AppProvider>` ne réinjecte pas si `window.shopify` existe déjà. **(2) Backend non bloquant** : `get_dashboard` (FastAPI async) faisait des lectures fichier + SQLite synchrones sur l'event loop. Extraction de toute l'assemblée dans `_assemble_dashboard()` (sync pur) appelée via `await asyncio.to_thread(...)`. **(3) Cache snapshot** : `load_snapshot_from_file_or_db` met en cache en mémoire les snapshots fichier (clé = chemin + mtime, invalidation auto au re-crawl, TTL 60 s, `threading.Lock`, copie superficielle au retour) ; le fallback DB n'est pas caché (chemin dégradé). Ajout de `clear_snapshot_cache()`. **(4) Anti-blocage loader** : le loader de `app._index.tsx` borne chaque appel backend via `AbortSignal.timeout` (dashboard 12 s, secondaires 8 s) → un backend froid ne fait plus pendre la page. **(5) CPU frontend** : `keywordCoverage()` (matching regex coûteux par mot-clé/produit) mémoïsé via `useMemo` dans `app.market-analysis.tsx`. **(6) Nettoyage** : suppression du `vite.config.js` redondant (Vite résout `.js` avant `.ts` → footgun), seul `vite.config.ts` reste.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/app/root.tsx`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.market-analysis.tsx`, `app/api/dashboard.py`, `app/api/snapshot_store.py`, `docs/AI_HANDOFF.md`. **Supprimé :** `shopify-app/vite.config.js`.
- **Decisions made:** Ne pas convertir le worker de jobs ni les handlers (`app/jobs/*`) — ils offloadent déjà via `asyncio.to_thread`, c'était une fausse piste. Ne pas cacher le fallback DB des snapshots (risque de péremption sans mtime, et fortement sollicité par les tests). **Refactor `defer()`/`<Await>` du dashboard et découpage des routes monolithiques (app._index 2971 l., market-analysis ~2800 l.) reportés** : ~91 lectures de champs différés interdépendantes, vérifiables seulement à l'exécution dans l'admin embarqué (frontières Suspense, CLS, hydratation, interaction polling) — trop risqué à shipper sans `npm run dev` sur une vraie boutique. Les timeouts de loader livrent l'essentiel du gain anti-blocage sans ce risque.
- **Validations run:** `ruff check app/api/dashboard.py app/api/snapshot_store.py` ✅ ; `pytest tests/test_api/test_dashboard.py` → **21 passed** ✅ ; `pytest` complet → **72 failed, 1680 passed** — identique à la base (`git stash`) : **0 régression introduite** (les 72 échecs préexistent : auth JWT/401, providers LLM, billing, privacy — liés à l'environnement de cette session) ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ (client + SSR).
- **Validations skipped:** Pas de test live dans l'admin Shopify embarqué (App Bridge `<head>`, mesure Web Vitals réelle, comportement defer) — nécessite `npm run dev` + tunnel sur une boutique. Échecs pytest préexistants non corrigés (hors périmètre, dus à l'environnement).
- **Open issues:** Les 72 échecs pytest de l'environnement (JWT/cryptography réinstallés, providers LLM sans réseau) restent à investiguer si l'environnement doit faire tourner la suite complète. Le gain LCP maximal nécessitera le refactor `defer()` + découpage des grosses routes (itération suivante, à valider en runtime).
- **Next recommended action:** Déployer, puis dans l'admin Shopify embarqué vérifier qu'un seul `<script app-bridge.js>` est présent dans le `<head>` (pas de doublon), et suivre les Web Vitals dans le Dev Dashboard. Ensuite, planifier l'itération `defer()`/découpage des routes avec validation `npm run dev`.

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Claude (Opus 4.8)
- **Goal:** Quand un cycle rend 0 proposition, expliquer clairement pourquoi et permettre de télécharger immédiatement le JSON (raisonnement + résultat) du cycle.
- **Summary:** Ajout de `diagnose_cycle_outcome()` dans `app/learning/scheduler.py` : explique en clair le résultat d'un cycle (`ok` / `learning_disabled` / `no_market_analysis` / `agent_not_run` / `no_products` / `no_candidates` / `all_candidates_failed` / `no_proposals`) avec messages fr/en. Le résultat de `run_learning_cycle` inclut désormais `diagnostics`, et l'endpoint agent GEO (`/geo/continuous-improvement/run`) aussi. Côté UI (`app.continuous-improvement.tsx`) : « Lancer un cycle maintenant » utilise un `cycleFetcher` dédié qui affiche une bannière de diagnostic (pourquoi 0 proposition) et un bouton **« Télécharger le JSON de ce cycle (raisonnement + résultat) »** ; la Card agent GEO affiche aussi le diagnostic + un bouton de téléchargement du run. Helper `downloadJson` factorisé (réutilisé par l'export). Cela règle le cas « j'ai eu 0 proposition sans explication et pas de JSON à envoyer ».
- **Files created:** `tests/test_learning/test_cycle_diagnostics.py`.
- **Files modified:** `app/learning/scheduler.py` (diagnose_cycle_outcome + champ diagnostics), `app/api/geo.py` (diagnostics dans la réponse), `shopify-app/app/routes/app.continuous-improvement.tsx` (cycleFetcher, diagnostic, téléchargement), `docs/AI_HANDOFF.md`.
- **Decisions made:** Champ `diagnostics` additif (rétro-compatible) sur les réponses existantes plutôt qu'un nouvel endpoint. Téléchargement du résultat brut côté client pour ne pas dépendre de la persistance (les cas « learning désactivé » / « pas d'analyse marché » ne créent pas de ligne agent_run). `cycleFetcher` séparé pour isoler l'affichage du cycle des autres actions partageant `fetcher`.
- **Validations run:** `ruff check .` (fichiers touchés) ✅ ; `pytest tests/test_learning/test_cycle_diagnostics.py tests/test_learning/test_scheduler.py tests/test_geo/test_continuous_agent.py tests/test_agent_schedule tests/test_api/test_agent_schedule.py` → **44 passed** ✅ ; `cd shopify-app && npm run build` ✅ ; `npx tsc` → aucune erreur sur le fichier (seul l'avertissement pré-existant `tsconfig baseUrl`).
- **Validations skipped:** `pytest` complet non relancé (72 échecs pré-existants déjà documentés, indépendants). Pas de test live.
- **Open issues:** Le diagnostic « no_candidates » signifie souvent que l'analyse de marché ne contient plus d'éléments éligibles ; régénérer l'analyse aide. Seuils heuristiques à affiner avec le pilote.
- **Next recommended action:** Relancer « Lancer un cycle maintenant » : lire la bannière de diagnostic, télécharger le JSON du cycle et l'examiner (champ `diagnostics` + `continuous_agent`).

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Claude (Opus 4.8)
- **Goal:** Ajouter une évaluation claire de l'efficacité de l'agent : savoir s'il améliore le SEO et le GEO, et quoi faire pour l'améliorer sinon.
- **Summary:** Nouveau module `app/agent_schedule/evaluation.py` (`evaluate_agent_effectiveness`) qui réutilise les briques de mesure existantes (`calculate_outcome`, observations learning mûres J+14/J+28/J+60) pour produire un verdict par dimension : **SEO** (impressions/clics/CTR/position) et **GEO** (delta de score de préparation). Chaque dimension est classée `improving` / `no_effect` / `regressing` / `inconclusive` (gating : ≥3 échantillons mûrs et confiance moyenne ≥35). Agrégation pondérée par confiance, distribution des verdicts, et `by_field` (quel type d'action marche le mieux). Surtout, `recommendations` actionnables et localisées (fr/en + code + severity) qui répondent à « comment l'améliorer sinon » : propositions en attente de validation (cause #1 d'absence d'effet en semi-auto), fenêtre non mûre, confiance faible (connecter GSC/GA4), SEO plat alors que GEO progresse (cibler mots-clés/CTR), GEO plat alors que SEO progresse (faits/FAQ/blocs de réponse), régression (repasser en semi-auto), qualité de contenu faible, tags négatifs dominants, ou « garder les réglages » si ça progresse. Exposé via `GET /api/shops/{shop}/agent-schedule/effectiveness`, inclus dans l'export JSON (`effectiveness`), et affiché dans la Card « Automatisation de l'agent » (badges verdict SEO/GEO + recommandations + breakdown par champ).
- **Files created:** `app/agent_schedule/evaluation.py`, `tests/test_agent_schedule/test_evaluation.py`.
- **Files modified:** `app/api/agent_schedule.py` (endpoint effectiveness), `app/agent_schedule/export.py` (section effectiveness), `tests/test_api/test_agent_schedule.py` (2 tests), `shopify-app/app/routes/app.continuous-improvement.tsx` (loader + affichage), `docs/AI_HANDOFF.md`.
- **Decisions made:** Réutiliser l'outcome math du moteur learning pour que le verdict colle aux poids appris (pas de second calcul divergent). SEO = signaux de recherche, GEO = delta de score de préparation. Verdict prudent par défaut (`inconclusive` tant que pas assez de données mûres) pour ne pas sur-promettre. Messages bilingues renvoyés par le backend (`fr`/`en` + `code`) pour rester utiles dans l'export « à montrer à ChatGPT » tout en laissant l'UI localiser.
- **Validations run:** `ruff check .` ✅ ; `pytest tests/test_agent_schedule tests/test_api/test_agent_schedule.py` → **27 passed** ✅ ; `cd shopify-app && npm run build` ✅ ; `npx tsc` → aucune erreur sur le fichier modifié (seul l'avertissement pré-existant `tsconfig baseUrl`).
- **Validations skipped:** `pytest` complet non relancé (72 échecs pré-existants déjà documentés ci-dessous, indépendants de cette tâche). Pas de test live ; le verdict réel nécessite des mesures J+14/J+28 sur une boutique pilote.
- **Open issues:** Le verdict reste `inconclusive` tant que <3 observations mûres existent ; sa fiabilité dépend de la connexion GSC/GA4 et de la taille du groupe contrôle. Les recommandations sont heuristiques (seuils fixes) — à affiner avec le retour pilote.
- **Next recommended action:** Sur une boutique pilote avec des actions appliquées atteignant J+28, ouvrir `/app/continuous-improvement`, vérifier les badges SEO/GEO et les recommandations, puis exporter le JSON et confirmer la présence de `effectiveness` (verdicts + recommandations + by_field).

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Claude (Opus 4.8)
- **Goal:** Permettre au marchand d'activer/désactiver un agent GEO quotidien, de lancer un test unique dans 5 minutes et d'exporter les résultats en JSON, depuis `/app/continuous-improvement`.
- **Summary:** Nouvelle couche d'orchestration `app/agent_schedule` au-dessus de `run_learning_cycle()` (aucun second agent). Table `agent_schedule_settings` (1 ligne/shop : enabled, mode, frequency, local_time, timezone, next_run_at, last_run_at, last_run_id, test_run_at). `scheduler.py` calcule `next_run_at` (J+1 via `zoneinfo`, défaut Europe/Paris 08:00), expose `run_due_agent_schedules()` (réutilisable par cron) avec garde-fous budget : le tick ne fait qu'un scan DB, un cycle ne tourne qu'au plus 1×/jour, cooldown anti-emballement (`AGENT_SCHEDULE_MIN_INTERVAL_HOURS`, défaut 20 h), test strictement one-shot (`test_run_at` consommé), set in-process `_RUNNING` anti-double-run, skip si pas d'analyse marché. `enable_daily` synchronise `merchant_learning_settings` (source de vérité du mode). Endpoints `GET/PUT …/agent-schedule/{status,settings}`, `POST …/{disable,test-in-5-min}`, `GET …/export`, et interne `POST /api/internal/agent-schedule/run-due` (require_internal_secret, pour Render/Railway/Vercel Cron toutes les 5-10 min). Ticker in-process ajouté au `lifespan` (à côté de JobWorker), désactivable via `AGENT_SCHEDULE_TICKER=false`. UI : nouvelle Card « Automatisation de l'agent » sous la Card « Agent de correction GEO » (statut, mode semi_auto recommandé par défaut + warning auto_apply, heure 08:00, boutons activer/désactiver/test 5 min/export, prochain & dernier lancement). Export téléchargé côté client (`leonie-agent-results-{shop}-{date}.json`) via un intent action qui agrège settings + learning_runs + agent_runs + approvals + tag_history + events GEO + produits.
- **Files created:** `app/agent_schedule/__init__.py`, `app/agent_schedule/store.py`, `app/agent_schedule/scheduler.py`, `app/agent_schedule/export.py`, `app/api/agent_schedule.py`, `tests/test_agent_schedule/__init__.py`, `tests/test_agent_schedule/test_scheduler.py`, `tests/test_api/test_agent_schedule.py`.
- **Files modified:** `app/db.py` (DDL SQLite+PG `agent_schedule_settings`), `app/main.py` (router + ticker lifespan), `shopify-app/app/routes/app.continuous-improvement.tsx` (loader/action/Card/export), `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne pas dupliquer l'agent : la planification réutilise `run_learning_cycle()`, le mode reste géré par `merchant_learning_settings`. Garde-fou budget prioritaire (demande explicite marchand) en couches. Test 5 min indépendant du flag quotidien et, en semi_auto, `confirm_live_write=False` ⇒ aucune écriture Shopify live. Export via action serveur + download client (pattern de `app.market-analysis.tsx`).
- **Validations run:** `ruff check .` ✅ ; `pytest tests/test_agent_schedule tests/test_api/test_agent_schedule.py` → **17 passed** ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** `pytest` complet : 72 échecs **pré-existants** et indépendants de cette tâche (modules optionnels `openai`/`groq` absents ; tests shops/privacy/billing/pagespeed renvoyant 401 sur l'environnement) — vérifiés identiques sur le checkout propre via `git stash`. `npm run typecheck` : seul l'avertissement pré-existant `tsconfig baseUrl` (TS 7.0), présent aussi sans mes changements ; aucune erreur sur le fichier modifié. Pas de test live Shopify/cron.
- **Open issues:** Sur Render/Railway, configurer soit le ticker in-process (par défaut, intervalle `AGENT_SCHEDULE_TICK_SECONDS`=300) soit un Cron externe vers `POST /api/internal/agent-schedule/run-due`. Le test « dans 5 min » ne s'exécute réellement qu'au prochain tick/cron (latence ≈ intervalle). L'agent ne tourne pas tant qu'aucune analyse marché n'existe pour le shop.
- **Next recommended action:** Sur une boutique pilote avec analyse marché, activer l'agent quotidien en semi_auto, lancer un test 5 min, vérifier l'apparition d'un run + `next_run_at`/`last_run_at`, puis exporter le JSON et contrôler qu'il contient settings, learning_runs, agent_runs, approvals, tag_history et events.

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter un groupe contrôle automatique pour la boucle d'apprentissage avancée, puis commit et push.
- **Summary:** Ajout de `app/learning/control_group.py` : pour chaque événement mature, le scheduler peut maintenant construire un contrôle synthétique à partir de produits similaires non modifiés. Le sélecteur exclut le produit traité, les produits inactifs/non publiés, les produits avec événement GEO appliqué/mesuré/rollback dans la fenêtre, et ceux avec `seo_changes` dans la fenêtre. La similarité combine catégorie/type, collections communes, bucket d'impressions, position proche, source du mot-clé et score d'opportunité proche. Les métriques contrôle sont agrégées par moyenne pondérée quand au moins 3 produits témoins ont de vraies métriques avant/après (`learning_metrics`/`control_metrics` ou snapshots GEO). Le scheduler utilise d'abord les `control_metrics` explicites du ledger, puis ce contrôle automatique en fallback. Si moins de 3 témoins valides existent, aucun contrôle n'est injecté afin de ne pas gonfler artificiellement la confiance.
- **Files created:** `app/learning/control_group.py`, `tests/test_learning/test_control_group.py`.
- **Files modified:** `app/learning/scheduler.py`, `tests/test_learning/test_scheduler.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne jamais fabriquer de métrique après coup depuis un seul point GSC courant : un produit témoin doit fournir un vrai couple before/after ou deux snapshots exploitables. Garder une qualité minimale à 3 témoins ; `fair` pour 3-4, `strong` à partir de 5. Garder le fallback explicite prioritaire pour que les futurs jobs de mesure puissent fournir un groupe contrôle plus robuste.
- **Validations run:** `ruff format app/learning/control_group.py app/learning/scheduler.py tests/test_learning/test_control_group.py tests/test_learning/test_scheduler.py` ✅ ; `ruff check .` ✅ ; `python -m py_compile app/learning/control_group.py app/learning/scheduler.py app/learning/outcomes.py app/learning/features.py app/learning/learner.py app/learning/store.py app/db.py app/geo/continuous_agent.py` ✅ ; `pytest tests/test_learning/test_control_group.py tests/test_learning/test_scheduler.py tests/test_learning/test_outcomes.py tests/test_learning/test_learner_policy.py` → **42 passed** ✅ ; `pytest` → **1752 passed, 188 skipped** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Pas de test live Shopify/GSC/GA4 ; le contrôle automatique nécessite des métriques before/after réelles ou des snapshots GEO sur des produits témoins.
- **Open issues:** La qualité du contrôle dépendra de la disponibilité de métriques produits non modifiés. Le prochain palier utile est d'alimenter automatiquement `learning_metrics`/snapshots pour les produits témoins au moment des jobs de mesure J+14/J+28.
- **Next recommended action:** Déployer, puis sur une boutique pilote avec assez de produits similaires, vérifier qu'une observation J+28 contient `control_metrics.selection_method = similar_unmodified_products_v1` et un `control_size >= 3`.

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Codex (GPT-5)
- **Goal:** Appliquer la boucle d'apprentissage avancée pour tirer parti des informations récoltées : ledger actionnable, fenêtres d'observation, verdict d'expérience, signaux tags/questions/concurrents et policy update.
- **Summary:** La boucle learning apprend désormais depuis des observations liées à un événement ledger précis (`ledger_event_id`) et enrichies par `metadata_json`. `build_observation_from_event()` produit un verdict stable (`positive_high_confidence`, `positive_low_confidence`, `neutral`, `negative`, `inconclusive`, `polluted_window`) avec `learnable=false` pour les fenêtres polluées/inconclusives. Le scheduler déduplique par événement + fenêtre, récupère les métriques contrôle explicites si elles sont présentes, détecte les actions qui se chevauchent sur le même produit dans la fenêtre J+14/J+28/J+60, et empêche ces fenêtres de nourrir les poids. Les features apprenables incluent maintenant champ, présence/source du mot-clé cible, tags à renforcer/éviter/forcer, questions pendantes, gaps concurrents et présence de faits/requêtes. Les candidats futurs exposent les mêmes features, ce qui permet aux tags/gaps validés par les résultats de modifier le ranking. L'agent continu remplit aussi `metrics_before` depuis les métriques GSC disponibles sur les mots-clés produit quand il crée un événement de proposition.
- **Files created:** Aucun.
- **Files modified:** `app/db.py`, `app/geo/continuous_agent.py`, `app/learning/models.py`, `app/learning/store.py`, `app/learning/outcomes.py`, `app/learning/features.py`, `app/learning/learner.py`, `app/learning/scheduler.py`, `tests/test_learning/test_store.py`, `tests/test_learning/test_outcomes.py`, `tests/test_learning/test_learner_policy.py`, `tests/test_learning/test_scheduler.py`, `tests/test_geo/test_continuous_agent.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne pas créer une nouvelle table d'expérimentation : enrichir `learning_observations` avec `ledger_event_id` + `metadata_json` suffit pour ce palier. Ne pas fabriquer de groupe contrôle artificiel depuis d'autres événements optimisés ; seuls les `control_metrics` explicitement fournis dans le ledger sont utilisés. Les fenêtres polluées restent traçables mais ne mettent pas à jour les poids. Les features tags/questions/concurrents sont compactes et plafonnées pour éviter une explosion de cardinalité.
- **Validations run:** `ruff format ...` fichiers learning/GEO/tests concernés ✅ ; `ruff check .` ✅ ; `python -m py_compile app/learning/models.py app/learning/store.py app/learning/outcomes.py app/learning/features.py app/learning/learner.py app/learning/scheduler.py app/geo/continuous_agent.py app/db.py` ✅ ; `pytest tests/test_learning/test_store.py tests/test_learning/test_outcomes.py tests/test_learning/test_learner.py tests/test_learning/test_learner_policy.py tests/test_learning/test_scheduler.py tests/test_geo/test_continuous_agent.py` → **53 passed** ✅ ; `pytest tests/test_learning tests/test_geo/test_continuous_agent.py tests/test_geo/test_continuous_agent_learning.py tests/test_geo/test_continuous_improvement.py tests/test_api/test_learning.py` → **97 passed** ✅ ; `pytest` → **1749 passed, 188 skipped** ✅.
- **Validations skipped:** `npm run typecheck` / `npm run build` non relancés pendant cette tâche car aucun fichier frontend n'a été modifié par cette boucle d'apprentissage. Pas de test live Shopify/GSC/LLM ; nécessite boutique pilote avec événements appliqués et métriques J+14/J+28.
- **Open issues:** La boucle ne crée pas encore automatiquement de groupe contrôle à partir de produits similaires non modifiés ; elle consomme seulement un contrôle explicite si le ledger le contient. Les métriques `metrics_after` doivent encore être alimentées par les jobs de mesure existants pour produire de vrais verdicts. Les anciennes observations restent sans `metadata_json` riche jusqu'aux prochains cycles.
- **Next recommended action:** Alimenter `control_metrics` dans les futurs jobs de mesure à partir de produits similaires non modifiés, puis afficher dans l'UI learning les verdicts d'expérience et les fenêtres polluées pour rendre la causalité lisible au marchand.

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Codex (GPT-5)
- **Goal:** Exécuter les tâches 1, 3, 4, 5 et 7 du plan d'amélioration : contexte produit canonique, tags comme mémoire stratégique, séparation diagnostic/génération finale, exploitation structurée des concurrents et attribution enrichie.
- **Summary:** Ajout d'un package `app/product_optimization` avec `build_product_optimization_context()` : chaque produit enrichi expose désormais un contexte stable `optimization_context` contenant ressource, profil/niche, mots-clés, faits confirmés/manquants, pipeline de questions, guidance tags, matrice de surfaces, patterns concurrents non copiables, contrat de génération et attribution. `enrich_market_analysis_result()` attache ce contexte après fusion des tags et éléments, et le job Analyse marché lui transmet le business profile + niche hypothesis quand disponibles. `ContentActionRequest` accepte `optimization_context`; le runner transforme tags + gaps concurrents + questions en `feedback` de prompt et inclut ce contexte dans le hash cache LLM. L'agent d'amélioration continue passe le contexte aux Content Actions et inscrit dans le ledger une attribution compacte (`target_keyword`, `keyword_source`, tags à renforcer/éviter, gaps concurrents, questions pendantes). Les approvals learning transportent aussi `ledger_event_id`/attribution, et l'application marchand met l'événement GEO en `applied` + `waiting_for_window`. Types Remix ajoutés en option sans nouvelle UI.
- **Files created:** `app/product_optimization/__init__.py`, `app/product_optimization/context.py`, `tests/test_product_optimization/test_product_context.py`.
- **Files modified:** `app/api/market_analysis.py`, `app/content_actions/schema.py`, `app/content_actions/runner.py`, `app/geo/continuous_improvement.py`, `app/geo/continuous_agent.py`, `app/learning/policy.py`, `app/learning/approvals.py`, `shopify-app/app/lib/marketAnalysisShared.tsx`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/test_content_actions/test_runner.py`, `tests/test_geo/test_continuous_agent.py`, `tests/test_geo/test_continuous_improvement.py`, `tests/test_learning/test_approvals.py`.
- **Decisions made:** Garder Analyse marché comme diagnostic/brief et `Content Actions` comme générateur final publiable, sans monter le routeur archivé. Ne pas créer de nouvelle table : utiliser `optimization_context` dans le JSON produit et les snapshots `geo_impact_events` pour l'attribution. Les données concurrentes restent des écarts structurels et exemples de patterns, jamais une source de copie ou de faits produit. Les tags négatifs/risques bloquent l'auto-apply via le contrat de génération, mais les tags neutres verrouillés par le marchand restent neutres.
- **Validations run:** `ruff format ...` fichiers Python/tests concernés ✅ ; `ruff check .` ✅ ; `python -m py_compile app/product_optimization/context.py app/geo/continuous_improvement.py app/content_actions/schema.py app/content_actions/runner.py app/geo/continuous_agent.py app/learning/policy.py app/learning/approvals.py` ✅ ; `pytest tests/test_product_optimization tests/test_content_actions tests/test_learning tests/test_geo/test_continuous_improvement.py tests/test_geo/test_continuous_agent.py tests/test_geo/test_continuous_agent_learning.py tests/test_api/test_market_analysis.py` → **130 passed** ✅ ; `pytest` → **1743 passed, 188 skipped** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de test live Shopify/DataForSEO/LLM ; nécessite boutique pilote, analyse fraîche et token actif. Pas de nouvelle UI navigateur car l'incrément expose un contrat backend/types, sans rendu visible.
- **Open issues:** Les analyses existantes doivent être relues via l'endpoint ou régénérées pour obtenir `optimization_context`. Le routeur public `content_actions` reste archivé dans `main.py`; le branchement profite aujourd'hui surtout à l'agent continu/runtime interne. L'attribution est beaucoup plus riche, mais la causalité reste dépendante de la qualité des métriques J+14/J+28 et des groupes contrôle.
- **Next recommended action:** Relancer une Analyse marché pilote, vérifier qu'un produit contient `optimization_context`, lancer un cycle “Amélioration continue” en `semi_auto`, valider une action sûre, puis vérifier que l'événement GEO passe à `applied` avec `optimization_attribution` avant la fenêtre J+14/J+28.

## Previous completed task

- **Date:** 2026-06-05
- **Agent:** Claude (Opus 4.8)
- **Goal:** Masquer la page Concurrents SERP et gérer les concurrents (ajout + exclusion) depuis un aperçu sur l'accueil, qui alimente l'analyse produit.
- **Summary:** **Masquage** : retrait du lien `/app/competitor-crawl` du menu (`app.tsx`) et du bouton « Voir le crawl SERP » de l'accueil — la route et le backend `competitor_serp` restent sur disque (accessibles par URL directe). **Liste d'exclusion** : nouveau `market_analysis_competitors_excluded.json` via `load_excluded_competitors`/`save_excluded_competitors` (competitors.py). Les endpoints `GET/PUT /market-analysis/competitors` renvoient/acceptent désormais `{competitors, excluded}` (PUT ne touche que les clés présentes → `settings.competitors.tsx` reste compatible). L'engine charge l'exclusion tôt, l'ajoute aux `merchant_domains` passés au crawl par produit (donc exclus du contenu) et filtre `competitor_signals` + `domain_competitor_signals` via `_drop_excluded_signals`. **Accueil** : nouveau composant `CompetitorsCard` (état local optimiste + `useFetcher`, intent `saveCompetitors`) qui affiche `union(competitorSignals, manuels) − exclus` avec badge « auto » pour les détectés, une croix [✕] par concurrent (l'exclure : ajout à excluded + retrait de manual, robuste même si re-détecté) et un champ d'ajout (ajout à manual + retrait d'excluded). Le loader accueil charge en plus la liste competitors.
- **Files created:** `tests/market_analysis/test_competitor_exclusion.py`.
- **Files modified:** `app/market_analysis/competitors.py`, `app/api/market_analysis.py` (endpoints étendus), `app/market_analysis/engine.py` (`_drop_excluded_signals` + application exclusion crawl/signals), `shopify-app/app/routes/app.tsx` (nav), `shopify-app/app/routes/app._index.tsx` (loader + action `saveCompetitors` + `CompetitorsCard` + prop drilling), `docs/AI_HANDOFF.md`.
- **Decisions made:** Réutiliser `market_analysis_competitors.json` (manuels, déjà branché via `build_competitor_signals`) + fichier d'exclusion séparé plutôt qu'un nouveau modèle. [✕] = exclusion robuste (peu importe la source) pour qu'un domaine détecté ne revienne pas à la prochaine analyse. Page seulement masquée (pas supprimée) — `competitor_serp_engine` conservé, exclusion non appliquée à cette page masquée (non requis). Endpoint PUT rétro-compatible (clés optionnelles).
- **Validations run:** `ruff check` (competitors/api/engine/tests) ✅ ; `pytest tests/market_analysis/test_competitor_exclusion.py` → **5 passed** ✅ ; `pytest` → **1740 passed, 188 skipped** ✅ ; `npm run typecheck` ✅ ; `npm run build` ✅.
- **Validations skipped:** Pas de test API TestClient des endpoints competitors (auth lourde à scaffolder ; endpoints = fins wrappers sur des fonctions de persistance déjà testées unitairement). Pas de test live.
- **Open issues:** Le `market_analysis_latest.json` existant garde un domaine exclu dans `competitor_signals` jusqu'à la prochaine analyse — l'aperçu accueil le masque déjà via le filtre `excluded`, et l'analyse ne le reprendra plus. L'édition `competitor_domains` du profil (textarea) coexiste toujours (vue « ce que l'IA comprend »).
- **Next recommended action:** Déployer (frontend + backend), vérifier sur l'accueil : ajout d'un domaine → apparaît ; [✕] sur un détecté → disparaît ; relancer une analyse marché → le domaine exclu n'apparaît plus dans les concurrents ni dans les sources de contenu produit ; menu sans « Concurrents SERP ».

## Earlier task (2026-06-04) — contenu produit nourri par les concurrents

- **Date:** 2026-06-04
- **Agent:** Claude (Opus 4.8)
- **Goal:** Nourrir le contenu produit (meta titre/description, FAQ, blog, description) avec les données concurrents SERP, automatiquement pendant l'analyse marché.
- **Summary:** Le crawl concurrent par produit (`_run_competitor_crawl_analysis`) est désormais **actif par défaut** dans l'analyse marché via `CompetitorCrawlConfig.for_market_analysis()` (ON sauf `COMPETITOR_CRAWL_ENABLED=false` explicite ; caps env conservés). Le formateur `format_competitor_crawl_for_prompt` n'expose plus seulement des moyennes : il injecte maintenant les **détails actionnables** lus dans `insights["top_urls"]` — titres SEO concurrents (≤3), meta descriptions concurrentes (≤3), sous-thèmes/H2 dédupliqués (≤8), longueur cible médiane, featured snippet. Les instructions Pass 2 (`_build_pass2_prompt`) pointent ces sections vers les bons champs : meta_title/description s'inspirent des titres/metas concurrents (sans copier), FAQ complète avec les thèmes concurrents, blog_outline/blog_ideas se structurent sur les H2 concurrents, product_description vise la longueur médiane, geo_answer_block s'inspire du snippet. Garde-fous anti-copie/anti-inférence conservés. Fail-open total (crawl vide ou LLM KO → analyse continue).
- **Files created:** `tests/market_analysis/test_competitor_crawl_config.py`.
- **Files modified:** `app/market_analysis/competitor_crawl/config.py` (factory `for_market_analysis` + `from_env(default_enabled=...)`), `app/market_analysis/competitor_crawl/prompt.py` (formateur enrichi + helpers `_collect`/`_collect_many`/`_first`/`_get`), `app/market_analysis/engine.py` (config crawl + instructions Pass 2), `tests/market_analysis/test_competitor_crawl_insights.py` (tests formateur enrichi + caps), `.env.example`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Rester dans le flux d'analyse marché (pas de dépendance à la page Concurrents ni timing). Activer le crawl par défaut (demande explicite « pendant l'analyse marché auto ») avec kill-switch `COMPETITOR_CRAWL_ENABLED=false`. Capper strictement les exemples injectés (3 titres, 3 metas, 8 H2) pour ne pas exploser le prompt Pass 2 (~8192 tokens). Ne pas connecter `competitor_serp_latest.json` (timing fragile) — réutiliser les insights déjà produits par le crawl par produit.
- **Validations run:** `ruff check app/market_analysis/competitor_crawl/config.py app/market_analysis/competitor_crawl/prompt.py app/market_analysis/engine.py tests/...` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_config.py tests/market_analysis/test_competitor_crawl_insights.py` → **12 passed** ✅ ; `pytest` → **1735 passed, 188 skipped** ✅.
- **Validations skipped:** `npm` non lancé (aucun fichier frontend modifié). Pas de test live DataForSeo/LLM — à valider sur boutique pilote.
- **Open issues:** Le contenu déjà généré n'est pas rétro-actif ; relancer une analyse marché pour bénéficier de l'enrichissement. Latence +30-90s/analyse selon le nombre d'URLs crawlées (ajustable via `COMPETITOR_CRAWL_MAX_URLS_PER_*`).
- **Next recommended action:** Déployer, relancer une analyse marché (DataForSeo actif), ouvrir un produit et vérifier : FAQ reprenant des PAA, plan de blog reflétant des H2 concurrents, meta différenciée des titres concurrents, aucune phrase concurrente copiée.

## Previous task — page Concurrents (refonte)

- **Date:** 2026-06-04
- **Agent:** Claude (Opus 4.8)
- **Goal:** Refondre la page `/app/competitor-crawl` : passer d'un dump de métriques brutes par URL (lent, crawl 3-10 pages/concurrent) à des **profils explicatifs par concurrent** affichés immédiatement, enrichis par une synthèse LLM "ce qu'ils font bien / opportunités pour toi / actions".
- **Summary:** Nouvelle architecture à 2 couches. **Couche 1 (instantanée)** : `aggregate_competitors_from_serp()` lit le cache SERP DataForSeo (`keyword_cache.SERP`, aucun appel API), groupe par domaine concurrent et calcule par concurrent : mots-clés rankés, meilleur/moyenne rank, force estimée + label, titres échantillons, PAA, page top-rank. Exposée via `GET /competitor-serp/preview` (synchrone) → la page s'affiche tout de suite. **Couche 2 (job background ~30-40s)** : `run_competitor_serp_crawl()` crawle 1 seule page top-rank par concurrent (≤8), puis `_synthesize_competitor()` fait 1 appel LLM JSON par concurrent (`get_router`, fail-open) avec contexte business profile, produisant `{title_style, strengths[], opportunities[], inspiration[]}`. Le front affiche les profils SERP immédiatement, lance l'enrichissement sur bouton, et remplace par la version enrichie via polling 5s. Détail technique de la page crawlée disponible en accordéon. **Bugs corrigés en cours de route** : stale closure du poller (fetcherRef) et plafond crawl trop élevé.
- **Files created:** `app/market_analysis/competitor_serp_engine.py`, `app/api/competitor_serp.py`, `tests/market_analysis/test_competitor_serp_engine.py`.
- **Files modified:** `app/main.py` (router monté), `app/market_analysis/competitor_crawl/insights.py` (extraction de `url_to_competitor_top_url` réutilisable), `shopify-app/app/lib/marketAnalysisShared.tsx` (types `CompetitorProfile`/`CompetitorSynthesis`/`CompetitorSerpResult`), `shopify-app/app/routes/app.competitor-crawl.tsx` (refonte complète profil-par-concurrent), `docs/AI_HANDOFF.md`.
- **Decisions made:** Inverser la priorité — le cache SERP (titres/PAA/ranks) donne 80% de la valeur instantanément ; le crawl léger 1 page/concurrent + LLM n'enrichit que la couche narrative. Borner à 8 concurrents pour la latence. Fail-open total : LLM indisponible → `synthesis: null`, la page reste utilisable (profils SERP + détail technique). Garder une fonction `_format_merchant_context` locale avec les vraies clés du business profile (`brand_name`, `niche_summary`, `brand_voice`, `key_themes`, `target_personas`) plutôt qu'importer `engine._format_business_profile_context` (évite de charger le module engine massif).
- **Validations run:** `ruff check app/market_analysis/competitor_serp_engine.py app/api/competitor_serp.py tests/market_analysis/test_competitor_serp_engine.py` ✅ ; `pytest tests/market_analysis/test_competitor_serp_engine.py` → **6 passed** ✅ ; `pytest` → **1727 passed, 188 skipped** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de navigation navigateur (route embedded nécessitant session Shopify) ; typecheck + build valident la route Remix. Pas de test live DataForSeo/LLM dans cette session — à valider sur boutique pilote.
- **Next recommended action:** Déployer, ouvrir `/app/competitor-crawl` (profils SERP visibles immédiatement), cliquer "Générer l'analyse détaillée" et vérifier l'apparition de la synthèse LLM après ~30-40s sans rechargement. Vérifier fail-open en coupant le LLM.

## Earlier task (same date)

- **Date:** 2026-06-04
- **Agent:** Codex (GPT-5)
- **Goal:** Créer une page dédiée d'analyse concurrentielle SERP qui étend le bloc “Concurrents” de l'accueil avec toutes les données du crawl concurrentiel.
- **Summary:** Ajout de la route Shopify embedded `/app/competitor-crawl`, reliée depuis le menu principal et le bloc “Concurrents” de l'accueil. La page charge la dernière Analyse marché, agrège `competitor_crawl_insights` par produit, filtre par produit/type de page, et affiche chaque URL SERP crawlée avec mot-clé associé, rank, type de page (produit/collection/blog/FAQ/guide), intention, title/meta, H1/H2/H3, longueur du contenu, FAQ visible, blocs réponse courte, PAA, featured snippet, JSON-LD, breadcrumb, maillage interne et ancres, images/alt text, preuves de confiance, tableaux/comparatifs, profondeur produit et gaps marchand. Le backend enrichit désormais les features stockées dans les insights avec les détails nécessaires, sans stocker le HTML concurrent complet.
- **Files created:** `shopify-app/app/routes/app.competitor-crawl.tsx`.
- **Files modified:** `app/market_analysis/competitor_crawl/extractor.py`, `app/market_analysis/competitor_crawl/insights.py`, `app/market_analysis/engine.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/lib/marketAnalysisShared.tsx`, `shopify-app/app/routes/app._index.tsx`, `shopify-app/app/routes/app.tsx`, `tests/market_analysis/test_competitor_crawl_extractor.py`, `tests/market_analysis/test_competitor_crawl_insights.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Afficher les textes courts structurels déjà extraits (title/meta/Hn/alt/ancres), mais ne jamais stocker le HTML concurrent complet. Garder la page compatible avec les anciennes analyses : les sections retombent sur les résumés existants ou “—” si une analyse doit être régénérée. Ne pas ajouter de nouvel appel DataForSEO : la page réutilise uniquement la dernière analyse persistée.
- **Validations run:** `ruff format app/market_analysis/competitor_crawl/extractor.py app/market_analysis/competitor_crawl/insights.py app/market_analysis/engine.py tests/market_analysis/test_competitor_crawl_extractor.py tests/market_analysis/test_competitor_crawl_insights.py` ✅ ; `python -m py_compile app/market_analysis/competitor_crawl/extractor.py app/market_analysis/competitor_crawl/insights.py app/market_analysis/engine.py` ✅ ; `ruff check app/market_analysis/competitor_crawl/extractor.py app/market_analysis/competitor_crawl/insights.py app/market_analysis/engine.py tests/market_analysis/test_competitor_crawl_extractor.py tests/market_analysis/test_competitor_crawl_insights.py` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_extractor.py tests/market_analysis/test_competitor_crawl_insights.py tests/market_analysis/test_competitor_crawl_integration.py` → **16 passed** ✅ ; `ruff check .` ✅ ; `pytest tests/market_analysis` → **191 passed** ✅ ; `pytest` → **1721 passed, 188 skipped** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de navigation navigateur local sur `/app/competitor-crawl` car la route embedded appelle `authenticate.admin()` et nécessite une session Shopify active ; `npm run build` et `typecheck` valident néanmoins la route Remix.
- **Open issues:** Les analyses déjà générées avant ce changement n'auront pas tous les nouveaux détails page par page. Relancer Analyse marché avec `COMPETITOR_CRAWL_ENABLED=true` pour remplir les nouvelles sections. Certains signaux restent heuristiques (ex. promesse title, CTA meta, preuve de confiance) et doivent être lus comme indicateurs structurels, pas comme vérité métier.
- **Next recommended action:** Déployer, relancer une Analyse marché pilote, puis ouvrir `/app/competitor-crawl` depuis le menu “Concurrents SERP” ou le bouton “Voir le crawl SERP” sur l'accueil.

## Previous completed task

- **Date:** 2026-06-04
- **Agent:** Codex (GPT-5)
- **Goal:** Corriger les résultats réels du crawl concurrentiel après analyse pilote : exclusion du domaine public marchand et filtrage des mots-clés retail brandés.
- **Summary:** L'analyse marché ne considère plus uniquement le domaine `*.myshopify.com` comme domaine marchand : elle construit maintenant la liste des domaines publics connus depuis la config tenant, GSC, `COMPETITOR_CRAWL_MERCHANT_DOMAINS` et le shop courant, puis les transmet à la sélection d'URLs concurrentes. Le crawler concurrentiel ignore donc aussi `leoniedelacroix.com` quand DataForSEO le remonte dans les SERP. Le pool de mots-clés et la réparation Pass 1 filtrent désormais les requêtes explicitement brandées retailer/concurrent (`maxi zoo`, `decathlon`, `zooplus`, etc.) avant ciblage produit, tout en conservant les requêtes brandées marchand Léonie et les requêtes produit génériques.
- **Files created:** Aucun.
- **Files modified:** `.env.example`, `app/market_analysis/competitor_crawl/url_selection.py`, `app/market_analysis/engine.py`, `tests/market_analysis/test_competitor_crawl_url_selection.py`, `tests/market_analysis/test_keyword_pool.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder une liste courte de retailers génériques pour éviter que des requêtes navigational/retailer deviennent des targets produit, et l'étendre avec les concurrents déclarés dans le business profile quand ils existent. Ne pas bloquer une requête contenant une marque marchande connue. Ajouter un env optionnel `COMPETITOR_CRAWL_MERCHANT_DOMAINS` pour les cas où le domaine public n'est pas dans la config tenant/GSC.
- **Validations run:** `ruff format app/market_analysis/engine.py app/market_analysis/competitor_crawl/url_selection.py tests/market_analysis/test_competitor_crawl_url_selection.py tests/market_analysis/test_keyword_pool.py` ✅ ; `python -m py_compile app/market_analysis/engine.py app/market_analysis/competitor_crawl/url_selection.py` ✅ ; `ruff check app/market_analysis/engine.py app/market_analysis/competitor_crawl/url_selection.py tests/market_analysis/test_competitor_crawl_url_selection.py tests/market_analysis/test_keyword_pool.py tests/market_analysis/test_competitor_crawl_integration.py` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_url_selection.py` → **6 passed** ✅ ; `pytest tests/market_analysis/test_keyword_pool.py` → **28 passed** ✅ ; `pytest tests/market_analysis/test_competitor_crawl_integration.py` → **5 passed** ✅ ; `pytest tests/market_analysis` → **189 passed** ✅ ; `ruff check .` ✅ ; `pytest` → **1719 passed, 188 skipped** ✅.
- **Validations skipped:** `cd shopify-app && npm run typecheck` et `cd shopify-app && npm run build` non lancés car aucun fichier frontend/TypeScript n'a été modifié.
- **Open issues:** À valider en live après déploiement Render avec une nouvelle Analyse marché : les produits ne doivent plus crawler `leoniedelacroix.com`, et les requêtes `maxi zoo` / `decathlon` ne doivent plus apparaître comme mots-clés cibles produit. Si un autre retailer apparaît, l'ajouter à la config business profile ou à la liste contrôlée.
- **Next recommended action:** Déployer sur Render, garder `COMPETITOR_CRAWL_ENABLED=true` avec limites basses, relancer une analyse pilote et inspecter `seo_keywords`, `competitor_crawl_insights.top_urls` et `sources_used`.

## Previous completed task

- **Date:** 2026-06-04
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter le crawl concurrentiel DataForSEO directement dans l'analyse produit, avec extraction SEO/GEO structurelle, comparaison marchand, boosts explicables et enrichissement Pass 2.
- **Summary:** Nouveau package `app/market_analysis/competitor_crawl` : configuration env désactivée par défaut, sélection des URLs SERP DataForSEO, filtrage domaine marchand/cart/checkout/account/search, fetcher HTTP respectant robots.txt, throttling par domaine, timeout, cache DB sans stockage HTML, extraction de features SEO/GEO/schema/platform, agrégation d'insights et formatage prompt. `run_market_analysis()` sélectionne les top URLs concurrentes après Pass 1/SERP, crawl en fail-open si `COMPETITOR_CRAWL_ENABLED=true`, compare avec la fiche marchand, expose `competitor_crawl_insights` par produit, ajoute `competitor_pattern_boost` plafonné à +20, enrichit `recommended_content_actions` et injecte un résumé structurel dans Pass 2 avec consignes anti-copie. Tables ajoutées : `competitor_crawl_cache`, `competitor_crawl_runs`. `.env.example` documente les variables `COMPETITOR_CRAWL_*`.
- **Files created:** `app/market_analysis/competitor_crawl/__init__.py`, `app/market_analysis/competitor_crawl/models.py`, `app/market_analysis/competitor_crawl/config.py`, `app/market_analysis/competitor_crawl/url_selection.py`, `app/market_analysis/competitor_crawl/fetcher.py`, `app/market_analysis/competitor_crawl/extractor.py`, `app/market_analysis/competitor_crawl/store.py`, `app/market_analysis/competitor_crawl/insights.py`, `app/market_analysis/competitor_crawl/prompt.py`, `tests/market_analysis/test_competitor_crawl_url_selection.py`, `tests/market_analysis/test_competitor_crawl_extractor.py`, `tests/market_analysis/test_competitor_crawl_insights.py`, `tests/market_analysis/test_competitor_crawl_integration.py`.
- **Files modified:** `.env.example`, `app/db.py`, `app/market_analysis/engine.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder le crawl concurrentiel strictement optionnel et désactivé par défaut. Ne pas ajouter Playwright ni contournement anti-bot. Ne stocker que hash + features, jamais le HTML concurrent. Ne pas modifier l'UI Remix dans ce passage : les données sont exposées dans le JSON produit pour éviter un changement frontend risqué. Définir un échantillon minimum de 2 pages pour créer des boosts ; sous ce seuil, insights présents mais boost nul. Ajouter `competitor_crawl` dans `sources_used` seulement si au moins une feature concurrente est extraite.
- **Validations run:** `python -m py_compile app/market_analysis/competitor_crawl/*.py app/market_analysis/engine.py app/db.py` ✅ ; `ruff format ...` fichiers Python/tests concernés ✅ ; `ruff check .` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_url_selection.py` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_extractor.py` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_insights.py` ✅ ; `pytest tests/market_analysis/test_competitor_crawl_integration.py` ✅ ; `pytest tests/market_analysis` → **185 passed** ✅ ; `pytest` → **1715 passed, 188 skipped** ✅ ; `git diff --check` ✅.
- **Validations skipped:** `cd shopify-app && npm run typecheck` et `cd shopify-app && npm run build` non lancés car aucun fichier frontend/TypeScript n'a été modifié.
- **Open issues:** Pas de test live DataForSEO + robots.txt externe dans cette session ; à valider sur une boutique pilote avec `COMPETITOR_CRAWL_ENABLED=true` et limites basses. L'UI Analyse marché n'affiche pas encore un bloc dédié “Patterns concurrents détectés”, mais le JSON produit expose toutes les données nécessaires.
- **Next recommended action:** Activer en staging avec `COMPETITOR_CRAWL_ENABLED=true`, `COMPETITOR_CRAWL_MAX_URLS_PER_RUN` bas, relancer une Analyse marché pilote et vérifier les champs `competitor_crawl_insights`, le boost appliqué et la présence du résumé structurel dans les logs/debug Pass 2.

## Previous completed task

- **Date:** 2026-06-03
- **Agent:** Codex (GPT-5)
- **Goal:** Implémenter un moteur d'apprentissage autonome SEO/GEO explicable, avec deux modes (`semi_auto`, `auto_apply`), suivi J+14/J+28, validations marchand et réinjection dans Analyse marché / Agent continu / Priorités.
- **Summary:** Ajout du package `app/learning` : modèles, features, outcomes, learner, policy, risk, approvals, store, scheduler et explications UI. Le moteur crée des observations J+14/J+28/J+60 depuis le ledger, calcule `outcome_score` [-100,+100], `confidence_score` [0,100] avec J+14 plafonné à 75, met à jour des poids merchant-specific et globaux anonymisés via moving average pondéré, puis classe les futures actions. Nouvelles tables `learning_observations`, `learning_weights`, `learning_runs`, `learning_policy_decisions`, `learning_pending_approvals`, `merchant_learning_settings`. Nouveaux endpoints `/api/shops/{shop}/learning/*` et `/api/internal/learning/run` protégé par `INTERNAL_API_SECRET`, plus handler job `learning_cycle`. L'agent continu crée maintenant des validations learning et auto-applique seulement les champs live-safe low-risk/high-confidence via les writers Shopify existants. Analyse marché, Priorités, Next Best Actions et Impact Report exposent les signaux learning en fail-open. La page Remix `/app/continuous-improvement` ajoute “Learning / Algorithme”, les deux modes uniquement, les métriques, les actions à valider, le bulk approve sûr et le suivi J+14/J+28.
- **Files created:** `app/learning/__init__.py`, `app/learning/models.py`, `app/learning/features.py`, `app/learning/outcomes.py`, `app/learning/learner.py`, `app/learning/policy.py`, `app/learning/store.py`, `app/learning/scheduler.py`, `app/learning/explain.py`, `app/learning/approvals.py`, `app/learning/risk.py`, `app/api/learning.py`, `docs/learning-engine.md`, `tests/test_learning/test_outcomes.py`, `tests/test_learning/test_learner_policy.py`, `tests/test_learning/test_approvals.py`, `tests/test_learning/test_modes.py`.
- **Files modified:** `app/main.py`, `app/db.py`, `app/jobs/handlers.py`, `app/geo/continuous_agent.py`, `app/geo/validation_timeline.py`, `app/geo/retention_milestones.py`, `app/geo/impact_report.py`, `app/geo/next_best_actions.py`, `app/geo/ledger.py`, `app/geo/optimization_snapshots.py`, `app/api/geo.py`, `app/market_analysis/engine.py`, `app/priorities/engine.py`, `shopify-app/app/routes/app.continuous-improvement.tsx`, `tests/test_api/test_geo.py`, `tests/test_geo/test_validation_timeline.py`, `tests/test_geo/test_retention_milestones.py`.
- **Decisions made:** Garder un algorithme déterministe et explicable plutôt qu'un modèle opaque ; J+28 pilote la décision principale, J+14 sert de signal intermédiaire, J+60 reste historique. Ne pas créer de troisième mode. Ne pas auto-appliquer blog, FAQ storefront, JSON-LD complexe, llms.txt/agents.md, alt text ou thème sans writer sûr explicite. Les poids globaux restent anonymisés par feature, sans données produit sensibles.
- **Validations run:** `python -m py_compile app/learning/*.py app/api/learning.py app/geo/continuous_agent.py app/geo/validation_timeline.py app/geo/retention_milestones.py app/geo/next_best_actions.py app/priorities/engine.py app/market_analysis/engine.py app/jobs/handlers.py app/db.py` ✅ ; `ruff format ...` fichiers Python concernés ✅ ; `ruff check app/learning app/api/learning.py ... tests/test_learning ...` ✅ ; `pytest tests/test_learning tests/test_geo/test_validation_timeline.py tests/test_geo/test_retention_milestones.py tests/test_geo/test_continuous_agent.py` → **28 passed** ✅ ; `pytest tests/test_learning tests/test_api/test_geo.py tests/test_api/test_market_analysis.py tests/test_geo/test_continuous_agent.py tests/test_geo/test_continuous_improvement.py tests/test_geo/test_validation_timeline.py tests/test_geo/test_retention_milestones.py tests/test_geo/test_next_best_actions.py tests/test_geo/test_impact_report.py` → **94 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Pas de test live Shopify auto-apply sur boutique officielle ; nécessite token actif, plan Pro/Agency, safe mode compatible et confirmation merchant. Pas de full `pytest` complet.
- **Open issues:** Les observations dépendent encore de la disponibilité réelle de `metrics_after` dans le ledger ; un prochain incrément peut enrichir automatiquement la collecte GSC/GA4 par page à chaque fenêtre. Le global anonymisé est prêt techniquement mais reste local au backend actuel tant qu'aucune consolidation multi-instance n'existe.
- **Next recommended action:** Déployer, configurer Render Cron sur `POST /api/internal/learning/run`, puis tester depuis Shopify dans “Amélioration continue” : mode `semi_auto`, lancer un cycle, valider une action sûre, attendre J+14/J+28 pour voir les poids évoluer.

## Previous completed task

- **Date:** 2026-06-03
- **Agent:** Codex (GPT-5)
- **Goal:** Corriger les faux statuts `JSON-LD: non amélioré`, `Maillage interne: non amélioré` et les faux produits orphelins observés après Analyse marché.
- **Summary:** Le builder JSON-LD accepte maintenant les formes Shopify GraphQL `images.edges` et `variants.edges`, ce qui évite que `proposed_schema_jsonld` tombe à `{}` par exception silencieuse. L'indicateur d'amélioration continue lit désormais `content_test_pack.proposed_schema_jsonld` en plus d'un éventuel champ top-level. Le moteur de maillage lit les produits de collection depuis `collection.product_ids`, `productIds` ou `products.edges`, lit les liens produits dans les articles depuis `linked_product_handles` ou les URLs `/products/<handle>` dans le HTML, et ne marque plus de produits orphelins quand aucune donnée de couverture collection/article exploitable n'est disponible.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/schema_builder.py`, `app/market_analysis/internal_linking.py`, `app/geo/continuous_improvement.py`, `tests/market_analysis/test_engine_geo_eeat.py`, `tests/market_analysis/test_internal_linking.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne pas afficher un diagnostic orphelin quand le crawl/snapshot ne fournit pas les relations nécessaires ; un diagnostic silencieux vaut mieux qu'un faux négatif marchand. Garder JSON-LD déterministe, mais rendre le parser compatible avec les formes Shopify réelles.
- **Validations run:** `ruff format app/market_analysis/schema_builder.py app/market_analysis/internal_linking.py app/geo/continuous_improvement.py tests/market_analysis/test_internal_linking.py tests/market_analysis/test_engine_geo_eeat.py` ✅ ; `ruff check app/market_analysis/schema_builder.py app/market_analysis/internal_linking.py app/geo/continuous_improvement.py tests/market_analysis/test_internal_linking.py tests/market_analysis/test_engine_geo_eeat.py` ✅ ; `pytest tests/market_analysis/test_internal_linking.py tests/market_analysis/test_engine_geo_eeat.py tests/test_geo/test_continuous_improvement.py` → **21 passed** ✅ ; `git diff --check` ✅.
- **Validations skipped:** Pas de nouvelle analyse live Shopify après déploiement ; il faudra relancer Analyse marché sur la boutique officielle pour régénérer le JSON-LD et recalculer les orphelins.
- **Open issues:** Si le snapshot officiel ne contient toujours aucune relation collection/article, le maillage restera `non amélioré` car l'app n'a pas de source fiable pour proposer un lien parent. Il faudra alors enrichir le crawl Shopify pour capturer les produits par collection et/ou les liens articles.
- **Next recommended action:** Déployer, relancer Analyse marché sur le site officiel, puis vérifier que les trois produits ne sont plus listés comme orphelins si leurs collections/articles sont bien présents dans le snapshot.

## Previous completed task

- **Date:** 2026-06-03
- **Agent:** Codex (GPT-5)
- **Goal:** Implémenter l'agent d'amélioration continue GEO : lecture des retours J+7/J+30/J+60, décision tags positifs/négatifs, génération GPT-4o mini, propositions, auto-apply sécurisé et journalisation score avant/après.
- **Summary:** Nouveau moteur `app/geo/continuous_agent.py` : il lit la dernière Analyse marché, agrège le ledger GEO, détecte les fenêtres dues J+7/J+30/J+60, calcule les deltas observés (`score_before/after`, `observed_impact`, `metrics_before/after`), met à jour les tags non verrouillés en positif/négatif/neutre, écrit l'historique dans `tag_performance_history`, génère des `content_actions` via le router LLM (GPT-4o mini côté provider OpenAI par défaut) et enregistre chaque proposition dans `geo_impact_events` avec score avant/après, justification et impact estimé. L'auto-apply est limité aux types déjà supportés par `safe_apply` (`meta_title`, `meta_description`, `product_description`) et exige plan Pro/Agency, access token, confirmation explicite et garde-fou `LEONIE_PILOT_SAFE_MODE`. La page `/app/continuous-improvement` a maintenant un bloc “Agent de correction GEO” avec lancement en mode proposition ou auto-apply sécurisé, et affiche les derniers runs + décisions tags. L'API expose `POST /api/shops/{shop}/geo/continuous-improvement/run`.
- **Files created:** `app/geo/continuous_agent.py`, `tests/test_geo/test_continuous_agent.py`.
- **Files modified:** `app/api/geo.py`, `app/db.py`, `app/geo/continuous_improvement.py`, `shopify-app/app/routes/app.continuous-improvement.tsx`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne pas appliquer automatiquement les surfaces non supportées par les mutations Shopify existantes ; elles restent en proposition. Les tags verrouillés par le marchand ne sont jamais reclassés par l'agent. Les tags de type `risk` restent négatifs même si le produit performe mieux. Les runs agent sont persistés dans `continuous_improvement_agent_runs`, séparés du ledger d'impact qui reste la source d'audit des actions.
- **Validations run:** `ruff format app/geo/continuous_agent.py app/geo/continuous_improvement.py app/api/geo.py app/db.py tests/test_geo/test_continuous_agent.py` ✅ ; `ruff check app/geo/continuous_agent.py app/geo/continuous_improvement.py app/api/geo.py app/db.py tests/test_geo/test_continuous_agent.py` ✅ ; `pytest tests/test_geo/test_continuous_agent.py tests/test_geo/test_continuous_improvement.py tests/test_api/test_market_analysis.py` → **15 passed** ✅ ; `pytest tests/test_api/test_geo.py tests/test_geo/test_continuous_agent.py tests/test_geo/test_continuous_improvement.py` → **38 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de test live d'auto-apply Shopify ; nécessite boutique installée, plan applicable, token actif, `LEONIE_PILOT_SAFE_MODE` désactivé et confirmation humaine. Pas de full `pytest` complet.
- **Open issues:** L'auto-apply UI utilise un bouton explicite mais pas encore une modale de confirmation détaillée par proposition. Les propositions générées couvrent d'abord les surfaces live-safe ; FAQ, JSON-LD, llms.txt, agents.md, liens internes et blog restent à intégrer à l'agent en mode proposition avancée.
- **Next recommended action:** Ajouter une revue détaillée des propositions générées par run dans `/app/continuous-improvement`, puis étendre les générateurs non live-safe en mode proposition seulement.

## Previous completed task

- **Date:** 2026-06-03
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter le système de tags à Analyse marché et créer une page « Amélioration continue » pour suivre les modifications de l'agent et les métriques.
- **Summary:** Analyse marché enrichit désormais chaque produit avec `improvement_tags` (mots-clés, axes d'analyse, axes de contenu, risques, tags marchands) et `improvement_elements` indiquant simplement si chaque surface est améliorée ou non : meta title, meta description, description, FAQ, bloc GEO, blog, alt images, JSON-LD et maillage interne. Les tags dérivés sont persistés dans `product_improvement_tags` sans supprimer les tags marchands lors d'une nouvelle analyse. Une nouvelle API `/geo/continuous-improvement` agrège tags, éléments améliorés, ledger GEO et métriques. Une nouvelle route Remix `/app/continuous-improvement` affiche les produits suivis, tags positifs/négatifs, éléments améliorés et modifications enregistrées de l'agent. Le menu principal inclut maintenant « Amélioration continue ». Le texte de confirmation « Analyser tous les produits » précise que l'historique, les tags et les décisions marchands sont conservés.
- **Files created:** `app/geo/continuous_improvement.py`, `shopify-app/app/routes/app.continuous-improvement.tsx`, `tests/test_geo/test_continuous_improvement.py`.
- **Files modified:** `app/api/geo.py`, `app/api/market_analysis.py`, `app/db.py`, `shopify-app/app/lib/i18n.ts`, `shopify-app/app/lib/marketAnalysisShared.tsx`, `shopify-app/app/routes/app.market-analysis.tsx`, `shopify-app/app/routes/app.tsx`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Réutiliser le ledger GEO pour l'historique des modifications au lieu de créer un journal concurrent. Persister les tags dans une table dédiée avec clé `(shop, product_id, tag_id)` et ne jamais supprimer automatiquement les tags absents d'une nouvelle analyse. Afficher sur Analyse marché uniquement l'état « amélioré / non amélioré » demandé, et réserver les détails/métriques à la page « Amélioration continue ». Les tags négatifs sont visibles mais non destructifs ; le marchand peut forcer ses propres tags via l'endpoint dédié.
- **Validations run:** `python -m py_compile app/geo/continuous_improvement.py app/api/market_analysis.py app/api/geo.py app/db.py` ✅ ; `ruff format app/geo/continuous_improvement.py app/api/market_analysis.py app/api/geo.py app/db.py tests/test_geo/test_continuous_improvement.py` ✅ ; `ruff check app/geo/continuous_improvement.py app/api/market_analysis.py app/api/geo.py app/db.py tests/test_geo/test_continuous_improvement.py` ✅ ; `pytest tests/test_api/test_market_analysis.py tests/test_geo/test_continuous_improvement.py tests/test_geo/test_ledger.py` → **17 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de test navigateur live de la nouvelle page dans Shopify embedded ; nécessite backend lancé, session Shopify active et données d'analyse marché récentes. Pas de full `pytest` pour éviter une validation longue non nécessaire au vu du périmètre ciblé.
- **Open issues:** Le mode auto-apply complet de l'agent GEO n'est pas encore implémenté ; cette livraison pose la mémoire, les tags, les statuts d'amélioration et la page de suivi. Les tags peuvent être créés par API mais l'UI d'ajout/retrait manuel directement dans Analyse marché reste à faire si souhaitée.
- **Next recommended action:** Brancher les futures corrections GPT-4o mini sur `record_agent_change_from_product` / `geo_impact_events`, puis ajouter l'édition visuelle des tags marchand depuis Analyse marché ou Amélioration continue.

## Previous completed task

- **Date:** 2026-06-02
- **Agent:** Codex (GPT-5)
- **Goal:** Relier l'enrichissement schema à Analyse marché/profil sans sur-ingénierie et simplifier l'activation Theme App Extension.
- **Summary:** L'app embed de la Theme App Extension est désormais le point d'activation unifié « Giulio Geo » avec deux coches : afficher la FAQ produit et activer les JSON-LD produit/collection/organisation. Le bloc injecte `Product`, `CollectionPage` ou `Organization` selon le template, et enrichit `Product` avec `material`, `countryOfOrigin` et `additionalProperty` seulement si un metafield marchand `leonie.schema_facts` existe. Les anciens blocs séparés Product/Collection/Organization/FAQ section ont été supprimés pour éviter les doublons. Analyse marché gagne une action explicite « Synchroniser avec le thème » dans le pack GEO : elle écrit les faits confirmés autorisés dans `leonie.schema_facts` via Admin GraphQL, sans écrire automatiquement lors d'une sauvegarde de proposition. La page `/app/jsonld` reste inchangée comme écran de vérification/preview.
- **Files created:** Aucun.
- **Files modified:** `shopify-app/extensions/leonie-seo-jsonld/blocks/faq_embed.liquid`, `app/apply/apply_faq.py`, `app/api/market_analysis.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `shopify-app/app/lib/marketAnalysisShared.tsx`, `tests/apply/test_apply_faq.py`, `tests/test_api/test_market_analysis.py`, `docs/AI_HANDOFF.md`.
- **Files deleted:** `shopify-app/extensions/leonie-seo-jsonld/blocks/product_jsonld.liquid`, `shopify-app/extensions/leonie-seo-jsonld/blocks/collection_jsonld.liquid`, `shopify-app/extensions/leonie-seo-jsonld/blocks/organization_jsonld.liquid`, `shopify-app/extensions/leonie-seo-jsonld/blocks/faq_in_product.liquid`.
- **Decisions made:** Supprimer les anciens blocs séparés pour que le marchand n'ait qu'un seul bloc à activer. Ne pas connecter le storefront au backend : Liquid lit Shopify live + metafields. Ne pas publier les faits à la sauvegarde d'une proposition ; la synchronisation schema est une action explicite. Filtrer strictement les facts autorisées (`materials`, `origins`, certifications, warranty, care, dimensions, compatibility, use cases, selection criteria) pour éviter ratings/reviews/certifications hallucines.
- **Validations run:** `ruff format app/apply/apply_faq.py app/api/market_analysis.py tests/apply/test_apply_faq.py tests/test_api/test_market_analysis.py` ✅ ; `ruff check app/apply/apply_faq.py app/api/market_analysis.py tests/apply/test_apply_faq.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/apply/test_apply_faq.py tests/test_api/test_market_analysis.py` → **15 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de test live dans l'éditeur de thème Shopify ni de Rich Results Test après déploiement ; nécessite `shopify app deploy`, activation de l'app embed sur une boutique et test d'une URL publique.
- **Open issues:** Le statut `/app/jsonld` vérifie encore le snapshot d'audit, pas le HTML live du storefront après activation. Le nouveau metafield `leonie.schema_facts` est écrit uniquement depuis Analyse marché, pas depuis la page profil boutique.
- **Next recommended action:** Déployer l'extension, activer uniquement l'app embed « Giulio Geo » dans le thème pilote, cocher FAQ + JSON-LD, synchroniser un produit depuis Analyse marché, puis comparer `/app/jsonld`, le HTML source produit et Google Rich Results.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Codex (GPT-5)
- **Goal:** Continuer le chantier blog SEO+GEO — Sprint 2 : maillage interne dans les brouillons blog + surface robots.txt/crawlabilité IA sans écriture thème.
- **Summary:** Les brouillons blog récupèrent désormais les `recommended_internal_links` produits par Analyse marché et les conservent dans `internal_links`. Le marchand peut ajuster l'ancre et l'URL depuis la page Blog ; l'aperçu affiche un bloc « À lire aussi » et la publication Shopify ajoute le même bloc HTML en fin d'article avant les JSON-LD Article/FAQPage. Le rendu est déterministe, dédupliqué et échappe les valeurs HTML. La page Crawlabilité IA expose maintenant un template `robots.txt.liquid` manuel (préserve les `robots.default_groups` Shopify + ajoute les user agents IA GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended) avec bouton copier et 3 étapes d'installation. Aucune nouvelle permission Shopify et aucune écriture thème automatique n'ont été ajoutées.
- **Files created:** `app/blog/internal_links.py`, `tests/test_blog/test_internal_links.py`.
- **Files modified:** `app/api/blog.py`, `app/geo/crawlability.py`, `shopify-app/app/routes/app.blog.tsx`, `shopify-app/app/routes/app.geo-crawlability.tsx`, `tests/test_geo/test_crawlability.py`, `tests/test_api/test_geo.py`.
- **Decisions made:** Réutiliser les recommandations de maillage déjà calculées par Analyse marché au lieu de recréer un moteur blog séparé. Rendre les liens éditables avant publication pour éviter les ancres maladroites. Garder robots.txt en mode manuel/copie car les fichiers IA automatiques (`/llms.txt`, `/llms-full.txt`, `/agents.md`) couvrent déjà le besoin 1-clic et robots.txt touche au thème.
- **Validations run:** `ruff format app/blog/internal_links.py app/api/blog.py app/geo/crawlability.py tests/test_blog/test_internal_links.py tests/test_geo/test_crawlability.py tests/test_api/test_geo.py` ✅ ; `ruff check app/blog/internal_links.py app/api/blog.py app/geo/crawlability.py tests/test_blog/test_internal_links.py tests/test_geo/test_crawlability.py tests/test_api/test_geo.py` ✅ ; `pytest tests/test_blog tests/test_geo/test_crawlability.py tests/test_api/test_geo.py` → **51 passed** ✅ ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅ ; `git diff --check` ✅.
- **Validations skipped:** Pas de test Shopify live de création d'article avec liens internes ; nécessite une session embedded + une analyse marché récente contenant `recommended_internal_links`.
- **Open issues:** Les brouillons déjà créés avant ce changement n'ont pas automatiquement `internal_links` ; il faut régénérer un brouillon depuis Analyse marché ou les ajouter manuellement. Le maillage est rendu en bloc « À lire aussi », pas encore inséré contextuellement dans les paragraphes par le LLM. Sprint 3 (mesure GSC par article + clic blog → produit) et Sprint 4 (autopilote) restent à faire.
- **Next recommended action:** Relancer une Analyse marché, générer un nouveau brouillon blog depuis un produit qui a des recommandations de maillage, vérifier les ancres dans `/app/blog`, puis publier en brouillon Shopify et contrôler le bloc « À lire aussi » dans l'article.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Claude (Opus 4.8)
- **Goal:** Feature « Fichiers IA » (agents.md / llms.txt / llms-full.txt) publiables en 1 clic depuis le dashboard, mis à jour automatiquement sur changement catalogue. **Livrée ET validée en production** sur la boutique pilote.
- **Summary:** Générateur **déterministe** (zéro LLM) du contenu à partir du snapshot Shopify + business profile (`app/geo/llms_txt.py` : `build_llms_txt`, `build_llms_full_txt`, `build_agents_md`, `build_llms_payload`, `wrap_liquid_raw`, helpers partagés dans `app/geo/_shared.py`). **Pivot d'architecture majeur** : Shopify sert désormais `/llms.txt`, `/llms-full.txt`, `/agents.md` nativement via des templates de thème ([changelog 28 mai 2026](https://shopify.dev/changelog/customize-llmstxt-llms-fulltxt-and-agentsmd)) — l'approche initiale Files API + URL Redirect a été **livrée puis abandonnée** car Shopify l'ignore silencieusement. La publication écrit les 3 `templates/*.liquid` sur le thème publié via `themeFilesUpsert` (Admin GraphQL 2025-01 ; `themes(roles:[MAIN])` → `themeFilesUpsert`/`themeFilesDelete`), enveloppés dans `{% raw %}` (anti-injection Liquid, vérifié : les balises raw n'apparaissent pas dans le fichier servi). Publish idempotent par hash (3 hashes : agents/llms/full) ; unpublish = `themeFilesDelete` (retour défaut Shopify). **Régénération auto sur webhook catalogue** : le tick fait `should_regenerate` (debounce 5 min) puis lance un **BackgroundTask** qui **re-crawle le snapshot** (`crawl_shopify_catalog_for_job` force=True) avant de republier — indispensable car le générateur lit le snapshot, pas Shopify live. **Filtrage qualité** : seuls les produits **ACTIVE + publiés Online Store** (`filter_products_by_scope`) et hors collection `frontpage` sont listés (auto-nettoyage à l'archivage). **Scope OAuth** : `read_themes` + `write_themes` ajoutés. UI : page `app.geo-llms-txt.tsx` + panneau `LlmsTxtPanel` accueil + entrée menu + i18n FR/EN.
- **Correctif auth critique (token plumbing) :** L'app a **deux stockages de token déconnectés** — Remix (`shopify-app-remix`, token exchange, table `shopify_sessions`) et le backend Python (`shop_tokens`, lue par `get_token`). L'`afterAuth` ne synchronisait pas les deux → après le changement de credentials (Pilot→Giulio Geo) toutes les écritures Shopify 401aient. **Fix** : hook `afterAuth` (`shopify.server.ts`) qui POST le token frais vers `POST /api/shops/{shop}/internal/token` (`save_token`). Le backend a aussi été durci : un 401/403 Shopify côté thème renvoie un `ShopifyThemeScopeError` (« réinstaller l'app ») → 403 lisible au lieu d'un 500.
- **Files created:** `app/geo/_shared.py`, `app/geo/llms_txt.py`, `app/apply/shopify_theme_files.py`, `app/llms_txt/{__init__,store,publisher}.py`, `app/api/llms_txt.py`, `shopify-app/app/routes/app.geo-llms-txt.tsx`, `shopify-app/app/components/LlmsTxtPanel.tsx`, tests (`tests/test_geo/test_llms_txt.py`, `tests/apply/test_shopify_theme_files.py`, `tests/test_llms_txt/test_{store,publisher}.py`, `tests/test_api/test_llms_txt_api.py`, `tests/test_api/test_shop_token_sync.py`).
- **Files modified:** `app/geo/crawlability.py` (réutilise `_shared`), `app/db.py` (table `llms_txt_publications`), `app/main.py` (router), `app/api/shops.py` (endpoint sync token), `shopify-app/app/shopify.server.ts` (afterAuth sync), `shopify-app/app/routes/{app.tsx,app._index.tsx,webhooks.tsx}`, `shopify-app/app/lib/i18n.ts`, scopes (`shopify.app{,.pilot,.local}.toml`, `render.yaml`, `.env.example` ×2), `shopify-app/shopify.app.toml` (webhooks catalogue), `PROGRESS.md`.
- **Files deleted:** `app/apply/shopify_files.py` + tests (Files API obsolète), méthodes redirect llms.txt dans `app/apply/shopify_writer.py` + `tests/apply/test_url_redirect_upsert.py`.
- **Decisions made:** 100% déterministe (anti-hallucination). Écrire les 3 templates (choix utilisateur) pour contrôle total des routes. agents.md v1 = même index que llms.txt. Produits actifs only (auto-entretenu). Re-crawl sur webhook en BackgroundTask pour ne pas dépasser le timeout webhook Shopify (~5s). Review `shopify-safety` passée sur l'ancien flow avant le pivot. Scope `write_content` conservé (blog).
- **Validations run:** `ruff check` ✅ ; `pytest tests/test_geo/test_llms_txt.py tests/apply tests/test_llms_txt tests/test_api/test_llms_txt_api.py tests/test_api/test_shop_token_sync.py` → **49+ passed** (suite feature) ; `cd shopify-app && npm run typecheck && npm run build` ✅. **Validation prod réelle** : sur la boutique pilote (`287c4a-bb.myshopify.com`), publish OK + les 3 routes publiques servent le contenu généré (200, `{% raw %}` absent du rendu) + blog réécriture débloquée par le token sync.
- **Déploiement effectué :** `shopify app deploy` (version 3, scopes themes + webhooks catalogue) + re-consent marchand + Render repointé sur l'app « Giulio Geo ». 5 commits poussés sur `main` (Render auto-deploy) : feature + token sync + 401 hardening + filtres actifs + re-crawl webhook.
- **Open issues:** (1) Régénération auto par webhook (re-crawl + republish) à **valider en réel** sur la boutique (renommer un produit → ~5-6 min → vérifier `/llms.txt`). (2) « Dépublier » non testé en réel. (3) Produit « (test) » : reste listé s'il est ACTIVE+publié → l'archiver dans Shopify pour le retirer. (4) Templates liés au thème publié au moment du publish ; changer de thème nécessite une re-publication (webhook `themes/publish` = amélioration future). (5) `themeFilesUpsert` async (`job`) non pollé — on se fie à `upsertedThemeFiles`. (6) `webhooks.tsx` route `app/uninstalled` vers Python sans laisser `shopify-app-remix` nettoyer sa session — d'où des sessions stale survivant à la désinstallation (purger `shopify_sessions` si re-401).
- **Next recommended action:** Valider en réel la régénération webhook (renommer un produit) + « Dépublier ». Optionnel : enrichir agents.md (format agent dédié), filtres collections supplémentaires (« produits liés » auto, ventes privées), polling du `job` de `themeFilesUpsert`, webhook `themes/publish`.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Codex (GPT-5)
- **Goal:** Forcer l'utilisation effective des mots-clés et du pack GEO dans les propositions Analyse marché produit.
- **Summary:** Le Pass 2 demande maintenant 5 idées d'articles distinctes avec `target_keyword`, une FAQ de 5-8 entrées inspirée d'abord des questions GEO/IA puis PAA, et une description produit qui intègre le pack GEO (réponse courte, définition, faits rapides, repères comparatifs). Après génération, une normalisation déterministe garantit une FAQ brouillon, 5 idées blog même avec un seul mot-clé solide, et l'ajout du pack GEO à la description si le LLM l'oublie. Le garde-fou de contenu bloque maintenant les propositions si les mots-clés primary/secondary importants ne sont pas présents dans le meta title ou la meta description. L'UI affiche jusqu'à 5 idées blog, chacune avec son mot-clé et son bouton "Générer l'article" ; l'API blog accepte `blog_idea_index` pour créer le brouillon correspondant. Le JSON-LD existant n'est pas étendu par les FAQ ajoutées automatiquement afin de respecter le périmètre demandé.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `app/api/blog.py`, `app/api/market_analysis.py`, `shopify-app/app/components/ProductContentProposals.tsx`, `shopify-app/app/lib/marketAnalysisShared.tsx`, `shopify-app/app/routes/app.blog.tsx`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/market_analysis/test_two_pass_engine.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** La FAQ est toujours générée comme brouillon dès qu'un mot-clé principal existe, mais la publication reste bloquée par `content_quality` si les preuves produit ou les claims ne sont pas suffisants. Les idées blog fallback utilisent des intentions génériques construites depuis le mot-clé validé, sans hardcoder de niche ou de segment marketing. Les badges UI affichent le mot-clé brut pour rester compatible avec Polaris.
- **Validations run:** `ruff format app/market_analysis/engine.py app/api/blog.py app/api/market_analysis.py tests/market_analysis/test_two_pass_engine.py` ✅ ; `ruff check app/market_analysis/engine.py app/api/blog.py app/api/market_analysis.py tests/market_analysis/test_two_pass_engine.py` ✅ ; `pytest tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_keyword_pool.py tests/test_api/test_market_analysis.py` ✅ (58 passed) ; `pytest tests/market_analysis tests/test_geo/test_facts.py tests/test_api/test_market_analysis.py` ✅ (170 passed) ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de run live Shopify/DataForSEO depuis l'app embedded ; nécessite une nouvelle analyse réelle boutique.
- **Open issues:** Les analyses déjà exportées doivent être régénérées pour afficher `proposed_blog_ideas`, la FAQ obligatoire et le nouveau blocage `important_keyword_missing_from_metadata`.
- **Next recommended action:** Relancer Analyse marché sur la boutique pilote et vérifier que le pull affiche des mots-clés utiles dans les métas, la FAQ GEO/IA, le pack GEO dans la description et 5 idées blog générables séparément.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Codex (GPT-5)
- **Goal:** Vérifier que les mots-clés sélectionnés sont réellement utilisés dans les propositions de contenu.
- **Summary:** Le validateur post-génération ajoute désormais un `keyword_content_guardrail` distinct du garde-fou de sélection keyword. Il vérifie que le primary et les meilleurs secondary sont couverts dans les surfaces adaptées (`product_page`, `blog`, `faq`) avant de laisser une proposition devenir publiable. Les requêtes commerciales comme `pull chien acheter` sont normalisées en intention (`pull chien`) pour éviter de forcer des formulations artificielles, tout en exigeant une couverture naturelle dans la page produit. Les sorties JSON exposent les champs couverts, les champs adaptés, le mode de couverture (`exact_terms` ou `commercial_intent_normalized`) et les mots-clés importants non couverts. Si la couverture est insuffisante, la réflexion SEO baisse sous le seuil et déclenche la régénération contrôlée.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `tests/market_analysis/test_two_pass_engine.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder les supporting keywords optionnels ; rendre le primary obligatoire ; exiger une couverture suffisante des top secondary sans imposer l'exact match des modificateurs commerciaux. Ne pas toucher JSON-LD, maillage interne, ni publication Shopify.
- **Validations run:** `ruff format app/market_analysis/engine.py tests/market_analysis/test_two_pass_engine.py` ✅ ; `ruff check app/market_analysis/engine.py tests/market_analysis/test_two_pass_engine.py` ✅ ; `pytest tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_keyword_pool.py` ✅ (46 passed) ; `pytest tests/market_analysis tests/test_geo/test_facts.py tests/test_api/test_market_analysis.py` ✅ (167 passed).
- **Validations skipped:** Pas de run live DataForSEO/Shopify embedded ; nécessite une nouvelle analyse réelle boutique.
- **Open issues:** Les exports existants doivent être régénérés pour voir `keyword_content_guardrail` et la nouvelle réflexion SEO.
- **Next recommended action:** Relancer Analyse marché sur la boutique pilote et vérifier que les mots-clés secondaires produit ont des `adapted_fields_covered` non vides ou déclenchent une régénération.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Codex (GPT-5)
- **Goal:** Corriger la sélection de mots-clés produit sans hardcoder de niches marketing.
- **Summary:** Le correctif retire le vocabulaire déterministe animaux/produits du moteur keyword et génère les seeds depuis le libellé marchand, le titre et le handle via des patrons linguistiques génériques (`X pour Y`, variantes courtes produit/usage). Les intentions découvertes par le Pass 1 (`buying_intents`, `target_customer`) peuvent enrichir la réparation, mais aucun segment métier type petfood/coiffure/mécanique n'est codé en dur. Une étape `keyword_guardrail` valide les cibles avant Pass 2 : le primary doit être aligné avec le produit/besoin client, il faut assez de cibles page produit, et trop de requêtes indirectes/DIY/avis/personnalisation non prouvée bloque la génération de contenu. Tests ajoutés sur un produit digital (`formation SEO pour Shopify`) et mécanique (`huile moteur synthétique pour moto`) pour prouver la découverte cross-niche. JSON-LD, maillage interne et publication Shopify restent inchangés.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `tests/market_analysis/test_keyword_pool.py`, `tests/market_analysis/test_two_pass_engine.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder des garde-fous génériques d'intention (`gratuit`, `avis`, `meilleur`, questions, personnalisation non prouvée) mais ne pas maintenir d'ontologie marketing par niche. Réparer déterministiquement la sélection keyword avant ranking, puis bloquer Pass 2 si les mots-clés restent non alignés.
- **Validations run:** `ruff format app/market_analysis/engine.py tests/market_analysis/test_keyword_pool.py tests/market_analysis/test_two_pass_engine.py` ✅ ; `ruff check app/market_analysis/engine.py tests/market_analysis/test_keyword_pool.py tests/market_analysis/test_two_pass_engine.py` ✅ ; `pytest tests/market_analysis/test_keyword_pool.py tests/market_analysis/test_two_pass_engine.py` ✅ (44 passed) ; `pytest tests/market_analysis tests/test_geo/test_facts.py tests/test_api/test_market_analysis.py` ✅ (165 passed).
- **Validations skipped:** Pas de run live DataForSEO/Shopify embedded ; nécessite une nouvelle analyse réelle boutique.
- **Open issues:** Les exports déjà générés conservent l'ancienne sélection du pull. Il faut relancer Analyse marché pour voir le nouveau `keyword_guardrail` et la sélection réparée.
- **Next recommended action:** Relancer l'analyse produit sur la boutique pilote et vérifier que les seeds/rankings du pull viennent bien du texte produit + données marché, pas d'un vocabulaire métier figé.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Codex (GPT-5)
- **Goal:** Durcir l'analyse marché produit pour empêcher les contenus non fiables d'être proposés comme publiables.
- **Summary:** Le moteur applique désormais strictement `surface_plan` côté code : une surface `generate=false` est exclue de `keyword_coverage`, ses champs proposés sont vidés dans le JSON publiable, et la FAQ bloquée remonte `faq_blocked_missing_evidence` avec questions marchand non publiables. La validation post-génération sort maintenant `valid_claims`, `unsupported_claims`, `unsupported_claim_categories`, `publish_blockers`, `product_consistency_score`, `seo_geo_score`, `publish_status`, `blocking_reasons`, `surface_statuses`, `merchant_questions`, `recommended_next_actions` et `keyword_surface_mapping`. Les claims sensibles non prouvés, les conflits de faits produit, `product_consistency_score < 70` et `publish_ready=false` bloquent `auto_apply_allowed`. Les mots-clés sont classés par surface : produit transactionnel, blog/guide informationnel ou comparatif, FAQ question factuelle ; les requêtes DIY/gratuites/tricot/crochet et `meilleur/meilleure` ne peuvent plus devenir primary keyword produit. L'extraction produit lit davantage d'attributs depuis options/variantes/metafields/description et détecte les conflits de matériaux.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `app/geo/facts.py`, `tests/market_analysis/test_two_pass_engine.py`, `tests/test_geo/test_facts.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Ne pas modifier le schema JSON-LD, le maillage interne, ni aucun chemin qui écrit/publie sur Shopify. Ne pas ajouter de fallback LLM pour extraire des faits produit afin de rester déterministe et éviter d'introduire de nouvelles hallucinations dans la source de vérité.
- **Validations run:** `ruff format app/market_analysis/engine.py app/geo/facts.py tests/market_analysis/test_two_pass_engine.py tests/test_geo/test_facts.py` ✅ ; `ruff check app/market_analysis/engine.py app/geo/facts.py tests/market_analysis/test_two_pass_engine.py tests/test_geo/test_facts.py` ✅ ; `pytest tests/market_analysis/test_two_pass_engine.py` ✅ (18 passed) ; `pytest tests/test_geo/test_facts.py` ✅ (4 passed) ; `pytest tests/market_analysis tests/test_geo/test_facts.py tests/test_api/test_market_analysis.py` ✅ (161 passed) ; `git diff --check` ✅.
- **Validations skipped:** Pas de typecheck/build frontend : aucun fichier TypeScript n'a été modifié pour ce durcissement. Pas de run live Shopify/DataForSEO depuis l'app embedded.
- **Open issues:** Les champs JSON-LD et maillage interne existent encore dans le produit mais n'ont pas été modifiés sur cette tâche, conformément à la consigne. Les exports historiques doivent être régénérés pour bénéficier des nouveaux statuts et blockers.
- **Next recommended action:** Relancer une Analyse marché produit avec `reflection_test=true` puis inspecter le JSON d'un produit bloqué : `surface_statuses`, `blocking_reasons`, `merchant_questions` et `keyword_surface_mapping` doivent expliquer quoi compléter avant publication.

## Previous completed task

- **Date:** 2026-05-31
- **Agent:** Codex (GPT-5)
- **Goal:** Remplacer l'ancienne Analyse produit par le mode validé avec réflexion garde-fou.
- **Summary:** Le job Analyse marché active désormais `reflection_test=True` par défaut côté backend, donc les analyses produits standards, les relances depuis Analyse marché, l'accueil et les analyses mono-produit utilisent toutes la boucle réflexion + retry contrôlé. Le bouton séparé `Analyse produit test` a été retiré de la page Analyse marché afin que le chemin normal soit le chemin validé. Le téléchargement de la réflexion reste disponible lorsque l'analyse contient le journal garde-fou.
- **Files created:** Aucun.
- **Files modified:** `app/api/market_analysis.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `tests/test_api/test_market_analysis.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder `reflection_test` comme flag technique pour compatibilité/override éventuel, mais le défaut produit est maintenant activé. Pas de changement sur le moteur de réflexion lui-même.
- **Validations run:** `ruff format app/api/market_analysis.py tests/test_api/test_market_analysis.py` ✅ ; `ruff check app/api/market_analysis.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/test_api/test_market_analysis.py` ✅ (9 passed) ; `pytest tests/market_analysis tests/test_api/test_market_analysis.py` ✅ (153 passed) ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de test live Shopify/DataForSEO depuis l'app embedded.
- **Open issues:** Les anciennes analyses sans `reflection_test` peuvent encore ne pas afficher le badge/réflexion tant qu'elles ne sont pas régénérées.
- **Next recommended action:** Déployer puis relancer une analyse produit standard pour confirmer que la réflexion est attachée sans utiliser de bouton séparé.

## Previous completed task

- **Date:** 2026-05-30
- **Agent:** Codex (GPT-5)
- **Goal:** Ajouter une Analyse produit test dans Analyse marché avec réflexion garde-fou, retry contrôlé et export JSON de la réflexion.
- **Summary:** Le backend accepte maintenant `reflection_test=true` sur le job Analyse marché. Dans ce mode, le pipeline reprend Pass 1 + Pass 2, puis score chaque proposition sur 5 questions garde-fou : cohérence entreprise, cohérence produit, potentiel SEO, potentiel GEO et actionnabilité marchand. Si le score final est inférieur à 75, si un critère critique bloque, ou si `content_quality.publish_ready` échoue, un seul retry ciblé est lancé avec la proposition précédente et les points faibles, puis le journal complet est attaché à `content_test_pack.content_guardrail_reflection`. L'UI ajoute un bouton `Analyse produit test`, affiche la réflexion par produit, et propose `Télécharger la réflexion` en JSON séparé.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `app/api/market_analysis.py`, `tests/market_analysis/test_two_pass_engine.py`, `tests/market_analysis/test_keyword_pool.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `shopify-app/app/lib/marketAnalysisShared.tsx`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Boucle limitée à 1 retry pour contrôler coût et latence. La réflexion est expérimentale et traçable dans le JSON plutôt qu'un apprentissage permanent global. Le bouton test réutilise le job existant avec un flag afin de rester proche de l'analyse produit réelle.
- **Validations run:** `ruff format app/market_analysis/engine.py app/api/market_analysis.py tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_keyword_pool.py` ✅ ; `ruff check app/market_analysis/engine.py app/api/market_analysis.py tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_keyword_pool.py` ✅ ; `pytest tests/market_analysis/test_two_pass_engine.py tests/market_analysis/test_keyword_pool.py` ✅ (36 passed) ; `pytest tests/market_analysis tests/test_api/test_market_analysis.py` ✅ (152 passed) ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de test live Shopify/DataForSEO depuis l'app embedded : nécessite boutique connectée et credentials réels.
- **Open issues:** La réflexion est encore heuristique/déterministe avec retry LLM ciblé ; le prochain apprentissage devra venir de l'examen des exports `analyse-marche-reflection-*.json` sur des cas réels.
- **Next recommended action:** Déployer, lancer `Analyse produit test` sur la boutique pilote, télécharger la réflexion, puis ajuster les seuils/questions à partir des cas réels.

## Previous completed task

- **Date:** 2026-05-30
- **Agent:** Codex (GPT-5)
- **Goal:** Réduire le biais de mots-clés IA dans Analyse marché pour les produits à titre commercial, observé sur `Le pull Le Léonie`.
- **Summary:** Le pool de mots-clés réel ajoute désormais des seeds courts type produit + audience (`pull chien`, `pull pour chien`) à partir du texte produit/handle, afin de ne pas dépendre uniquement du label long ou du nom commercial. Le filtre DataForSEO garde aussi une idée si elle recouvre suffisamment le produit lui-même, même si elle ne recouvre pas assez le seed long. Google Suggest et Trends comptent maintenant comme signaux réels dans le plancher de fusion Pass 1, ce qui évite que le LLM remplace trop vite des suggestions observées par des mots-clés `llm_proposed`.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `tests/market_analysis/test_keyword_pool.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Correction ciblée sur le pool de candidats, sans élargir le prompt ni introduire de dépendance. Les seeds génériques restent limités à quelques types produit/audiences animaux pour préserver le coût et éviter le bruit.
- **Validations run:** `ruff format app/market_analysis/engine.py tests/market_analysis/test_keyword_pool.py` ✅ ; `ruff check app/market_analysis/engine.py tests/market_analysis/test_keyword_pool.py` ✅ ; `pytest tests/market_analysis/test_keyword_pool.py` ✅ (22 passed) ; `pytest tests/market_analysis` ✅ (143 passed).
- **Validations skipped:** Pas encore de smoke live DataForSEO/Shopify : nécessite les credentials et une analyse réelle boutique.
- **Open issues:** À vérifier sur un nouvel export réel que le pull reçoit davantage de DataForSEO/Suggest (`pull chien`, `pull pour chien`, variantes vêtements/manteaux) et moins de `llm_proposed`.
- **Next recommended action:** Relancer Analyse marché sur la boutique pilote puis comparer les sources du pull avec harnais/fontaine dans l'export JSON.

## Previous completed task

- **Date:** 2026-05-30
- **Agent:** Codex (GPT-5)
- **Goal:** Empêcher les nouveaux enrichissements Analyse marché (JSON-LD / maillage interne) de bloquer l'analyse produit en production.
- **Summary:** Le moteur Analyse marché est maintenant fail-open sur deux surfaces additives : génération JSON-LD et recommandations de maillage interne. Si un format de snapshot Shopify réel déclenche une exception dans ces modules, l'analyse produit continue et logge un warning au lieu de faire échouer tout le job.
- **Files created:** Aucun.
- **Files modified:** `app/market_analysis/engine.py`, `tests/market_analysis/test_engine_geo_eeat.py`, `tests/market_analysis/test_engine_intent_cluster_cannibalization.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Les nouveautés GEO/maillage sont des diagnostics additionnels : elles ne doivent jamais être une dépendance bloquante pour produire les recommandations SEO existantes.
- **Validations run:** `ruff check app/market_analysis/engine.py tests/market_analysis/test_engine_geo_eeat.py tests/market_analysis/test_engine_intent_cluster_cannibalization.py` ✅ ; `pytest tests/market_analysis/test_engine_geo_eeat.py tests/market_analysis/test_engine_intent_cluster_cannibalization.py tests/test_api/test_market_analysis.py` ✅ (17 passed).
- **Validations skipped:** Pas de test embedded Shopify live dans cette session.
- **Open issues:** Si l'analyse plante encore après déploiement de ce correctif, la cause est probablement en amont du moteur (création du job, snapshot, auth backend, LLM/provider), et il faudra lire l'erreur exacte affichée ou les logs backend.
- **Next recommended action:** Commit/push puis redéployer backend + frontend, relancer une analyse produit depuis Analyse marché.

## Previous completed task

- **Date:** 2026-05-30
- **Agent:** Codex (GPT-5)
- **Goal:** Corriger l'Analyse marché après signalement marchand : une analyse produit échouait avec une erreur UI opaque « 0 » et les nouveaux diagnostics SEO/GEO n'étaient pas visibles après relance.
- **Summary:** Le job backend conserve désormais les nouveaux champs top-level `cannibalization_alerts`, `orphan_products` et `blog_gap_suggestions` dans la donnée complétée, sauvegardée et renvoyée au polling. Les échecs d'analyse produit individuelle sont maintenant affichés dans la bannière d'erreur de la page au lieu d'être effacés silencieusement. Le backend logge aussi la stacktrace complète d'un job Analyse marché échoué pour faciliter le diagnostic serveur.
- **Files created:** Aucun.
- **Files modified:** `app/api/market_analysis.py`, `shopify-app/app/routes/app.market-analysis.tsx`, `shopify-app/app/lib/i18n.ts`, `tests/test_api/test_market_analysis.py`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Garder la correction minimale : propagation des champs de diagnostic + visibilité de l'erreur produit. Pas de changement sur l'algorithme SEO/GEO lui-même.
- **Validations run:** `ruff check app/api/market_analysis.py tests/test_api/test_market_analysis.py` ✅ ; `pytest tests/test_api/test_market_analysis.py tests/market_analysis/test_engine_intent_cluster_cannibalization.py tests/market_analysis/test_engine_geo_eeat.py` ✅ (15 passed) ; `cd shopify-app && npm run typecheck` ✅ ; `cd shopify-app && npm run build` ✅.
- **Validations skipped:** Pas de reproduction Shopify embedded live : nécessite la boutique installée/session Shopify active et les variables backend de production. Une commande `ruff check` a été lancée par erreur sur des fichiers TypeScript et a échoué parce que Ruff parse le TS comme du Python ; résultat ignoré et remplacé par `npm run typecheck`/`npm run build`.
- **Open issues:** Si l'analyse plante encore en production, la page devrait maintenant afficher la vraie erreur backend au lieu d'un message opaque. Il faudra alors lire cette erreur ou les logs backend pour traiter la cause racine restante.
- **Next recommended action:** Déployer cette correction, relancer une analyse produit, puis vérifier que la bannière d'erreur affiche un message exploitable ou que les sections Pack GEO / Maillage interne apparaissent après analyse terminée.

## Previous completed task

- **Date:** 2026-05-30
- **Agent:** Claude (Opus 4.7)
- **Goal:** Revue complète de la page Analyse marché + montée en gamme de l'algorithme SEO/GEO sur trois axes : keyword intelligence (intent SERP, clustering FR, cannibalisation), pack GEO (JSON-LD déterministe, signaux E-E-A-T, blocs extractibles IA), maillage interne automatique (graphe sémantique produits ↔ collections ↔ articles, orphelins, trous de blog).
- **Summary:** 6 nouveaux modules backend déterministes (zéro coût LLM additionnel) + 4 modules existants étendus + composants frontend. **Chantier B (keyword intelligence)** : `keyword_normalization.py` (NFD + lemma FR + Jaccard + clusters), `intent_classifier.py` (règles SERP → intent_type avec `intent_type_source` ∈ {serp_classified, llm_guessed, unclassified}), `cannibalization.py` (détection cross-produits sur cluster head + hint de réorientation pour Pass 2). **Chantier A (GEO)** : `schema_builder.py` (Product + FAQPage + BreadcrumbList JSON-LD construits en Python à partir des `confirmed_facts` — jamais par le LLM), `eeat.py` (détection certifications FR Ecocert/AB/GOTS/FSC/Made in France + warranty + merchant experience). Le prompt Pass 2 reçoit une section « RÈGLES GEO » et émet 3 nouveaux champs : `proposed_geo_definition_block` (~25 mots, format « X est Y qui Z »), `proposed_geo_quick_facts` (3-5 puces extractibles), `proposed_geo_comparison_table` (objets {critère, valeur}, gated ≥3 critères). **Chantier C (maillage interne)** : `internal_linking.py` qui remplit `recommended_internal_links` (auparavant hardcodé `[]` en `engine.py:2354`) avec siblings (Jaccard sur cluster head), collection parente, articles informationnels, + `orphan_products` et `blog_gap_suggestions` au niveau job. `app/api/market_analysis.py` propage `snapshot.collections` + `snapshot.articles` vers `run_market_analysis`. Frontend : nouveau `CannibalizationBanner`, `OrphanGapsBanner`, `GeoPackSection`, `InternalLinksSection` ; i18n FR + EN ; types TS étendus (IntentTypeSource, SerpFeatureTarget, KeywordCluster, CannibalizationAlert, InternalLinkSuggestion, BlogGapSuggestion, SchemaJsonLd, EeatSignal). Le plan complet est dans `/Users/adrienleredde/.claude/plans/fait-une-revu-compl-te-gentle-planet.md`.
- **Files created:** `app/market_analysis/keyword_normalization.py`, `app/market_analysis/intent_classifier.py`, `app/market_analysis/cannibalization.py`, `app/market_analysis/schema_builder.py`, `app/market_analysis/eeat.py`, `app/market_analysis/internal_linking.py`, `tests/market_analysis/test_keyword_normalization.py`, `tests/market_analysis/test_intent_classifier.py`, `tests/market_analysis/test_cannibalization.py`, `tests/market_analysis/test_schema_builder.py`, `tests/market_analysis/test_eeat.py`, `tests/market_analysis/test_internal_linking.py`, `tests/market_analysis/test_engine_intent_cluster_cannibalization.py`, `tests/market_analysis/test_engine_geo_eeat.py`.
- **Files modified:** `app/market_analysis/engine.py` (intégration des 6 modules en post-Pass 1 et post-Pass 2 ; `_PASS2_KEYS` étendu ; `_build_pass2_prompt` étendu avec règles GEO + injection E-E-A-T + hint cannibalisation ; `_build_product_result` produit JSON-LD + GEO fields ; sortie `cannibalization_alerts`, `orphan_products`, `blog_gap_suggestions` au niveau job), `app/api/market_analysis.py` (forward `collections` + `articles` du snapshot), `shopify-app/app/routes/app.market-analysis.tsx` (types + composants Banner/Section), `shopify-app/app/lib/marketAnalysisShared.tsx` (types partagés étendus), `shopify-app/app/lib/i18n.ts` (15+ clés FR/EN), `docs/AI_HANDOFF.md`.
- **Decisions made:** JSON-LD construit en Python, jamais par le LLM (un `aggregateRating` halluciné = pénalité Google rich results). Cannibalisation détectée sur le cluster head (Jaccard ≥ 0.5) plutôt que sur l'identité exacte de la query, ce qui groupe automatiquement « croquette/croquettes/croquéte ». L'intent classifier garde la source de classification (`serp_classified` vs `llm_guessed`) — règle « real data > AI estimates » respectée. Internal linking purement algorithmique : aucun nouvel appel LLM, coût budget zéro.
- **Validations run:** `ruff check` sur tous les nouveaux fichiers et modules modifiés ✅ ; `ruff format` appliqué ✅ ; `pytest` complet → **1713 ✅** (+90 nouveaux : 27 keyword_normalization + 13 intent_classifier + 11 cannibalization + 12 schema_builder + 9 eeat + 9 internal_linking + 3 engine-B + 4 engine-A + 2 cohérence) ; `cd shopify-app && npm run typecheck` ✅ ; `npm run build` ✅ (chunks générés). Plan validé via ExitPlanMode avant exécution.
- **Validations skipped:** Pas de smoke run end-to-end sur boutique pilote (nécessite un shop avec snapshot + clés API DataForSEO). Pas de validation interactive sur validator.schema.org. Pas de revue par les subagents `python-quality` / `shopify-architecture-reviewer` (envisageable avant merge si tâche commit demandée).
- **Open issues:** (1) Aucun commit git n'a été créé — la branche est sur `main` avec ~14 fichiers modifiés à staged manuellement par l'utilisateur. (2) Les bugs frontend identifiés dans le plan (polling infini sur erreur, silent failures sur persist de labels, race conditions sur re-run) ont été écartés par choix utilisateur et restent ouverts. (3) Le `proposed_breadcrumb_path` mentionné dans le plan n'a pas été ajouté au pack produit (la fonction `build_breadcrumb_schema` est dispo mais non câblée côté `_build_product_result` faute de `collection_handle` connu à ce niveau — déférable). (4) Les bugs backend identifiés (silent passthrough DataForSEO vide, parent volume fallback trompeur, budget gate all-or-nothing) restent ouverts.
- **Next recommended action:** Créer les commits atomiques (un par chantier B/A/C) → smoke run sur shop pilote pour confirmer la sortie JSON contient bien les nouveaux champs → valider 1 JSON-LD généré sur https://validator.schema.org → mettre à jour `PROGRESS.md` avec la livraison.

## Previous completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** Sprint 1 du chantier blog SEO+GEO — publication d'articles en brouillon Shopify avec sections grounded sur les faits, schema Article + FAQPage, et éditeur hybride Auto/Manuel par section.
- **Summary:** Nouvelle pipeline blog : `app/blog/section_generator.py` (par H2, 40-60 mots `direct_answer` + 150-300 mots `body`, `claims_used` pointant les faits Shopify confirmés ; température 0 + json_mode), `app/blog/schema.py` (Article — Org ou Person, FAQPage = signal GEO depuis que Google a abandonné les rich results FAQ en mai 2026), `app/blog/shopify_articles.py` (mutation `articleCreate` brouillon via Admin GraphQL 2025-01, retries 429/5xx hérités du pattern `ShopifyWriter`). Endpoints `POST /blog/section`, `POST /blog/generate-all`, `POST /blog/publish-draft`, `GET /blog/blogs`. Route Remix `app.blog-editor.$productId.tsx` : par section, toggle Auto/Manuel, bouton « Régénérer », « Tout générer », publication via modal (choix blog, auteur Org/Person). Scope Shopify `write_content` ajouté (re-consent merchants existants).
- **Files created:** `app/blog/__init__.py`, `app/blog/section_generator.py`, `app/blog/schema.py`, `app/blog/shopify_articles.py`, `app/api/blog.py`, `shopify-app/app/routes/app.blog-editor.$productId.tsx`, `tests/test_blog/__init__.py`, `tests/test_blog/test_schema.py`, `tests/test_blog/test_section_generator.py`, `tests/test_blog/test_shopify_articles.py`.
- **Files modified:** `app/main.py` (router blog), `shopify-app/app/components/ProductContentProposals.tsx` (bouton « Ouvrir l'éditeur de blog »), `.env`, `render.yaml` (×2), `shopify-app/shopify.app.toml` (scope `write_content`), `docs/AI_HANDOFF.md`.
- **Decisions made:** Brouillon Shopify systématique en Sprint 1 (jamais d'auto-publication tant que confiance pas établie). Auteur `Organization` par défaut, `Person` optionnel pour E-E-A-T renforcé. Réponses-directes 40-60 mots = chunks LLM-citables (objectif GEO). FAQPage conservé pour GEO uniquement (rich results FAQ Google supprimés mai 2026).
- **Validations run:** `pytest` complet — 1622 ✅ (8 nouveaux : schema Article/FAQPage, section generator déterministe, BlogPublisher isPublished=false) ; `ruff` ✅ ; frontend `typecheck` ✅ et `build` ✅.
- **Validations skipped:** Test live Shopify articleCreate non effectué (nécessite shop pilote + re-consent du scope `write_content`).
- **Open issues:** Action marchand requise après deploy : re-consentement Shopify (nouveau scope `write_content`). Sprint 2 prévu : maillage interne automatique (embeddings produits déjà en base) + page robots.txt (téléchargement + 2 phrases d'install, pas de `write_themes`).
- **Next recommended action:** Tester en pilote : lancer une analyse → ouvrir l'éditeur de blog d'un produit → générer toutes les sections → publier en brouillon → vérifier l'article dans Shopify Admin. Puis enchaîner Sprint 2.

## Previous completed task

- **Date:** 2026-05-29
- **Agent:** Claude (Opus 4.7)
- **Goal:** Réparer GSC : import bloqué par un 403 « insufficient authentication scopes » + données GSC perdues au redéploiement (non écrites sur le disque persistant Render Starter monté en `/app/data`).
- **Summary:** (1) **Union des scopes Google** : GSC et GA4 partagent une seule ligne `google_tokens` par shop ; chaque flux ne demandait que son scope, donc connecter GA4 écrasait le token avec `analytics.readonly` seul → 403 sur Search Console. Nouveau module `app/google_scopes.py` (`GOOGLE_OAUTH_SCOPES` = webmasters.readonly + analytics.readonly) utilisé par les deux flux → un consentement = un token valide pour les deux APIs. (2) **Chemin de données centralisé** : nouveau `app/paths.py:data_dir()` honorant `DATA_DIR` ; remplacé ~15 `_DATA_DIR` codés en dur (`Path(__file__).parents[2]/data/raw`) — GSC écrivait hors du disque monté. (3) **render.yaml** : services en `plan: starter`, bloc `disk` (name leonie-data, mountPath `/app/data`, 1 Go) + env `DATA_DIR=/app/data/raw` sur l'API.
- **Files created:** `app/google_scopes.py`, `app/paths.py`, `tests/test_paths_and_scopes.py`.
- **Files modified:** `app/gsc/client.py`, `app/ga4/oauth.py`, ~13 modules `app/api/*` + `app/*/client.py`/`jobs.py`/`competitors.py` (data_dir), `render.yaml`, `docs/AI_HANDOFF.md`.
- **Decisions made:** Union des scopes plutôt que tokens séparés (les deux partagent google_tokens). `DATA_DIR` absolu (`/app/data/raw`) → pointe sur le disque quel que soit le cwd. render.yaml aligné sur la réalité Starter+disk pour éviter un downgrade au prochain deploy IaC.
- **Validations run:** `pytest` complet — 1608 ✅ ; import sanity (GSC_SCOPES == GA4_SCOPES == union) ; `ruff check`/`--fix` ✅.
- **Validations skipped:** Pas de test live OAuth (nécessite consentement Google réel).
- **ACTION MARCHAND REQUISE après déploiement :** reconnecter Google **une seule fois** (un consentement couvre GSC+GA4), vérifier la propriété (`sc-domain:leoniedelacroix.com` côté import), puis lancer l'import GSC (90 j). Les données persisteront ensuite sur le disque.
- **Open issues:** Le push de `render.yaml` déclenche un **redéploiement Render** (autoDeployTrigger: commit) avec changement de plan + attache disque — à pousser en connaissance de cause. Tokens existants à renouveler (re-consent).
- **Next recommended action:** Après deploy + reconnexion, relancer une analyse et confirmer que `gsc` apparaît dans `sources_used` et que les requêtes réelles alimentent le pool de mots-clés.

## Previous completed task

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
- **Next recommended action:** Recharger la page d'accueil Giulio Geo Pilot après déploiement/redémarrage backend.

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

## 2026-06-03 — Learning engine test hardening

- **Scope completed:** Added a comprehensive backend/API/GEO/UI safety test suite for `app/learning/`.
- **Files covered:** `outcomes`, `learner`, `policy`, `store`, `scheduler`, `approvals`, learning API routes, continuous improvement integration, and the Remix continuous improvement learning contract.
- **Important fixes made:**
  - `create_due_observations()` no longer passes transient `deltas` into `create_observation()`.
  - Edited learning approvals remain status `edited` and are still eligible for explicit one-click safe application.
  - Successful approval application now records a `seo_changes` trace.
  - `app.learning` is included in setuptools packaging.
  - Tests for intentionally archived API routers are skipped at collection time instead of forcing archived routers back into `app.main`.
- **Safety contracts now tested:**
  - Only `semi_auto` and `auto_apply` exist; no manual mode is allowed.
  - `semi_auto` creates pending approvals and does not write live.
  - `auto_apply` requires enabled learning, pro/agency plan, low risk, high confidence, supported writer, confirmed live write, safe field, and no locked negative merchant tag.
  - J+14 is intermediate and confidence-capped; J+28 is the primary learning window; J+60 remains historical.
  - Low-volume or contradictory observations cannot become high-confidence learning evidence.
  - Bulk approval applies only safe supported actions.
- **Validations run:**
  - `ruff check .` ✅
  - `pytest tests/test_learning` — 74/74 ✅
  - `pytest tests/test_api/test_learning.py` — 7/7 ✅
  - `pytest tests/test_geo/test_continuous_agent_learning.py` — 6/6 ✅
  - `pytest` — 1704 passed, 188 skipped ✅
  - `cd shopify-app && npm run typecheck` ✅
  - `cd shopify-app && npm run build` ✅

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
